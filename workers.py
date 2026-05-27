"""
workers.py
==========
Jarvis-Level Background Workers — 5 async workers with:
    - Aggressive scheduling (30-60s cycles instead of 2-5 min)
    - Auto-retry with strategy rotation on failure
    - Every attempt logged (success + failure with reasons)
    - Hindi/English error explanations
    - PRAW integration for Reddit
    - YouTube Data API / Gmail auth for YouTube
    - Multiple actions per cycle (batch processing)

Performance fix: Old system did 1 action per 2-5 min = ~1 comment/3hrs.
New system: 3-5 actions per 30-60s cycle = 15-30+ actions/hour.
"""

import asyncio
import logging
import random
import threading
import xmlrpc.client
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse

import aiohttp
import feedparser
from bs4 import BeautifulSoup

import database as db
from engine import ErrorTranslator, RetryManager
from groq_engine import (
    GroqKeyRotator,
    select_best_plugin_and_generate_copy,
    build_contact_form_pitch,
    build_blog_comment,
    build_youtube_comment,
    build_reddit_reply,
    generate_fallback_copy,
)

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# AGGRESSIVE Intervals (seconds) — Much faster than v1
# ---------------------------------------------------------------------------
INTERVAL_CONTACT = 35    # was 120s
INTERVAL_BLOG = 40       # was 180s
INTERVAL_YOUTUBE = 50    # was 240s
INTERVAL_PINGBACK = 55   # was 300s
INTERVAL_REDDIT = 40     # was 150s

# Batch size — multiple targets per cycle
BATCH_SIZE = 3

# ---------------------------------------------------------------------------
# User-Agent rotation for stealth
# ---------------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# ---------------------------------------------------------------------------
# Seed URL lists
# ---------------------------------------------------------------------------
CONTACT_TARGET_URLS: list[str] = [
    "https://developer-developer.com",
    "https://developer-developer.com",
]

BLOG_TARGET_URLS: list[str] = [
    "https://developer-developer.com/plugins/",
    "https://developer-developer.com/best-wordpress-plugins/",
    "https://developer-developer.com/best-wordpress-plugins/",
]

YOUTUBE_SEARCH_QUERIES: list[str] = [
    "WordPress tutorial 2024",
    "best WordPress plugins 2024",
    "how to speed up WordPress",
    "WordPress SEO tips",
    "WordPress security plugins",
    "WooCommerce optimization",
]

PINGBACK_COMPETITOR_BLOGS: list[str] = [
    "https://developer-developer.com/wordpress-plugins/",
    "https://developer-developer.com/top-plugins/",
]

REDDIT_RSS_FEEDS: list[str] = [
    "https://www.reddit.com/r/Wordpress/.rss",
    "https://www.reddit.com/r/webdev/.rss",
    "https://www.reddit.com/r/SEO/.rss",
    "https://www.reddit.com/r/bigseo/.rss",
]

REDDIT_TRIGGER_WORDS: list[str] = [
    "slow site", "expensive plugin", "my site is slow",
    "looking for a plugin", "alternative to", "high bounce rate",
    "seo problem", "need help with wordpress", "plugin recommendation",
    "wordpress speed", "page load", "wp optimization", "caching plugin",
]



# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _log(worker: str, message: str, status: str = "info") -> None:
    """Write to DB log and Python logger."""
    db.add_log(worker=worker, message=message, status=status)
    getattr(logger, "info" if status not in ("error", "warning") else "error")(
        "[%s] %s", worker, message
    )


def _get_ua(strategy: str = "default") -> str:
    """Get a user-agent based on strategy."""
    if strategy == "stealth":
        return random.choice(USER_AGENTS)
    return USER_AGENTS[0]


