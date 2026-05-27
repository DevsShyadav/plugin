"""
engine.py
=========
The asyncio Engine Manager — the bridge between Streamlit's main thread
and the 5 background async workers.

KEY FIX: Engine uses a module-level global singleton so it survives
Streamlit session reloads. When HF Space auto-refreshes or a new browser
tab opens, the workers keep running — only a deliberate Stop button
will shut them down.
"""

import asyncio
import logging
import threading
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
# Module-level global — survives Streamlit re-runs and session resets
# ---------------------------------------------------------------------------
_GLOBAL_THREAD: Optional[threading.Thread] = None
_GLOBAL_STOP_EVENT: threading.Event = threading.Event()
_GLOBAL_LOCK: threading.Lock = threading.Lock()


class EngineManager:
    """
    Manages the lifecycle of the background asyncio worker pool.
    Uses module-level globals so the engine keeps running even when
    Streamlit re-runs the script (e.g. on auto-refresh).
    """

    @property
    def is_running(self) -> bool:
        """True if the background thread is alive and workers are active."""
        global _GLOBAL_THREAD, _GLOBAL_STOP_EVENT
        return (
            _GLOBAL_THREAD is not None
            and _GLOBAL_THREAD.is_alive()
            and not _GLOBAL_STOP_EVENT.is_set()
        )

    def start(self) -> None:
        global _GLOBAL_THREAD, _GLOBAL_STOP_EVENT

        with _GLOBAL_LOCK:
            if self.is_running:
                return

            # Reset stop signal
            _GLOBAL_STOP_EVENT.clear()

            db.add_log("Engine", "🚀 Engine starting — spawning 5 workers...", "info")

            _GLOBAL_THREAD = threading.Thread(
                target=self._run_event_loop,
                name="WorkerEngineThread",
                daemon=True,
            )
            _GLOBAL_THREAD.start()
            logger.info("Engine thread started.")

    def stop(self) -> None:
        global _GLOBAL_THREAD, _GLOBAL_STOP_EVENT

        with _GLOBAL_LOCK:
            if not self.is_running:
                return

            db.add_log("Engine", "🛑 Stop signal sent — workers winding down...", "info")
            _GLOBAL_STOP_EVENT.set()

            if _GLOBAL_THREAD:
                _GLOBAL_THREAD.join(timeout=15)
                if not _GLOBAL_THREAD.is_alive():
                    db.add_log("Engine", "✅ All workers stopped cleanly.", "success")
                else:
                    db.add_log("Engine", "⚠️ Workers did not exit cleanly.", "error")

            _GLOBAL_THREAD = None

    def get_status_line(self) -> str:
        if self.is_running:
            return "🟢 Engine Running — Workers Active"
        return "🔴 Engine Stopped"

    def _run_event_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_all_workers())
        except Exception as exc:
            logger.error("Engine event loop crashed: %s", exc)
            db.add_log("Engine", f"💥 Engine crashed: {exc}", "error")
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
        global _GLOBAL_STOP_EVENT

        rotator = GroqKeyRotator()

        if not rotator.has_valid_keys:
            db.add_log(
                "Engine",
                "⚠️ No Groq API keys found. Add keys in Settings before starting.",
                "error",
            )

        db.add_log("Engine", "All 5 workers launched concurrently.", "info")

        await asyncio.gather(
            self._safe_worker("Contact Sniper",   worker_contact_sniper,   rotator),
            self._safe_worker("Blog Bomber",      worker_blog_bomber,      rotator),
            self._safe_worker("YouTube Hijacker", worker_youtube_hijacker, rotator),
            self._safe_worker("Pingback Engine",  worker_pingback_engine,  rotator),
            self._safe_worker("Reddit Sniper",    worker_reddit_sniper,    rotator),
        )

    async def _safe_worker(self, name: str, worker_fn, rotator: GroqKeyRotator) -> None:
        try:
            await worker_fn(rotator, _GLOBAL_STOP_EVENT)
        except asyncio.CancelledError:
            logger.info("Worker '%s' cancelled.", name)
        except Exception as exc:
            logger.error("Worker '%s' crashed: %s", name, exc)
            db.add_log(f"Worker_{name}", f"💥 Worker crashed: {exc}", "error")


# ---------------------------------------------------------------------------
# Singleton — always returns the same instance
# ---------------------------------------------------------------------------
_ENGINE_INSTANCE: Optional[EngineManager] = None


def get_engine() -> EngineManager:
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        _ENGINE_INSTANCE = EngineManager()
    return _ENGINE_INSTANCE
