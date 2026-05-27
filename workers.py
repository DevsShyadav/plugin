"""
workers.py — 5 async background workers
Each worker runs in an infinite loop, auto-restarts on browser crash.
Intervals are configurable — current settings optimized for active operation.
"""

import asyncio
import logging
import random
import threading
import xmlrpc.client
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
# Intervals between each worker cycle (seconds)
# ---------------------------------------------------------------------------
INTERVAL_CONTACT   = 45    # 45 sec
INTERVAL_BLOG      = 60    # 1 min
INTERVAL_YOUTUBE   = 90    # 90 sec
INTERVAL_PINGBACK  = 120   # 2 min
INTERVAL_REDDIT    = 60    # 1 min

# ---------------------------------------------------------------------------
# Target URLs
# ---------------------------------------------------------------------------
CONTACT_TARGET_URLS: list[str] = [
    "https://wpforms.com",
    "https://elementor.com",
    "https://themeisle.com",
    "https://wpbeginner.com",
    "https://wpmailster.com",
]

BLOG_TARGET_URLS: list[str] = [
    "https://wpbeginner.com/showcase/best-wordpress-plugins/",
    "https://kinsta.com/best-wordpress-plugins/",
    "https://www.wpexplorer.com/best-wordpress-plugins/",
    "https://www.elegantthemes.com/blog/wordpress/best-wordpress-plugins",
    "https://themeisle.com/blog/best-wordpress-plugins/",
]

YOUTUBE_SEARCH_QUERIES: list[str] = [
    "WordPress tutorial 2025",
    "best WordPress plugins 2025",
    "how to speed up WordPress website",
    "WordPress SEO tutorial",
    "WordPress for beginners 2025",
]

PINGBACK_COMPETITOR_BLOGS: list[str] = [
    "https://wpbeginner.com/plugins/",
    "https://kinsta.com/blog/wordpress-plugins/",
    "https://www.wpexplorer.com/wordpress-plugins-review/",
    "https://themeisle.com/blog/best-wordpress-plugins/",
]

REDDIT_RSS_FEEDS: list[str] = [
    "https://www.reddit.com/r/Wordpress/.rss",
    "https://www.reddit.com/r/webdev/.rss",
    "https://www.reddit.com/r/SEO/.rss",
    "https://www.reddit.com/r/web_design/.rss",
    "https://www.reddit.com/r/digital_marketing/.rss",
]

REDDIT_TRIGGER_WORDS: list[str] = [
    "slow site", "expensive plugin", "my site is slow",
    "looking for a plugin", "alternative to", "high bounce rate",
    "seo problem", "need help with wordpress", "plugin recommendation",
    "wordpress is slow", "page speed", "google pagespeed",
    "wordpress plugin help", "best plugin for", "which plugin",
]

# ---------------------------------------------------------------------------
# Playwright args — required for HF Spaces Docker container
# ---------------------------------------------------------------------------
PLAYWRIGHT_LAUNCH_ARGS: dict = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-zygote",
        "--single-process",
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
# Helpers
# ---------------------------------------------------------------------------

def _log(worker: str, message: str, status: str = "info") -> None:
    db.add_log(worker=worker, message=message, status=status)
    getattr(logger, "info" if status != "error" else "error")("[%s] %s", worker, message)