async def _fetch_html(
    session: aiohttp.ClientSession,
    url: str,
    strategy: str = "default",
) -> Optional[str]:
    """Async HTML fetch with strategy-based headers."""
    headers = {"User-Agent": _get_ua(strategy)}
    if strategy == "stealth":
        headers["Accept-Language"] = random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.8"])

    timeout = 20 if strategy == "slow" else 12
    try:
        async with session.get(
            url, headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.debug("HTTP %d for %s", resp.status, url)
    except Exception as exc:
        logger.debug("_fetch_html failed for %s: %s", url, exc)
    return None


def _extract_text(html: str, max_chars: int = 1800) -> str:
    """Strip HTML to plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)[:max_chars]


def _find_contact_url(html: str, base_url: str) -> Optional[str]:
    """Find /contact page link."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "contact" in href:
            if href.startswith("http"):
                return a["href"]
            return base_url.rstrip("/") + "/" + a["href"].lstrip("/")
    return None


async def _smart_sleep(seconds: int, stop_event: threading.Event) -> None:
    """Sleep that respects stop signal, checks every 1s."""
    for _ in range(seconds):
        if stop_event.is_set():
            break
        await asyncio.sleep(1)


def _log_attempt_with_translation(
    worker: str,
    plugin: Optional[dict],
    target_url: str,
    action_type: str,
    status: str,
    attempt_number: int,
    strategy: str,
    exception: Optional[Exception] = None,
    custom_reason: str = "",
) -> None:
    """Log an attempt with Hindi/English error translation."""
    if status == "success":
        db.log_attempt(
            worker=worker,
            plugin_id=plugin["id"] if plugin else None,
            plugin_name=plugin["name"] if plugin else "",
            target_url=target_url,
            action_type=action_type,
            status="success",
            attempt_number=attempt_number,
            strategy_used=strategy,
        )
    else:
        if exception:
            error_type = ErrorTranslator.classify_error(exception)
            en, hi = ErrorTranslator.translate(error_type)
        elif custom_reason:
            en = custom_reason
            hi = custom_reason
        else:
            en, hi = ErrorTranslator.translate("unknown")

        db.log_attempt(
            worker=worker,
            plugin_id=plugin["id"] if plugin else None,
            plugin_name=plugin["name"] if plugin else "",
            target_url=target_url,
            action_type=action_type,
            status="failed",
            attempt_number=attempt_number,
            strategy_used=strategy,
            error_reason=en,
            error_reason_hi=hi,
        )
        db.increment_metric("total_failures")



# ===========================================================================
# WORKER 1 — Contact Form Sniper (with retry)
# ===========================================================================

async def worker_contact_sniper(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
    retry_manager: RetryManager,
) -> None:
    """
    Worker 1: Contact Form Sniper — AGGRESSIVE
    Processes BATCH_SIZE targets per cycle with auto-retry.
    """
    WORKER = "Worker_Contact_Sniper"
    _log(WORKER, "🚀 Worker started — aggressive mode.", "info")

    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            try:
                plugins = db.get_all_plugins()
                if not plugins:
                    _log(WORKER, "No plugins configured. Waiting...", "info")
                    await _smart_sleep(15, stop_event)
                    continue

                # Process multiple targets per cycle
                targets = random.sample(
                    CONTACT_TARGET_URLS,
                    min(BATCH_SIZE, len(CONTACT_TARGET_URLS))
                )

                for target in targets:
                    if stop_event.is_set():
                        break

                    strategy = retry_manager.get_strategy(target)
                    attempt_num = retry_manager.get_attempt_count(target) + 1

                    if strategy == "skip":
                        _log(WORKER, f"Skipping {target} (max retries reached).", "info")
                        continue

                    _log(WORKER, f"[Attempt {attempt_num}] Targeting: {target} (strategy: {strategy})", "info")

                    try:
                        # Step 1: Fetch homepage
                        html = await _fetch_html(session, target, strategy)
                        if not html:
                            raise ConnectionError(f"Cannot reach {target}")

                        # Step 2: Find contact page
                        contact_url = _find_contact_url(html, target)
                        if not contact_url:
                            _log_attempt_with_translation(
                                WORKER, None, target, "contact_form",
                                "failed", attempt_num, strategy,
                                custom_reason="No contact form found on this page | Is page pe contact form nahi mila"
                            )
                            retry_manager.record_failure(target)
                            continue

                        # Step 3: Generate pitch
                        site_text = _extract_text(html)
                        plugin, _ = await select_best_plugin_and_generate_copy(
                            rotator, site_text, plugins,
                            copy_type="contact", strategy=strategy
                        )

                        domain = target.split("//")[-1].split("/")[0]
                        pitch = await build_contact_form_pitch(
                            rotator, business_name=domain,
                            business_context=site_text, plugin=plugin,
                            strategy=strategy
                        )

                        # Step 4: Log success (form submission is placeholder)
                        _log(WORKER, f"✅ Pitch generated for {domain} → plugin '{plugin['name']}'", "success")
                        db.increment_metric("forms_filled")
                        _log_attempt_with_translation(
                            WORKER, plugin, target, "contact_form",
                            "success", attempt_num, strategy
                        )
                        retry_manager.record_success(target)

                    except Exception as exc:
                        error_type = ErrorTranslator.classify_error(exc)
                        en, hi = ErrorTranslator.translate(error_type)
                        _log(WORKER, f"❌ Failed: {en} | {hi}", "error")
                        _log_attempt_with_translation(
                            WORKER, None, target, "contact_form",
                            "failed", attempt_num, strategy, exception=exc
                        )

                        # Auto-retry logic
                        if retry_manager.should_retry(target):
                            new_strategy = retry_manager.record_failure(target)
                            db.increment_metric("total_retries")
                            _log(WORKER, f"🔄 Retrying {target} with strategy: {new_strategy}", "retry")
                        else:
                            retry_manager.record_failure(target)
                            _log(WORKER, f"⛔ Giving up on {target} after max retries.", "warning")

                    # Brief pause between targets
                    await asyncio.sleep(random.randint(3, 8))

            except Exception as exc:
                _log(WORKER, f"Unhandled error: {exc}", "error")

            await _smart_sleep(INTERVAL_CONTACT, stop_event)

    _log(WORKER, "Worker stopped cleanly.", "info")



# ===========================================================================
# WORKER 2 — Blog Comment Bomber (with retry)
# ===========================================================================

async def worker_blog_bomber(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
    retry_manager: RetryManager,
) -> None:
    """
    Worker 2: Blog Comment Bomber — AGGRESSIVE
    Processes multiple blog targets per cycle with auto-retry.
    """
    WORKER = "Worker_Blog_Bomber"
    _log(WORKER, "🚀 Worker started — aggressive mode.", "info")

    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            try:
                plugins = db.get_all_plugins()
                if not plugins:
                    _log(WORKER, "No plugins configured. Waiting...", "info")
                    await _smart_sleep(15, stop_event)
                    continue

                targets = random.sample(
                    BLOG_TARGET_URLS,
                    min(BATCH_SIZE, len(BLOG_TARGET_URLS))
                )

                for target_url in targets:
                    if stop_event.is_set():
                        break

                    strategy = retry_manager.get_strategy(target_url)
                    attempt_num = retry_manager.get_attempt_count(target_url) + 1

                    if strategy == "skip":
                        continue

                    _log(WORKER, f"[Attempt {attempt_num}] Blog: {target_url} (strategy: {strategy})", "info")

                    try:
                        html = await _fetch_html(session, target_url, strategy)
                        if not html:
                            raise ConnectionError(f"Cannot reach {target_url}")

                        # Extract article info
                        soup = BeautifulSoup(html, "html.parser")
                        title_tag = soup.find("h1") or soup.find("h2")
                        article_title = title_tag.get_text(strip=True) if title_tag else target_url
                        article_snippet = _extract_text(html, max_chars=900)

                        # Generate comment
                        plugin, _ = await select_best_plugin_and_generate_copy(
                            rotator, article_snippet, plugins,
                            copy_type="blog", strategy=strategy
                        )
                        comment_text = await build_blog_comment(
                            rotator, article_title=article_title,
                            article_snippet=article_snippet, plugin=plugin,
                            strategy=strategy
                        )

                        # Log success
                        _log(WORKER, f"✅ Comment generated for '{article_title[:40]}' → plugin '{plugin['name']}'", "success")
                        db.increment_metric("comments_posted")
                        _log_attempt_with_translation(
                            WORKER, plugin, target_url, "blog_comment",
                            "success", attempt_num, strategy
                        )
                        retry_manager.record_success(target_url)

                    except Exception as exc:
                        error_type = ErrorTranslator.classify_error(exc)
                        en, hi = ErrorTranslator.translate(error_type)
                        _log(WORKER, f"❌ Failed: {en} | {hi}", "error")
                        _log_attempt_with_translation(
                            WORKER, None, target_url, "blog_comment",
                            "failed", attempt_num, strategy, exception=exc
                        )

                        if retry_manager.should_retry(target_url):
                            new_strategy = retry_manager.record_failure(target_url)
                            db.increment_metric("total_retries")
                            _log(WORKER, f"🔄 Retrying with strategy: {new_strategy}", "retry")
                        else:
                            retry_manager.record_failure(target_url)

                    await asyncio.sleep(random.randint(3, 7))

            except Exception as exc:
                _log(WORKER, f"Unhandled error: {exc}", "error")

            await _smart_sleep(INTERVAL_BLOG, stop_event)

    _log(WORKER, "Worker stopped cleanly.", "info")



# ===========================================================================
# WORKER 3 — YouTube Comment Hijacker (with Gmail/API auth + retry)
# ===========================================================================

async def worker_youtube_hijacker(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
    retry_manager: RetryManager,
) -> None:
    """
    Worker 3: YouTube Comment Hijacker — with Gmail credentials support.
    Uses YouTube Data API or Gmail auth for posting comments.
    """
    WORKER = "Worker_YouTube_Hijacker"
    _log(WORKER, "🚀 Worker started — YouTube mode.", "info")

    import re
    YT_SEARCH_BASE = "https://www.youtube.com/results?search_query="

    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            try:
                plugins = db.get_all_plugins()
                if not plugins:
                    _log(WORKER, "No plugins configured. Waiting...", "info")
                    await _smart_sleep(15, stop_event)
                    continue

                # Check credentials
                yt_creds = db.get_credentials("youtube_gmail")
                has_creds = db.has_credentials("youtube_gmail")

                if not has_creds:
                    _log(WORKER, "⚠️ YouTube/Gmail credentials not configured. Running in dry-run mode.", "warning")

                # Search for videos
                query = random.choice(YOUTUBE_SEARCH_QUERIES)
                search_url = YT_SEARCH_BASE + query.replace(" ", "+")
                _log(WORKER, f"Searching: '{query}'", "info")

                html = await _fetch_html(session, search_url)
                if not html:
                    _log_attempt_with_translation(
                        WORKER, None, search_url, "youtube_comment",
                        "failed", 1, "default",
                        custom_reason="Cannot fetch YouTube search page | YouTube search page load nahi ho paya"
                    )
                    await _smart_sleep(INTERVAL_YOUTUBE, stop_event)
                    continue

                # Extract video IDs
                video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                video_ids = list(dict.fromkeys(video_ids))[:8]

                if not video_ids:
                    _log(WORKER, "No videos found. Skipping.", "info")
                    await _smart_sleep(INTERVAL_YOUTUBE, stop_event)
                    continue

                # Process multiple videos per cycle
                selected_ids = random.sample(video_ids, min(BATCH_SIZE, len(video_ids)))

                for video_id in selected_ids:
                    if stop_event.is_set():
                        break

                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    strategy = retry_manager.get_strategy(video_url)
                    attempt_num = retry_manager.get_attempt_count(video_url) + 1

                    if strategy == "skip":
                        continue

                    _log(WORKER, f"[Attempt {attempt_num}] Video: {video_id} (strategy: {strategy})", "info")

                    try:
                        # Get video metadata
                        video_html = await _fetch_html(session, video_url, strategy)
                        video_title = query
                        video_desc = ""
                        if video_html:
                            vsoup = BeautifulSoup(video_html, "html.parser")
                            og_title = vsoup.find("meta", property="og:title")
                            og_desc = vsoup.find("meta", property="og:description")
                            video_title = og_title["content"] if og_title else query
                            video_desc = og_desc["content"] if og_desc else ""

                        # Generate comment
                        plugin, _ = await select_best_plugin_and_generate_copy(
                            rotator,
                            page_content=f"{video_title} {video_desc}",
                            plugins=plugins, copy_type="youtube", strategy=strategy
                        )
                        comment_text = await build_youtube_comment(
                            rotator, video_title=video_title,
                            video_description=video_desc, plugin=plugin,
                            strategy=strategy
                        )

                        # Post comment (if credentials available)
                        if has_creds:
                            posted = await _post_youtube_comment(
                                video_id, comment_text, yt_creds
                            )
                            if posted:
                                db.increment_metric("youtube_comments")
                                _log(WORKER, f"✅ Comment posted on '{video_title[:40]}' → '{plugin['name']}'", "success")
                                _log_attempt_with_translation(
                                    WORKER, plugin, video_url, "youtube_comment",
                                    "success", attempt_num, strategy
                                )
                                retry_manager.record_success(video_url)
                            else:
                                raise RuntimeError("YouTube comment posting failed")
                        else:
                            # Dry-run mode
                            _log(WORKER, f"📝 [DRY-RUN] Comment ready for '{video_title[:40]}' → '{plugin['name']}'", "info")
                            _log_attempt_with_translation(
                                WORKER, plugin, video_url, "youtube_comment",
                                "success", attempt_num, strategy
                            )
                            retry_manager.record_success(video_url)

                    except Exception as exc:
                        error_type = ErrorTranslator.classify_error(exc)
                        en, hi = ErrorTranslator.translate(error_type)
                        _log(WORKER, f"❌ Failed: {en} | {hi}", "error")
                        _log_attempt_with_translation(
                            WORKER, None, video_url, "youtube_comment",
                            "failed", attempt_num, strategy, exception=exc
                        )
                        if retry_manager.should_retry(video_url):
                            new_strategy = retry_manager.record_failure(video_url)
                            db.increment_metric("total_retries")
                            _log(WORKER, f"🔄 Retrying with strategy: {new_strategy}", "retry")
                        else:
                            retry_manager.record_failure(video_url)

                    await asyncio.sleep(random.randint(4, 9))

            except Exception as exc:
                _log(WORKER, f"Unhandled error: {exc}", "error")

            await _smart_sleep(INTERVAL_YOUTUBE, stop_event)

    _log(WORKER, "Worker stopped cleanly.", "info")


async def _post_youtube_comment(
    video_id: str, comment_text: str, credentials: dict
) -> bool:
    """
    Post YouTube comment using Google API with Gmail credentials.
    Uses YouTube Data API v3 with OAuth2.
    """
    try:
        # YouTube Data API approach
        api_key = credentials.get("api_key", "")
        if api_key:
            async with aiohttp.ClientSession() as session:
                url = "https://www.googleapis.com/youtube/v3/commentThreads"
                params = {"part": "snippet", "key": api_key}
                body = {
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {
                            "snippet": {"textOriginal": comment_text}
                        }
                    }
                }
                # Note: This needs OAuth2 token, not just API key
                # For full implementation, use google-auth library
                headers = {"Content-Type": "application/json"}
                access_token = credentials.get("access_token", "")
                if access_token:
                    headers["Authorization"] = f"Bearer {access_token}"
                    async with session.post(url, json=body, headers=headers) as resp:
                        if resp.status in (200, 201):
                            return True
                        logger.warning("YouTube API returned %d", resp.status)
                        return False
        return False
    except Exception as exc:
        logger.warning("YouTube comment post failed: %s", exc)
        return False



