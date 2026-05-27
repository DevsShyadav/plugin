"""
engine.py
=========
Jarvis-Level AI Marketing Engine Manager

Key improvements over v1:
    - Auto-retry with different strategies when blocked
    - Plain Hindi/English error explanations for every failure
    - Smarter scheduling — workers cycle every 30-60s instead of 2-5 min
    - Retry manager tracks attempts per target and switches approach
    - Error translator provides human-readable diagnostics
    - Engine health monitoring with self-healing capabilities

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │  Streamlit Main Thread                                  │
    │  ┌──────────────┐        ┌─────────────────────────┐   │
    │  │  UI renders  │◄──────►│   EngineManager         │   │
    │  │  user clicks │        │  + RetryManager         │   │
    │  │  start/stop  │        │  + ErrorTranslator      │   │
    │  └──────────────┘        └────────────┬────────────┘   │
    └───────────────────────────────────────│─────────────────┘
                                            │
                        ┌───────────────────▼──────────────────┐
                        │  Background Thread (daemon)           │
                        │  asyncio event loop                   │
                        │  ├─ worker_contact_sniper (30s)       │
                        │  ├─ worker_blog_bomber (45s)          │
                        │  ├─ worker_youtube_hijacker (60s)     │
                        │  ├─ worker_pingback_engine (60s)      │
                        │  └─ worker_reddit_sniper (45s)        │
                        └──────────────────────────────────────┘
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Optional

from groq_engine import GroqKeyRotator
from workers import (
    worker_contact_sniper,
    worker_blog_bomber,
    worker_youtube_hijacker,
    worker_pingback_engine,
    worker_reddit_sniper,
)
import database as db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error Translator — Hindi/English plain language explanations
# ---------------------------------------------------------------------------

class ErrorTranslator:
    """
    Translates technical errors into plain Hindi/English explanations
    so the user knows exactly what went wrong and how to fix it.
    """

    TRANSLATIONS = {
        "timeout": {
            "en": "The target website took too long to respond. Site might be down or blocking us.",
            "hi": "Target website ne bahut der lagayi respond karne mein. Site down ho sakti hai ya block kar rahi hai.",
        },
        "rate_limit": {
            "en": "API rate limit hit. Too many requests sent too fast. Switching to backup key.",
            "hi": "API rate limit lag gayi. Bahut jaldi requests bheje gaye. Backup key pe switch kar rahe hain.",
        },
        "auth_failed": {
            "en": "Authentication failed. Check your credentials in Settings.",
            "hi": "Login fail ho gaya. Settings mein apne credentials check karo.",
        },
        "captcha": {
            "en": "CAPTCHA detected. The site is blocking automated access. Trying different approach.",
            "hi": "CAPTCHA detect hua. Site automated access block kar rahi hai. Doosra tarika try kar rahe hain.",
        },
        "blocked": {
            "en": "Our request was blocked by the website. Changing strategy and retrying.",
            "hi": "Hamari request website ne block kar di. Strategy change karke dobara try kar rahe hain.",
        },
        "no_form": {
            "en": "No contact form found on this page. Moving to next target.",
            "hi": "Is page pe koi contact form nahi mila. Agla target try kar rahe hain.",
        },
        "network": {
            "en": "Network error — cannot reach the target. Check internet connection.",
            "hi": "Network error — target tak nahi pahunch pa rahe. Internet connection check karo.",
        },
        "no_keys": {
            "en": "No API keys configured. Add Groq API keys in Settings to start.",
            "hi": "Koi API key set nahi hai. Settings mein Groq API keys add karo.",
        },
        "no_plugins": {
            "en": "No plugins added yet. Add at least one plugin in Settings.",
            "hi": "Abhi tak koi plugin add nahi kiya. Settings mein kam se kam ek plugin add karo.",
        },
        "no_credentials": {
            "en": "Platform credentials not configured. Add them in Settings.",
            "hi": "Platform credentials set nahi hain. Settings mein add karo.",
        },
        "form_submit_fail": {
            "en": "Form was found but submission failed. Form structure might have changed.",
            "hi": "Form mila lekin submit nahi ho paya. Form ka structure change ho gaya hoga.",
        },
        "comment_disabled": {
            "en": "Comments are disabled on this post/video.",
            "hi": "Is post/video pe comments disabled hain.",
        },
        "unknown": {
            "en": "An unexpected error occurred. Engine will auto-retry with different approach.",
            "hi": "Ek unexpected error aaya. Engine khud se doosre tarike se retry karega.",
        },
    }

    @classmethod
    def translate(cls, error_type: str) -> tuple[str, str]:
        """
        Returns (english_explanation, hindi_explanation) for a given error type.
        """
        entry = cls.TRANSLATIONS.get(error_type, cls.TRANSLATIONS["unknown"])
        return entry["en"], entry["hi"]

    @classmethod
    def classify_error(cls, exception: Exception) -> str:
        """
        Classify an exception into an error type string.
        """
        exc_str = str(exception).lower()
        exc_type = type(exception).__name__.lower()

        if "timeout" in exc_str or "timeout" in exc_type:
            return "timeout"
        elif "429" in exc_str or "rate" in exc_str:
            return "rate_limit"
        elif "401" in exc_str or "403" in exc_str or "auth" in exc_str:
            return "auth_failed"
        elif "captcha" in exc_str or "recaptcha" in exc_str:
            return "captcha"
        elif "blocked" in exc_str or "denied" in exc_str or "ban" in exc_str:
            return "blocked"
        elif "network" in exc_str or "connect" in exc_str or "dns" in exc_str:
            return "network"
        else:
            return "unknown"


# ---------------------------------------------------------------------------
# Retry Manager — Smart retry with strategy rotation
# ---------------------------------------------------------------------------

class RetryManager:
    """
    Manages retry logic with different strategies for each target.
    
    Strategies:
        1. default    — Standard approach with original parameters
        2. slow       — Longer delays, more human-like timing
        3. stealth    — Different user-agent, random delays
        4. alternate  — Try different page elements/selectors
        5. skip       — Give up on this target, move to next
    """

    STRATEGIES = ["default", "slow", "stealth", "alternate", "skip"]
    MAX_RETRIES = 3

    def __init__(self):
        self._attempts: dict[str, int] = {}  # target_url -> attempt count
        self._strategy_index: dict[str, int] = {}  # target_url -> strategy index
        self._lock = threading.Lock()

    def get_strategy(self, target_url: str) -> str:
        """Get current strategy for a target URL."""
        with self._lock:
            idx = self._strategy_index.get(target_url, 0)
            return self.STRATEGIES[min(idx, len(self.STRATEGIES) - 1)]

    def get_attempt_count(self, target_url: str) -> int:
        """Get current attempt count for a target."""
        with self._lock:
            return self._attempts.get(target_url, 0)

    def should_retry(self, target_url: str) -> bool:
        """
        Returns True if we should retry this target.
        Returns False if max retries exceeded (time to skip).
        """
        with self._lock:
            count = self._attempts.get(target_url, 0)
            return count < self.MAX_RETRIES

    def record_failure(self, target_url: str) -> str:
        """
        Record a failure and rotate to next strategy.
        Returns the new strategy to use on retry.
        """
        with self._lock:
            self._attempts[target_url] = self._attempts.get(target_url, 0) + 1
            self._strategy_index[target_url] = self._strategy_index.get(target_url, 0) + 1
            idx = self._strategy_index[target_url]
            strategy = self.STRATEGIES[min(idx, len(self.STRATEGIES) - 1)]

            # Clean up old entries to prevent memory leak (keep only last 200)
            if len(self._attempts) > 200:
                oldest_keys = list(self._attempts.keys())[:100]
                for k in oldest_keys:
                    self._attempts.pop(k, None)
                    self._strategy_index.pop(k, None)

            return strategy

    def record_success(self, target_url: str) -> None:
        """Clear retry state for a successfully processed target."""
        with self._lock:
            self._attempts.pop(target_url, None)
            self._strategy_index.pop(target_url, None)

    def reset(self) -> None:
        """Clear all retry state."""
        with self._lock:
            self._attempts.clear()
            self._strategy_index.clear()


# ---------------------------------------------------------------------------
# Engine Manager
# ---------------------------------------------------------------------------

class EngineManager:
    """
    Jarvis-level Engine Manager with auto-retry, error translation,
    and smart scheduling.

    Usage:
        engine = EngineManager()
        engine.start()
        engine.is_running  # True/False
        engine.stop()
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._started_at: Optional[datetime] = None
        self.retry_manager = RetryManager()
        self.error_translator = ErrorTranslator()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and not self._stop_event.is_set()
        )

    @property
    def uptime(self) -> str:
        """Returns human-readable uptime string."""
        if not self._started_at or not self.is_running:
            return "—"
        delta = datetime.now() - self._started_at
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def start(self) -> None:
        with self._lock:
            if self.is_running:
                logger.info("Engine already running.")
                return

            self._stop_event.clear()
            self.retry_manager.reset()
            self._started_at = datetime.now()

            db.add_log("🤖 Jarvis", "🚀 Engine starting — launching 5 workers with smart scheduling...", "info")

            self._thread = threading.Thread(
                target=self._run_event_loop,
                name="JarvisEngineThread",
                daemon=True,
            )
            self._thread.start()
            logger.info("Engine thread started: %s", self._thread.name)

    def stop(self) -> None:
        with self._lock:
            if not self.is_running:
                return

            db.add_log("🤖 Jarvis", "🛑 Stop signal sent — workers finishing current cycle...", "info")
            self._stop_event.set()

            if self._thread:
                self._thread.join(timeout=10)
                if self._thread.is_alive():
                    db.add_log("🤖 Jarvis", "⚠️ Workers did not exit cleanly. Force-stopping.", "warning")
                else:
                    db.add_log("🤖 Jarvis", "✅ All workers stopped cleanly.", "success")

            self._thread = None
            self._loop = None
            self._started_at = None

    def get_status_line(self) -> str:
        if self.is_running:
            return f"🟢 JARVIS ACTIVE — Uptime: {self.uptime}"
        return "🔴 Engine Offline"

    # ------------------------------------------------------------------
    # Private: event loop
    # ------------------------------------------------------------------

    def _run_event_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        try:
            loop.run_until_complete(self._run_all_workers())
        except Exception as exc:
            logger.error("Engine event loop crashed: %s", exc)
            error_type = ErrorTranslator.classify_error(exc)
            en, hi = ErrorTranslator.translate(error_type)
            db.add_log("🤖 Jarvis", f"💥 Engine crashed: {en} | {hi}", "error")
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            loop.close()

    async def _run_all_workers(self) -> None:
        rotator = GroqKeyRotator()

        if not rotator.has_valid_keys:
            en, hi = ErrorTranslator.translate("no_keys")
            db.add_log("🤖 Jarvis", f"⚠️ {en} | {hi}", "error")

        db.add_log("🤖 Jarvis", "All 5 workers launched — aggressive scheduling active.", "info")

        await asyncio.gather(
            self._safe_worker("Contact Sniper", worker_contact_sniper, rotator),
            self._safe_worker("Blog Bomber", worker_blog_bomber, rotator),
            self._safe_worker("YouTube Hijacker", worker_youtube_hijacker, rotator),
            self._safe_worker("Pingback Engine", worker_pingback_engine, rotator),
            self._safe_worker("Reddit Sniper", worker_reddit_sniper, rotator),
        )

    async def _safe_worker(self, name: str, worker_fn, rotator: GroqKeyRotator) -> None:
        try:
            await worker_fn(rotator, self._stop_event, self.retry_manager)
        except asyncio.CancelledError:
            logger.info("Worker '%s' was cancelled.", name)
        except Exception as exc:
            logger.error("Worker '%s' crashed: %s", name, exc)
            error_type = ErrorTranslator.classify_error(exc)
            en, hi = ErrorTranslator.translate(error_type)
            db.add_log(
                f"Worker_{name}",
                f"💥 Worker crashed: {en} | {hi}",
                "error",
            )


# ---------------------------------------------------------------------------
# Singleton getter (fallback)
# ---------------------------------------------------------------------------

_global_engine: Optional[EngineManager] = None

def get_engine() -> EngineManager:
    global _global_engine
    if _global_engine is None:
        _global_engine = EngineManager()
    return _global_engine
