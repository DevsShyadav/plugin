"""
workers.py
==========
The 5 asynchronous background workers for the AI Marketing Dashboard.

Each worker is an infinite async loop that:
  1. Fetches a target (URL, RSS feed, YouTube, etc.)
  2. Scrapes relevant content via Playwright + BeautifulSoup4
  3. Calls Groq (via groq_engine.py) to select the best plugin + generate copy
  4. Submits the generated copy (form, comment, pingback, etc.)
  5. Logs results and increments metrics in the SQLite database
  6. Sleeps for a configurable interval before the next cycle

All workers share a single GroqKeyRotator instance passed in by engine.py.
They check a threading.Event (stop_event) to know when to shut down cleanly.

SCRAPING NOTES:
  - Playwright runs in headless mode for form submissions.
  - BeautifulSoup4 is used for lightweight HTML parsing.
  - Mock/seed URL lists are provided — replace with real scraping pipelines.
  - Every worker has a try/except at the top level so one crash never kills
    the entire engine.
"""

import asyncio
import logging
import os
import random
import threading
import xmlrpc.client
from datetime import datetime
from typing import Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

import database as db
from groq_engine import (
    GroqKeyRotator,
    select_best_plugin_and_generate_copy,
    build_contact_form_pitch,
    build_blog_comment,
    build_youtube_comment,
    build_reddit_reply,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable intervals (seconds between each worker cycle)
# ---------------------------------------------------------------------------
INTERVAL_CONTACT   = 120   # 2 min  — contact form submissions
INTERVAL_BLOG      = 180   # 3 min  — blog comment drops
INTERVAL_YOUTUBE   = 240   # 4 min  — YouTube comment posts
INTERVAL_PINGBACK  = 300   # 5 min  — pingback pings
INTERVAL_REDDIT    = 150   # 2.5 min — Reddit RSS monitoring

# ---------------------------------------------------------------------------
# Seed URL lists — replace / extend these with real scraping sources
# ---------------------------------------------------------------------------
# ─────────────────────────────────────────────────────────────────────────────
# TARGET CONFIGURATION — Replace these with your real targets
# ─────────────────────────────────────────────────────────────────────────────

# Real local business websites that have contact forms
# Format: full URL of the homepage (worker will auto-find /contact page)
CONTACT_TARGET_URLS: list[str] = [
    "https://wpforms.com",
    "https://elementor.com",
    "https://themeisle.com",
    "https://wpbeginner.com",
    "https://wpmailster.com",
    # Add more real business URLs here
]

# Real WP plugin review blogs that have comment sections
BLOG_TARGET_URLS: list[str] = [
    "https://wpbeginner.com/showcase/best-wordpress-plugins/",
    "https://kinsta.com/best-wordpress-plugins/",
    "https://www.wpexplorer.com/best-wordpress-plugins/",
    "https://www.elegantthemes.com/blog/wordpress/best-wordpress-plugins",
    "https://themeisle.com/blog/best-wordpress-plugins/",
]

# YouTube search queries — find videos to comment on
YOUTUBE_SEARCH_QUERIES: list[str] = [
    "WordPress tutorial 2025",
    "best WordPress plugins 2025",
    "how to speed up WordPress website",
    "WordPress SEO tutorial",
    "WordPress for beginners 2025",
    "how to make a WordPress website",
]

# Real competitor WP plugin blogs — for pingbacks
PINGBACK_COMPETITOR_BLOGS: list[str] = [
    "https://wpbeginner.com/plugins/",
    "https://kinsta.com/blog/wordpress-plugins/",
    "https://www.wpexplorer.com/wordpress-plugins-review/",
    "https://themeisle.com/blog/best-wordpress-plugins/",
]

# Reddit RSS feeds to monitor
REDDIT_RSS_FEEDS: list[str] = [
    "https://www.reddit.com/r/Wordpress/.rss",
    "https://www.reddit.com/r/webdev/.rss",
    "https://www.reddit.com/r/SEO/.rss",
    "https://www.reddit.com/r/web_design/.rss",
    "https://www.reddit.com/r/digital_marketing/.rss",
]

# Trigger words — reply when these appear in Reddit posts
REDDIT_TRIGGER_WORDS: list[str] = [
    "slow site", "expensive plugin", "my site is slow",
    "looking for a plugin", "alternative to", "high bounce rate",
    "seo problem", "need help with wordpress", "plugin recommendation",
    "wordpress is slow", "page speed", "google pagespeed",
    "wordpress plugin help", "best plugin for", "which plugin",
]



# ---------------------------------------------------------------------------
# Playwright browser launch args — required for Linux containers (HF Spaces)
# ---------------------------------------------------------------------------
# HF Spaces runs in a sandboxed Docker container. Chromium needs these flags
# to work without a real display or root-level sandbox privileges.
PLAYWRIGHT_LAUNCH_ARGS: dict = {
    "headless": True,
    "args": [
        "--no-sandbox",                  # required in Docker/root environments
        "--disable-setuid-sandbox",      # companion to --no-sandbox
        "--disable-dev-shm-usage",       # /dev/shm is tiny in containers; use /tmp
        "--disable-gpu",                 # no GPU in HF containers
        "--no-zygote",                   # avoids fork issues in sandboxed envs
        "--single-process",              # safer in constrained containers
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
        "--safebrowsing-disable-auto-update",
    ],
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _log(worker: str, message: str, status: str = "info") -> None:
    """Write to DB log and Python logger simultaneously."""
    db.add_log(worker=worker, message=message, status=status)
    getattr(logger, "info" if status != "error" else "error")(
        "[%s] %s", worker, message
    )


async def _fetch_html(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """
    Lightweight async HTML fetch via aiohttp.
    Returns raw HTML string or None on failure.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as exc:
        logger.debug("_fetch_html failed for %s: %s", url, exc)
    return None


def _extract_text(html: str, max_chars: int = 1500) -> str:
    """Strip HTML tags and return clean plain text (truncated)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)[:max_chars]


def _find_contact_url(html: str, base_url: str) -> Optional[str]:
    """
    Scan anchor tags for a /contact page link.
    Returns the full URL or None if not found.
    """
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "contact" in href:
            if href.startswith("http"):
                return a["href"]
            return base_url.rstrip("/") + "/" + a["href"].lstrip("/")
    return None



# ===========================================================================
# WORKER 1 — Contact Form Sniper
# ===========================================================================

async def worker_contact_sniper(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    """
    Worker 1: Contact Form Sniper
    ─────────────────────────────
    Cycle:
      1. Pick a random business URL from CONTACT_TARGET_URLS.
      2. Scrape homepage to find /contact page link.
      3. Use Groq to generate a fear+solution pitch for the most relevant plugin.
      4. Use Playwright to locate and fill the contact form fields.
      5. Submit the form, log result, increment forms_filled counter.

    Selector placeholders (marked with # TODO) should be updated to match
    the actual CSS selectors of your target sites.
    """
    WORKER = "Worker_Contact_Sniper"
    _log(WORKER, "Worker started.", "info")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**PLAYWRIGHT_LAUNCH_ARGS)

        async with aiohttp.ClientSession() as session:
            while not stop_event.is_set():
                try:
                    plugins = db.get_all_plugins()
                    if not plugins:
                        _log(WORKER, "No plugins configured. Waiting...", "info")
                        await asyncio.sleep(30)
                        continue

                    target = random.choice(CONTACT_TARGET_URLS)
                    _log(WORKER, f"Targeting: {target}", "info")

                    # --- Step 1: Fetch homepage & find contact page ----------
                    homepage_html = await _fetch_html(session, target)
                    if not homepage_html:
                        _log(WORKER, f"Could not reach {target}. Skipping.", "error")
                        await asyncio.sleep(INTERVAL_CONTACT)
                        continue

                    contact_url = _find_contact_url(homepage_html, target)
                    if not contact_url:
                        _log(WORKER, f"No contact page found at {target}.", "info")
                        await asyncio.sleep(INTERVAL_CONTACT)
                        continue

                    _log(WORKER, f"Found contact page: {contact_url}", "info")

                    # --- Step 2: Scrape site context for plugin selection ----
                    site_text = _extract_text(homepage_html)
                    plugin, copy = await select_best_plugin_and_generate_copy(
                        rotator, site_text, plugins, copy_type="contact"
                    )
                    _log(WORKER, f"Selected plugin: {plugin['name']}", "info")

                    # --- Step 3: Build personalised pitch --------------------
                    domain = target.split("//")[-1].split("/")[0]
                    pitch = await build_contact_form_pitch(
                        rotator,
                        business_name=domain,
                        business_context=site_text,
                        plugin=plugin,
                    )

                    # --- Step 4: Fill & submit form via Playwright -----------
                    page = await browser.new_page()
                    try:
                        await page.goto(contact_url, timeout=20000)
                        await page.wait_for_load_state("networkidle", timeout=15000)

                        # TODO: Replace selectors below with real site selectors
                        # Common patterns:  input[name="name"], #your-name, .contact-name
                        await page.fill('input[name="name"]', "Alex Johnson")          # TODO
                        await page.fill('input[name="email"]', "alex@marketingpro.io") # TODO
                        await page.fill('textarea[name="message"]', pitch)              # TODO

                        # TODO: Update submit selector to match the target form
                        await page.click('button[type="submit"]')  # TODO
                        await page.wait_for_timeout(3000)

                        db.increment_metric("forms_filled")
                        db.record_plugin_action(plugin["id"], "contact_form", "submitted", contact_url)
                        _log(
                            WORKER,
                            f"✅ Form submitted at {contact_url} for plugin '{plugin['name']}'",
                            "success",
                        )
                    except PWTimeout:
                        _log(WORKER, f"Timeout on form at {contact_url}", "error")
                    except Exception as exc:
                        _log(WORKER, f"Form submission error: {exc}", "error")
                    finally:
                        await page.close()

                except Exception as exc:
                    _log(WORKER, f"Unhandled error: {exc}", "error")

                # Sleep before next cycle (respects stop signal)
                for _ in range(INTERVAL_CONTACT):
                    if stop_event.is_set():
                        break
                    await asyncio.sleep(1)

        await browser.close()

    _log(WORKER, "Worker stopped cleanly.", "info")



# ===========================================================================
# WORKER 2 — Blog Comment Bomber
# ===========================================================================

async def worker_blog_bomber(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    """
    Worker 2: Blog Comment Bomber
    ──────────────────────────────
    Cycle:
      1. Pick a random blog from BLOG_TARGET_URLS.
      2. Scrape the page to extract article titles and snippets.
      3. Use Groq to select the most relevant plugin and write a natural comment.
      4. Use Playwright to find the comment form and auto-submit.
      5. Log result and increment comments_posted counter.

    Selector placeholders marked with # TODO — update for each target blog's
    comment form structure (WordPress default, Disqus, custom, etc.)
    """
    WORKER = "Worker_Blog_Bomber"
    _log(WORKER, "Worker started.", "info")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**PLAYWRIGHT_LAUNCH_ARGS)

        async with aiohttp.ClientSession() as session:
            while not stop_event.is_set():
                try:
                    plugins = db.get_all_plugins()
                    if not plugins:
                        _log(WORKER, "No plugins configured. Waiting...", "info")
                        await asyncio.sleep(30)
                        continue

                    target_url = random.choice(BLOG_TARGET_URLS)
                    _log(WORKER, f"Scraping blog: {target_url}", "info")

                    html = await _fetch_html(session, target_url)
                    if not html:
                        _log(WORKER, f"Could not fetch {target_url}", "error")
                        await asyncio.sleep(INTERVAL_BLOG)
                        continue

                    # --- Extract article title and body snippet ---------------
                    soup = BeautifulSoup(html, "lxml")
                    title_tag = soup.find("h1") or soup.find("h2")
                    article_title = title_tag.get_text(strip=True) if title_tag else target_url

                    article_snippet = _extract_text(html, max_chars=800)

                    # --- Groq: pick plugin + generate contextual comment ------
                    plugin, _ = await select_best_plugin_and_generate_copy(
                        rotator, article_snippet, plugins, copy_type="blog"
                    )
                    comment_text = await build_blog_comment(
                        rotator,
                        article_title=article_title,
                        article_snippet=article_snippet,
                        plugin=plugin,
                    )
                    _log(WORKER, f"Generated comment for '{plugin['name']}'", "info")

                    # --- Playwright: fill & submit comment form ---------------
                    page = await browser.new_page()
                    try:
                        await page.goto(target_url, timeout=20000)
                        await page.wait_for_load_state("networkidle", timeout=15000)

                        # TODO: Update selectors to match target blog's comment form
                        await page.fill('#author',  "Alex Johnson")           # TODO
                        await page.fill('#email',   "alex@marketingpro.io")   # TODO
                        await page.fill('#comment', comment_text)              # TODO
                        await page.click('#submit')                            # TODO
                        await page.wait_for_timeout(4000)

                        db.increment_metric("comments_posted")
                        db.record_plugin_action(plugin["id"], "blog_comment", "commented", target_url)
                        _log(
                            WORKER,
                            f"✅ Comment posted on {target_url} for '{plugin['name']}'",
                            "success",
                        )
                    except PWTimeout:
                        _log(WORKER, f"Timeout loading {target_url}", "error")
                    except Exception as exc:
                        _log(WORKER, f"Comment submission error: {exc}", "error")
                    finally:
                        await page.close()

                except Exception as exc:
                    _log(WORKER, f"Unhandled error: {exc}", "error")

                for _ in range(INTERVAL_BLOG):
                    if stop_event.is_set():
                        break
                    await asyncio.sleep(1)

        await browser.close()

    _log(WORKER, "Worker stopped cleanly.", "info")



# ===========================================================================
# WORKER 3 — YouTube Comment Hijacker
# ===========================================================================

async def worker_youtube_hijacker(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    """
    Worker 3: YouTube Comment Hijacker
    ────────────────────────────────────
    Cycle:
      1. Pick a random search query from YOUTUBE_SEARCH_QUERIES.
      2. Scrape YouTube search results page for video links & titles.
      3. For each video, use Groq to generate a helpful comment promoting
         the most relevant plugin as an alternative/companion tool.
      4. Use Playwright to navigate to the video page and post the comment.
         NOTE: YouTube requires authentication. A session/cookie injection
         approach is needed — placeholder login flow included below.

    Authentication TODO:
      - Inject saved browser cookies (export from a logged-in Chrome profile)
        via page.context.add_cookies([...]) before navigating to YouTube.
      - Or use YouTube Data API v3 with OAuth2 for programmatic posting.

    Selector placeholders marked with # TODO.
    """
    WORKER = "Worker_YouTube_Hijacker"
    _log(WORKER, "Worker started.", "info")

    # YouTube search URL template
    YT_SEARCH_BASE = "https://www.youtube.com/results?search_query="

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**PLAYWRIGHT_LAUNCH_ARGS)

        async with aiohttp.ClientSession() as session:
            while not stop_event.is_set():
                try:
                    plugins = db.get_all_plugins()
                    if not plugins:
                        _log(WORKER, "No plugins configured. Waiting...", "info")
                        await asyncio.sleep(30)
                        continue

                    query = random.choice(YOUTUBE_SEARCH_QUERIES)
                    search_url = YT_SEARCH_BASE + query.replace(" ", "+")
                    _log(WORKER, f"Searching YouTube: '{query}'", "info")

                    # --- Fetch search results page via aiohttp ---------------
                    html = await _fetch_html(session, search_url)
                    if not html:
                        _log(WORKER, "Could not fetch YouTube search page.", "error")
                        await asyncio.sleep(INTERVAL_YOUTUBE)
                        continue

                    # --- Extract video IDs from page source ------------------
                    # YouTube embeds JSON data in the page; parse video IDs
                    import re
                    video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                    video_ids = list(dict.fromkeys(video_ids))[:5]  # unique, first 5

                    if not video_ids:
                        _log(WORKER, "No video IDs found. Skipping cycle.", "info")
                        await asyncio.sleep(INTERVAL_YOUTUBE)
                        continue

                    video_id = random.choice(video_ids)
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    _log(WORKER, f"Targeting video: {video_url}", "info")

                    # --- Extract video title/description for context ---------
                    # Lightweight: parse from page meta tags
                    video_html = await _fetch_html(session, video_url)
                    video_title = query   # fallback
                    video_desc  = ""
                    if video_html:
                        vsoup = BeautifulSoup(video_html, "lxml")
                        og_title = vsoup.find("meta", property="og:title")
                        og_desc  = vsoup.find("meta", property="og:description")
                        video_title = og_title["content"] if og_title else query
                        video_desc  = og_desc["content"]  if og_desc  else ""

                    # --- Groq: pick plugin + write YouTube comment -----------
                    plugin, _ = await select_best_plugin_and_generate_copy(
                        rotator,
                        page_content=f"{video_title} {video_desc}",
                        plugins=plugins,
                        copy_type="youtube",
                    )
                    comment_text = await build_youtube_comment(
                        rotator,
                        video_title=video_title,
                        video_description=video_desc,
                        plugin=plugin,
                    )

                    # --- Playwright: post comment ----------------------------
                    page = await browser.new_page()
                    try:
                        # TODO: Inject authentication cookies before navigating
                        # await page.context.add_cookies([{...}])  # TODO

                        await page.goto(video_url, timeout=25000)
                        await page.wait_for_load_state("networkidle", timeout=20000)

                        # Scroll to comment section to trigger lazy load
                        await page.evaluate("window.scrollBy(0, 800)")
                        await page.wait_for_timeout(3000)

                        # TODO: Update selectors for YouTube's comment input
                        await page.click('#simplebox-placeholder')              # TODO
                        await page.wait_for_timeout(1500)
                        await page.fill('#contenteditable-root', comment_text)  # TODO
                        await page.wait_for_timeout(1000)
                        await page.click('#submit-button')                      # TODO
                        await page.wait_for_timeout(3000)

                        db.increment_metric("comments_posted")
                        db.record_plugin_action(plugin["id"], "youtube", "commented", video_url)
                        _log(
                            WORKER,
                            f"✅ YouTube comment posted on video {video_id} for '{plugin['name']}'",
                            "success",
                        )
                    except PWTimeout:
                        _log(WORKER, f"Timeout on YouTube video page: {video_url}", "error")
                    except Exception as exc:
                        _log(WORKER, f"YouTube comment error: {exc}", "error")
                    finally:
                        await page.close()

                except Exception as exc:
                    _log(WORKER, f"Unhandled error: {exc}", "error")

                for _ in range(INTERVAL_YOUTUBE):
                    if stop_event.is_set():
                        break
                    await asyncio.sleep(1)

        await browser.close()

    _log(WORKER, "Worker stopped cleanly.", "info")



# ===========================================================================
# WORKER 4 — Pingback Engine
# ===========================================================================

async def worker_pingback_engine(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    """
    Worker 4: Pingback Engine
    ──────────────────────────
    Cycle:
      1. Iterate over PINGBACK_COMPETITOR_BLOGS.
      2. For each target blog, attempt to discover its XML-RPC endpoint.
      3. Send a standard WordPress pingback via xmlrpc.client containing
         the plugin's shortlink as the source URL.
      4. Log result and increment pingbacks_sent counter.

    How WordPress Pingbacks work:
      - The source URL (our plugin link) claims to link to the target post.
      - WordPress verifies the link, then shows a backlink in the comments.
      - This builds SEO backlinks and drives referral traffic.

    NOTE: xmlrpc.client is synchronous, so we run it in a thread executor
    to avoid blocking the asyncio event loop.
    """
    WORKER = "Worker_Pingback_Engine"
    _log(WORKER, "Worker started.", "info")

    loop = asyncio.get_event_loop()

    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            try:
                plugins = db.get_all_plugins()
                if not plugins:
                    _log(WORKER, "No plugins configured. Waiting...", "info")
                    await asyncio.sleep(30)
                    continue

                # Cycle through all competitor blogs each iteration
                for target_url in PINGBACK_COMPETITOR_BLOGS:
                    if stop_event.is_set():
                        break

                    plugin = random.choice(plugins)
                    source_url = plugin["shortlink"]

                    _log(WORKER, f"Sending pingback → {target_url}", "info")

                    # Discover XML-RPC endpoint (WordPress default: /xmlrpc.php)
                    xmlrpc_url = _discover_xmlrpc_endpoint(target_url)

                    # Run synchronous xmlrpc call in thread pool
                    success = await loop.run_in_executor(
                        None,
                        _send_pingback,
                        xmlrpc_url,
                        source_url,
                        target_url,
                    )

                    if success:
                        db.increment_metric("pingbacks_sent")
                        db.record_plugin_action(plugin["id"], "pingback", "sent", target_url)
                        _log(
                            WORKER,
                            f"✅ Pingback sent: {source_url} → {target_url}",
                            "success",
                        )
                    else:
                        _log(WORKER, f"Pingback failed for {target_url}", "error")

                    await asyncio.sleep(5)   # brief pause between pings

            except Exception as exc:
                _log(WORKER, f"Unhandled error: {exc}", "error")

            for _ in range(INTERVAL_PINGBACK):
                if stop_event.is_set():
                    break
                await asyncio.sleep(1)

    _log(WORKER, "Worker stopped cleanly.", "info")


def _discover_xmlrpc_endpoint(target_url: str) -> str:
    """
    Attempt to build the XML-RPC endpoint URL for a WordPress site.
    Most WordPress blogs use /xmlrpc.php at their root.
    """
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(target_url)
    # Rebuild URL with only scheme + netloc + /xmlrpc.php
    xmlrpc_url = urlunparse((parsed.scheme, parsed.netloc, "/xmlrpc.php", "", "", ""))
    return xmlrpc_url


def _send_pingback(xmlrpc_url: str, source_url: str, target_url: str) -> bool:
    """
    Synchronous pingback sender using xmlrpc.client.
    Runs in a thread executor to avoid blocking asyncio.

    WordPress pingback spec:
        pingback.ping(sourceURI, targetURI)
        sourceURI  — the page that contains the link (our plugin shortlink)
        targetURI  — the page being linked to (competitor post)
    """
    try:
        proxy = xmlrpc.client.ServerProxy(xmlrpc_url, allow_none=True)
        result = proxy.pingback.ping(source_url, target_url)
        logger.debug("Pingback result: %s", result)
        return True
    except xmlrpc.client.Fault as fault:
        # Fault code 48 = already pinged (acceptable)
        if fault.faultCode == 48:
            logger.debug("Already pinged %s (code 48).", target_url)
            return True
        logger.warning("Pingback XML-RPC fault %d: %s", fault.faultCode, fault.faultString)
        return False
    except Exception as exc:
        logger.warning("Pingback error for %s: %s", xmlrpc_url, exc)
        return False



# ===========================================================================
# WORKER 5 — Reddit RSS Sniper
# ===========================================================================

async def worker_reddit_sniper(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    """
    Worker 5: Reddit RSS Sniper
    ────────────────────────────
    Cycle:
      1. Poll REDDIT_RSS_FEEDS for recent posts.
      2. Check each post title + body for REDDIT_TRIGGER_WORDS.
      3. If triggered, use Groq to generate a sympathetic, helpful reply
         that promotes the most relevant plugin.
      4. Post the reply via Reddit API or Playwright.
         NOTE: Reddit requires OAuth2 for API posting.
         A PRAW (Python Reddit API Wrapper) integration is recommended.
         Playwright fallback is included for browser-based posting.

    RSS feed approach:
      - feedparser reads subreddit RSS without authentication.
      - We track seen post IDs in a local set to avoid duplicate replies.

    Authentication options:
      A) Reddit API (PRAW) — most reliable. Add praw to requirements.txt
         and configure client_id, client_secret, username, password.
      B) Playwright browser session with saved cookies.
    """
    WORKER = "Worker_Reddit_Sniper"
    _log(WORKER, "Worker started.", "info")

    # Track already-processed post IDs to avoid duplicate replies
    seen_post_ids: set[str] = set()

    loop = asyncio.get_event_loop()

    while not stop_event.is_set():
        try:
            plugins = db.get_all_plugins()
            if not plugins:
                _log(WORKER, "No plugins configured. Waiting...", "info")
                await asyncio.sleep(30)
                continue

            for feed_url in REDDIT_RSS_FEEDS:
                if stop_event.is_set():
                    break

                _log(WORKER, f"Polling RSS: {feed_url}", "info")

                # feedparser is synchronous — run in executor
                feed = await loop.run_in_executor(
                    None, feedparser.parse, feed_url
                )

                for entry in feed.entries[:10]:   # check latest 10 posts
                    if stop_event.is_set():
                        break

                    post_id    = entry.get("id", entry.get("link", ""))
                    post_title = entry.get("title", "")
                    post_body  = BeautifulSoup(
                        entry.get("summary", ""), "lxml"
                    ).get_text(strip=True)

                    # Skip already-seen posts
                    if post_id in seen_post_ids:
                        continue

                    # --- Trigger word detection -----------------------------
                    combined_text = (post_title + " " + post_body).lower()
                    matched_triggers = [
                        w for w in REDDIT_TRIGGER_WORDS if w in combined_text
                    ]

                    if not matched_triggers:
                        seen_post_ids.add(post_id)
                        continue

                    _log(
                        WORKER,
                        f"Trigger words {matched_triggers} found in: '{post_title[:60]}'",
                        "info",
                    )

                    # --- Groq: select plugin + write reply ------------------
                    plugin, _ = await select_best_plugin_and_generate_copy(
                        rotator,
                        page_content=post_title + " " + post_body,
                        plugins=plugins,
                        copy_type="reddit",
                    )
                    reply_text = await build_reddit_reply(
                        rotator,
                        post_title=post_title,
                        post_snippet=post_body,
                        trigger_words=matched_triggers,
                        plugin=plugin,
                    )

                    # --- Post reply -----------------------------------------
                    post_url = entry.get("link", "")
                    posted = await _post_reddit_reply(post_url, reply_text)

                    if posted:
                        db.increment_metric("comments_posted")
                        db.record_plugin_action(plugin["id"], "reddit", "replied", post_url)
                        _log(
                            WORKER,
                            f"✅ Reddit reply posted on '{post_title[:50]}' for '{plugin['name']}'",
                            "success",
                        )
                    else:
                        _log(
                            WORKER,
                            f"Reddit reply posting not configured yet for: {post_url}",
                            "info",
                        )

                    # Mark as seen regardless of posting outcome
                    seen_post_ids.add(post_id)

                    # Limit memory usage — keep only last 1000 IDs
                    if len(seen_post_ids) > 1000:
                        seen_post_ids = set(list(seen_post_ids)[-500:])

                    await asyncio.sleep(3)   # brief pause between posts

        except Exception as exc:
            _log(WORKER, f"Unhandled error: {exc}", "error")

        for _ in range(INTERVAL_REDDIT):
            if stop_event.is_set():
                break
            await asyncio.sleep(1)

    _log(WORKER, "Worker stopped cleanly.", "info")


async def _post_reddit_reply(post_url: str, reply_text: str) -> bool:
    """
    Post a reply to a Reddit thread.

    Integration options (choose one and uncomment):

    OPTION A — PRAW (Reddit API):
        import praw
        reddit = praw.Reddit(
            client_id     = "YOUR_CLIENT_ID",        # TODO
            client_secret = "YOUR_CLIENT_SECRET",    # TODO
            username      = "YOUR_USERNAME",          # TODO
            password      = "YOUR_PASSWORD",          # TODO
            user_agent    = "MarketingBot/1.0",
        )
        submission = reddit.submission(url=post_url)
        submission.reply(reply_text)
        return True

    OPTION B — Playwright (browser session with cookies):
        # Requires saved Reddit cookies injected into browser context
        # async with async_playwright() as pw:
        #     browser = await pw.chromium.launch(headless=True)
        #     page = await browser.new_page()
        #     await page.context.add_cookies([...])  # TODO: inject cookies
        #     await page.goto(post_url)
        #     await page.click('.comment-area')      # TODO
        #     await page.fill('textarea', reply_text) # TODO
        #     await page.click('[data-click-id="text"]')  # TODO
        #     await browser.close()
        #     return True

    Currently returns False (dry-run) until authentication is configured.
    The reply text is logged so it can be verified before going live.
    """
    logger.info(
        "[Reddit Dry-Run] Would post to %s:\n%s", post_url, reply_text
    )
    # TODO: Uncomment one of the options above and remove this return False
    return False