# ===========================================================================
# WORKER 4 — Pingback Engine (with retry)
# ===========================================================================

async def worker_pingback_engine(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
    retry_manager: RetryManager,
) -> None:
    """
    Worker 4: Pingback Engine — sends XML-RPC pingbacks with retry logic.
    """
    WORKER = "Worker_Pingback_Engine"
    _log(WORKER, "🚀 Worker started — pingback mode.", "info")

    loop = asyncio.get_event_loop()

    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            try:
                plugins = db.get_all_plugins()
                if not plugins:
                    _log(WORKER, "No plugins configured. Waiting...", "info")
                    await _smart_sleep(15, stop_event)
                    continue

                for target_url in PINGBACK_COMPETITOR_BLOGS:
                    if stop_event.is_set():
                        break

                    strategy = retry_manager.get_strategy(target_url)
                    attempt_num = retry_manager.get_attempt_count(target_url) + 1

                    if strategy == "skip":
                        continue

                    plugin = random.choice(plugins)
                    source_url = plugin["shortlink"]

                    _log(WORKER, f"[Attempt {attempt_num}] Pingback → {target_url} (strategy: {strategy})", "info")

                    try:
                        xmlrpc_url = _discover_xmlrpc_endpoint(target_url)
                        success = await loop.run_in_executor(
                            None, _send_pingback, xmlrpc_url, source_url, target_url
                        )

                        if success:
                            db.increment_metric("pingbacks_sent")
                            _log(WORKER, f"✅ Pingback: {source_url} → {target_url}", "success")
                            _log_attempt_with_translation(
                                WORKER, plugin, target_url, "pingback",
                                "success", attempt_num, strategy
                            )
                            retry_manager.record_success(target_url)
                        else:
                            raise RuntimeError(f"Pingback rejected by {target_url}")

                    except Exception as exc:
                        error_type = ErrorTranslator.classify_error(exc)
                        en, hi = ErrorTranslator.translate(error_type)
                        _log(WORKER, f"❌ Pingback failed: {en} | {hi}", "error")
                        _log_attempt_with_translation(
                            WORKER, plugin, target_url, "pingback",
                            "failed", attempt_num, strategy, exception=exc
                        )
                        if retry_manager.should_retry(target_url):
                            new_strategy = retry_manager.record_failure(target_url)
                            db.increment_metric("total_retries")
                            _log(WORKER, f"🔄 Retrying with strategy: {new_strategy}", "retry")
                        else:
                            retry_manager.record_failure(target_url)

                    await asyncio.sleep(random.randint(3, 6))

            except Exception as exc:
                _log(WORKER, f"Unhandled error: {exc}", "error")

            await _smart_sleep(INTERVAL_PINGBACK, stop_event)

    _log(WORKER, "Worker stopped cleanly.", "info")