async def _fetch_html(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    headers = {"User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as exc:
        logger.debug("_fetch_html failed for %s: %s", url, exc)
    return None


def _extract_text(html: str, max_chars: int = 1500) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)[:max_chars]


def _find_contact_url(html: str, base_url: str) -> Optional[str]:
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
    WORKER = "Worker_Contact_Sniper"
    _log(WORKER, "Worker started.", "info")

    while not stop_event.is_set():
        try:
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

                            site_text = _extract_text(homepage_html)
                            plugin, _ = await select_best_plugin_and_generate_copy(
                                rotator, site_text, plugins, copy_type="contact"
                            )
                            domain = target.split("//")[-1].split("/")[0]
                            pitch = await build_contact_form_pitch(
                                rotator, business_name=domain,
                                business_context=site_text, plugin=plugin,
                            )
                            _log(WORKER, f"Generated pitch for '{plugin['name']}'", "info")

                            page = await browser.new_page()
                            try:
                                await page.goto(contact_url, timeout=20000)
                                await page.wait_for_load_state("networkidle", timeout=15000)
                                await page.fill('input[name="name"]', "Alex Johnson")
                                await page.fill('input[name="email"]', "alex@marketingpro.io")
                                await page.fill('textarea[name="message"]', pitch)
                                await page.click('button[type="submit"]')
                                await page.wait_for_timeout(3000)
                                db.increment_metric("forms_filled")
                                db.record_plugin_action(
                                    plugin["id"], "contact_form", "submitted",
                                    target_url=contact_url, generated_text=pitch, status="success",
                                )
                                _log(WORKER, f"✅ Form submitted at {contact_url} for '{plugin['name']}'", "success")
                            except PWTimeout:
                                _log(WORKER, f"Timeout on form at {contact_url}", "error")
                            except Exception as exc:
                                _log(WORKER, f"Form error: {exc}", "error")
                            finally:
                                await page.close()

                        except Exception as exc:
                            _log(WORKER, f"Cycle error: {exc}", "error")

                        await asyncio.sleep(INTERVAL_CONTACT)

                await browser.close()

        except Exception as exc:
            _log(WORKER, f"Browser crashed, restarting in 10s: {exc}", "error")
            await asyncio.sleep(10)

    _log(WORKER, "Worker stopped cleanly.", "info")


# ===========================================================================
# WORKER 2 — Blog Comment Bomber
# ===========================================================================

async def worker_blog_bomber(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    WORKER = "Worker_Blog_Bomber"
    _log(WORKER, "Worker started.", "info")

    while not stop_event.is_set():
        try:
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

                            soup = BeautifulSoup(html, "lxml")
                            title_tag = soup.find("h1") or soup.find("h2")
                            article_title = title_tag.get_text(strip=True) if title_tag else target_url
                            article_snippet = _extract_text(html, max_chars=800)

                            plugin, _ = await select_best_plugin_and_generate_copy(
                                rotator, article_snippet, plugins, copy_type="blog"
                            )
                            comment_text = await build_blog_comment(
                                rotator, article_title=article_title,
                                article_snippet=article_snippet, plugin=plugin,
                            )
                            _log(WORKER, f"Generated comment for '{plugin['name']}'", "info")

                            page = await browser.new_page()
                            try:
                                await page.goto(target_url, timeout=20000)
                                await page.wait_for_load_state("networkidle", timeout=15000)
                                await page.fill('#author', "Alex Johnson")
                                await page.fill('#email', "alex@marketingpro.io")
                                await page.fill('#comment', comment_text)
                                await page.click('#submit')
                                await page.wait_for_timeout(4000)
                                db.increment_metric("comments_posted")
                                db.record_plugin_action(
                                    plugin["id"], "blog_comment", "commented",
                                    target_url=target_url, generated_text=comment_text, status="success",
                                )
                                _log(WORKER, f"✅ Comment posted on {target_url} for '{plugin['name']}'", "success")
                            except PWTimeout:
                                _log(WORKER, f"Timeout loading {target_url}", "error")
                            except Exception as exc:
                                _log(WORKER, f"Comment error: {exc}", "error")
                            finally:
                                await page.close()

                        except Exception as exc:
                            _log(WORKER, f"Cycle error: {exc}", "error")

                        await asyncio.sleep(INTERVAL_BLOG)

                await browser.close()

        except Exception as exc:
            _log(WORKER, f"Browser crashed, restarting in 10s: {exc}", "error")
            await asyncio.sleep(10)

    _log(WORKER, "Worker stopped cleanly.", "info")


# ===========================================================================
# WORKER 3 — YouTube Comment Hijacker
# ===========================================================================

async def worker_youtube_hijacker(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    WORKER = "Worker_YouTube_Hijacker"
    _log(WORKER, "Worker started.", "info")

    YT_SEARCH_BASE = "https://www.youtube.com/results?search_query="

    while not stop_event.is_set():
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(**PLAYWRIGHT_LAUNCH_ARGS)
                async with aiohttp.ClientSession() as session:
                    while not stop_event.is_set():
                        try:
                            plugins = db.get_all_plugins()
                            if not plugins:
                                await asyncio.sleep(30)
                                continue

                            query = random.choice(YOUTUBE_SEARCH_QUERIES)
                            search_url = YT_SEARCH_BASE + query.replace(" ", "+")
                            _log(WORKER, f"Searching YouTube: '{query}'", "info")

                            html = await _fetch_html(session, search_url)
                            if not html:
                                _log(WORKER, "Could not fetch YouTube search page.", "error")
                                await asyncio.sleep(INTERVAL_YOUTUBE)
                                continue

                            import re
                            video_ids = list(dict.fromkeys(
                                re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                            ))[:5]

                            if not video_ids:
                                _log(WORKER, "No video IDs found. Skipping.", "info")
                                await asyncio.sleep(INTERVAL_YOUTUBE)
                                continue

                            video_id = random.choice(video_ids)
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            _log(WORKER, f"Targeting video: {video_url}", "info")

                            video_html = await _fetch_html(session, video_url)
                            video_title, video_desc = query, ""
                            if video_html:
                                vsoup = BeautifulSoup(video_html, "lxml")
                                og_t = vsoup.find("meta", property="og:title")
                                og_d = vsoup.find("meta", property="og:description")
                                if og_t: video_title = og_t["content"]
                                if og_d: video_desc  = og_d["content"]

                            plugin, _ = await select_best_plugin_and_generate_copy(
                                rotator, f"{video_title} {video_desc}", plugins, copy_type="youtube"
                            )
                            comment_text = await build_youtube_comment(
                                rotator, video_title=video_title,
                                video_description=video_desc, plugin=plugin,
                            )
                            _log(WORKER, f"Generated YT comment for '{plugin['name']}'", "info")

                            page = await browser.new_page()
                            try:
                                # TODO: inject cookies for auth
                                await page.goto(video_url, timeout=25000)
                                await page.wait_for_load_state("networkidle", timeout=20000)
                                await page.evaluate("window.scrollBy(0, 800)")
                                await page.wait_for_timeout(3000)
                                await page.click('#simplebox-placeholder')
                                await page.wait_for_timeout(1500)
                                await page.fill('#contenteditable-root', comment_text)
                                await page.wait_for_timeout(1000)
                                await page.click('#submit-button')
                                await page.wait_for_timeout(3000)
                                db.increment_metric("comments_posted")
                                db.record_plugin_action(
                                    plugin["id"], "youtube", "commented",
                                    target_url=video_url, generated_text=comment_text, status="success",
                                )
                                _log(WORKER, f"✅ YouTube comment posted on {video_id} for '{plugin['name']}'", "success")
                            except PWTimeout:
                                _log(WORKER, f"Timeout on YouTube: {video_url}", "error")
                            except Exception as exc:
                                _log(WORKER, f"YouTube comment error: {exc}", "error")
                            finally:
                                await page.close()

                        except Exception as exc:
                            _log(WORKER, f"Cycle error: {exc}", "error")

                        await asyncio.sleep(INTERVAL_YOUTUBE)

                await browser.close()

        except Exception as exc:
            _log(WORKER, f"Browser crashed, restarting in 10s: {exc}", "error")
            await asyncio.sleep(10)

    _log(WORKER, "Worker stopped cleanly.", "info")


# ===========================================================================
# WORKER 4 — Pingback Engine
# ===========================================================================

async def worker_pingback_engine(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
) -> None:
    WORKER = "Worker_Pingback_Engine"
    _log(WORKER, "Worker started.", "info")

    loop = asyncio.get_event_loop()

    while not stop_event.is_set():
        try:
            plugins = db.get_all_plugins()
            if not plugins:
                await asyncio.sleep(30)
                continue

            for target_url in PINGBACK_COMPETITOR_BLOGS:
                if stop_event.is_set():
                    break

                plugin = random.choice(plugins)
                source_url = plugin["shortlink"]
                _log(WORKER, f"Sending pingback → {target_url}", "info")

                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(target_url)
                xmlrpc_url = urlunparse((parsed.scheme, parsed.netloc, "/xmlrpc.php", "", "", ""))

                try:
                    success = await loop.run_in_executor(
                        None, _send_pingback, xmlrpc_url, source_url, target_url
                    )
                    if success:
                        db.increment_metric("pingbacks_sent")
                        db.record_plugin_action(
                            plugin["id"], "pingback", "sent",
                            target_url=target_url,
                            generated_text=f"Source: {source_url}",
                            status="success",
                        )
                        _log(WORKER, f"✅ Pingback sent: {source_url} → {target_url}", "success")
                    else:
                        _log(WORKER, f"Pingback failed for {target_url}", "error")
                except Exception as exc:
                    _log(WORKER, f"Pingback error: {exc}", "error")

                await asyncio.sleep(5)

        except Exception as exc:
            _log(WORKER, f"Cycle error: {exc}", "error")

        await asyncio.sleep(INTERVAL_PINGBACK)

    _log(WORKER, "Worker stopped cleanly.", "info")


def _send_pingback(xmlrpc_url: str, source_url: str, target_url: str) -> bool:
    try:
        proxy = xmlrpc.client.ServerProxy(xmlrpc_url, allow_none=True)
        proxy.pingback.ping(source_url, target_url)
        return True
    except xmlrpc.client.Fault as fault:
        if fault.faultCode == 48:
            return True  # Already pinged
        logger.warning("Pingback fault %d: %s", fault.faultCode, fault.faultString)
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
    WORKER = "Worker_Reddit_Sniper"
    _log(WORKER, "Worker started.", "info")

    seen_post_ids: set[str] = set()
    loop = asyncio.get_event_loop()

    while not stop_event.is_set():
        try:
            plugins = db.get_all_plugins()
            if not plugins:
                await asyncio.sleep(30)
                continue

            for feed_url in REDDIT_RSS_FEEDS:
                if stop_event.is_set():
                    break

                _log(WORKER, f"Polling RSS: {feed_url}", "info")

                try:
                    feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
                except Exception as exc:
                    _log(WORKER, f"RSS fetch error: {exc}", "error")
                    continue

                for entry in feed.entries[:10]:
                    if stop_event.is_set():
                        break

                    post_id    = entry.get("id", entry.get("link", ""))
                    post_title = entry.get("title", "")
                    post_body  = BeautifulSoup(
                        entry.get("summary", ""), "lxml"
                    ).get_text(strip=True)

                    if post_id in seen_post_ids:
                        continue

                    combined = (post_title + " " + post_body).lower()
                    matched  = [w for w in REDDIT_TRIGGER_WORDS if w in combined]

                    if not matched:
                        seen_post_ids.add(post_id)
                        continue

                    _log(WORKER, f"Trigger {matched} in: '{post_title[:60]}'", "info")

                    try:
                        plugin, _ = await select_best_plugin_and_generate_copy(
                            rotator, post_title + " " + post_body, plugins, copy_type="reddit"
                        )
                        reply_text = await build_reddit_reply(
                            rotator, post_title=post_title, post_snippet=post_body,
                            trigger_words=matched, plugin=plugin,
                        )

                        post_url = entry.get("link", "")
                        # Dry-run — saves to DB for manual review
                        db.record_plugin_action(
                            plugin["id"], "reddit", "generated",
                            target_url=post_url, generated_text=reply_text, status="dry_run",
                        )
                        _log(WORKER, f"📝 Reddit reply generated for: '{post_title[:50]}'", "info")

                    except Exception as exc:
                        _log(WORKER, f"Reply generation error: {exc}", "error")

                    seen_post_ids.add(post_id)

                    if len(seen_post_ids) > 1000:
                        seen_post_ids = set(list(seen_post_ids)[-500:])

                    await asyncio.sleep(2)

        except Exception as exc:
            _log(WORKER, f"Cycle error: {exc}", "error")

        await asyncio.sleep(INTERVAL_REDDIT)

    _log(WORKER, "Worker stopped cleanly.", "info")