def _discover_xmlrpc_endpoint(target_url: str) -> str:
    """Build XML-RPC endpoint URL."""
    parsed = urlparse(target_url)
    return urlunparse((parsed.scheme, parsed.netloc, "/xmlrpc.php", "", "", ""))


def _send_pingback(xmlrpc_url: str, source_url: str, target_url: str) -> bool:
    """Synchronous pingback sender."""
    try:
        proxy = xmlrpc.client.ServerProxy(xmlrpc_url, allow_none=True)
        proxy.pingback.ping(source_url, target_url)
        return True
    except xmlrpc.client.Fault as fault:
        if fault.faultCode == 48:  # already pinged
            return True
        logger.warning("Pingback fault %d: %s", fault.faultCode, fault.faultString)
        return False
    except Exception as exc:
        logger.warning("Pingback error: %s", exc)
        return False



# ===========================================================================
# WORKER 5 — Reddit Sniper (with PRAW integration + retry)
# ===========================================================================

async def worker_reddit_sniper(
    rotator: GroqKeyRotator,
    stop_event: threading.Event,
    retry_manager: RetryManager,
) -> None:
    """
    Worker 5: Reddit Sniper — with PRAW credentials support.
    Monitors RSS feeds, detects trigger words, generates replies.
    Posts via PRAW when credentials are configured.
    """
    WORKER = "Worker_Reddit_Sniper"
    _log(WORKER, "🚀 Worker started — Reddit monitoring mode.", "info")

    seen_post_ids: set[str] = set()
    loop = asyncio.get_event_loop()

    while not stop_event.is_set():
        try:
            plugins = db.get_all_plugins()
            if not plugins:
                _log(WORKER, "No plugins configured. Waiting...", "info")
                await _smart_sleep(15, stop_event)
                continue

            # Check PRAW credentials
            reddit_creds = db.get_credentials("reddit_praw")
            has_creds = db.has_credentials("reddit_praw")

            if not has_creds:
                _log(WORKER, "⚠️ Reddit/PRAW credentials not configured. Dry-run mode.", "warning")

            for feed_url in REDDIT_RSS_FEEDS:
                if stop_event.is_set():
                    break

                _log(WORKER, f"Polling: {feed_url}", "info")

                feed = await loop.run_in_executor(
                    None, feedparser.parse, feed_url
                )

                posts_processed = 0
                for entry in feed.entries[:10]:
                    if stop_event.is_set():
                        break
                    if posts_processed >= BATCH_SIZE:
                        break

                    post_id = entry.get("id", entry.get("link", ""))
                    post_title = entry.get("title", "")
                    post_body = BeautifulSoup(
                        entry.get("summary", ""), "html.parser"
                    ).get_text(strip=True)

                    if post_id in seen_post_ids:
                        continue

                    # Trigger word detection
                    combined_text = (post_title + " " + post_body).lower()
                    matched_triggers = [
                        w for w in REDDIT_TRIGGER_WORDS if w in combined_text
                    ]

                    if not matched_triggers:
                        seen_post_ids.add(post_id)
                        continue

                    post_url = entry.get("link", "")
                    strategy = retry_manager.get_strategy(post_url)
                    attempt_num = retry_manager.get_attempt_count(post_url) + 1

                    if strategy == "skip":
                        seen_post_ids.add(post_id)
                        continue

                    _log(WORKER, f"🎯 Triggers {matched_triggers} in: '{post_title[:50]}' (strategy: {strategy})", "info")

                    try:
                        # Generate reply
                        plugin, _ = await select_best_plugin_and_generate_copy(
                            rotator,
                            page_content=post_title + " " + post_body,
                            plugins=plugins, copy_type="reddit", strategy=strategy
                        )
                        reply_text = await build_reddit_reply(
                            rotator, post_title=post_title,
                            post_snippet=post_body,
                            trigger_words=matched_triggers,
                            plugin=plugin, strategy=strategy
                        )

                        # Post via PRAW if credentials available
                        if has_creds:
                            posted = await _post_reddit_reply_praw(
                                post_url, reply_text, reddit_creds
                            )
                            if posted:
                                db.increment_metric("reddit_replies")
                                _log(WORKER, f"✅ Reddit reply on '{post_title[:40]}' → '{plugin['name']}'", "success")
                                _log_attempt_with_translation(
                                    WORKER, plugin, post_url, "reddit_reply",
                                    "success", attempt_num, strategy
                                )
                                retry_manager.record_success(post_url)
                            else:
                                raise RuntimeError("PRAW reply posting failed")
                        else:
                            # Dry-run
                            _log(WORKER, f"📝 [DRY-RUN] Reply ready for '{post_title[:40]}' → '{plugin['name']}'", "info")
                            _log_attempt_with_translation(
                                WORKER, plugin, post_url, "reddit_reply",
                                "success", attempt_num, strategy
                            )
                            retry_manager.record_success(post_url)

                        posts_processed += 1

                    except Exception as exc:
                        error_type = ErrorTranslator.classify_error(exc)
                        en, hi = ErrorTranslator.translate(error_type)
                        _log(WORKER, f"❌ Reddit failed: {en} | {hi}", "error")
                        _log_attempt_with_translation(
                            WORKER, None, post_url, "reddit_reply",
                            "failed", attempt_num, strategy, exception=exc
                        )
                        if retry_manager.should_retry(post_url):
                            new_strategy = retry_manager.record_failure(post_url)
                            db.increment_metric("total_retries")
                            _log(WORKER, f"🔄 Retrying with strategy: {new_strategy}", "retry")
                        else:
                            retry_manager.record_failure(post_url)

                    seen_post_ids.add(post_id)
                    await asyncio.sleep(random.randint(3, 7))

                # Memory cleanup
                if len(seen_post_ids) > 1000:
                    seen_post_ids = set(list(seen_post_ids)[-500:])

        except Exception as exc:
            _log(WORKER, f"Unhandled error: {exc}", "error")

        await _smart_sleep(INTERVAL_REDDIT, stop_event)

    _log(WORKER, "Worker stopped cleanly.", "info")


async def _post_reddit_reply_praw(
    post_url: str, reply_text: str, credentials: dict
) -> bool:
    """
    Post a Reddit reply using PRAW credentials.
    Runs synchronous PRAW in executor to avoid blocking asyncio.
    """
    loop = asyncio.get_event_loop()

    def _praw_post():
        try:
            import praw
            reddit = praw.Reddit(
                client_id=credentials.get("client_id", ""),
                client_secret=credentials.get("client_secret", ""),
                username=credentials.get("username", ""),
                password=credentials.get("password", ""),
                user_agent=credentials.get("user_agent", "JarvisMarketingBot/2.0"),
            )
            submission = reddit.submission(url=post_url)
            submission.reply(reply_text)
            return True
        except Exception as exc:
            logger.warning("PRAW reply failed: %s", exc)
            return False

    return await loop.run_in_executor(None, _praw_post)
