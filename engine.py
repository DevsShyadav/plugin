"""
engine.py
=========
The asyncio Engine Manager — the bridge between Streamlit's main thread
and the 5 background async workers.

THE CORE PROBLEM:
    Streamlit runs in its own thread and does NOT have a running asyncio
    event loop. The workers are all async coroutines. We cannot simply call
    asyncio.run() from Streamlit because:
      a) It blocks the UI thread entirely.
      b) A new event loop can't be started inside an already-running loop.

THE SOLUTION — Dedicated Background Thread + Persistent Event Loop:
    ┌─────────────────────────────────────────────────────────┐
    │  Streamlit Main Thread                                  │
    │  ┌──────────────┐        ┌─────────────────────────┐   │
    │  │  UI renders  │◄──────►│   EngineManager         │   │
    │  │  user clicks │        │  (singleton in session  │   │
    │  │  start/stop  │        │   state)                │   │
    │  └──────────────┘        └────────────┬────────────┘   │
    └───────────────────────────────────────│─────────────────┘
                                            │ start() / stop()
                        ┌───────────────────▼──────────────────┐
                        │  Background Thread (daemon)           │
                        │  ┌────────────────────────────────┐  │
                        │  │  asyncio event loop (forever)  │  │
                        │  │  ├─ worker_contact_sniper()    │  │
                        │  │  ├─ worker_blog_bomber()       │  │
                        │  │  ├─ worker_youtube_hijacker()  │  │
                        │  │  ├─ worker_pingback_engine()   │  │
                        │  │  └─ worker_reddit_sniper()     │  │
                        │  └────────────────────────────────┘  │
                        └──────────────────────────────────────┘

KEY DESIGN DECISIONS:
    • threading.Event (stop_event) is used to signal workers to stop cleanly.
    • The event loop thread is a daemon so it auto-exits if the app dies.
    • GroqKeyRotator is instantiated once per engine start so it shares key
      rotation state across all concurrent workers.
    • asyncio.gather() runs all 5 workers concurrently inside the loop.
    • Engine state (running/stopped) is surfaced to Streamlit via properties.
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
# Engine Manager
# ---------------------------------------------------------------------------

class EngineManager:
    """
    Manages the lifecycle of the background asyncio worker pool.

    Usage (from Streamlit):
        engine = EngineManager()            # create once, store in st.session_state
        engine.start()                      # spin up background thread + workers
        engine.is_running                   # True/False for UI toggle state
        engine.stop()                       # graceful shutdown
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._loop:   Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()          # prevent concurrent start/stop races

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the background thread is alive and workers are active."""
        return (
            self._thread is not None
            and self._thread.is_alive()
            and not self._stop_event.is_set()
        )

    def start(self) -> None:
        """
        Start the background worker engine.

        Safe to call multiple times — if already running, does nothing.
        Logs the action to the database so the UI console reflects it.
        """
        with self._lock:
            if self.is_running:
                logger.info("Engine already running. Ignoring start().")
                return

            # Reset the stop signal before launching
            self._stop_event.clear()

            db.add_log("Engine", "🚀 Engine starting — spawning 5 workers...", "info")

            # Create and start the daemon thread
            self._thread = threading.Thread(
                target=self._run_event_loop,
                name="WorkerEngineThread",
                daemon=True,   # auto-killed if main process exits
            )
            self._thread.start()
            logger.info("Engine thread started: %s", self._thread.name)

    def stop(self) -> None:
        """
        Signal all workers to stop and wait for the thread to exit (max 10s).

        Workers check stop_event inside their sleep loops and exit cleanly
        rather than being killed mid-operation.
        """
        with self._lock:
            if not self.is_running:
                logger.info("Engine not running. Ignoring stop().")
                return

            db.add_log("Engine", "🛑 Stop signal sent — workers winding down...", "info")
            self._stop_event.set()

            # Give the thread up to 10 seconds to exit gracefully
            if self._thread:
                self._thread.join(timeout=10)
                if self._thread.is_alive():
                    logger.warning("Engine thread did not exit cleanly within 10s.")
                    db.add_log("Engine", "⚠️ Workers did not exit cleanly. Force-stopping.", "error")
                else:
                    db.add_log("Engine", "✅ All workers stopped cleanly.", "success")
                    logger.info("Engine thread stopped cleanly.")

            self._thread = None
            self._loop   = None

    def get_status_line(self) -> str:
        """Short status string for display in the UI header."""
        if self.is_running:
            return "🟢 Engine Running — Workers Active"
        return "🔴 Engine Stopped"

    # ------------------------------------------------------------------
    # Private: event loop thread target
    # ------------------------------------------------------------------

    def _run_event_loop(self) -> None:
        """
        Entry point for the background daemon thread.

        Creates a brand-new asyncio event loop for this thread (Streamlit's
        main thread has no loop), runs all workers concurrently via
        asyncio.gather(), and cleans up when done.
        """
        # Each background thread needs its own event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        try:
            loop.run_until_complete(self._run_all_workers())
        except Exception as exc:
            logger.error("Engine event loop crashed: %s", exc)
            db.add_log("Engine", f"💥 Engine crashed: {exc}", "error")
        finally:
            # Clean up pending tasks before closing the loop
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            loop.close()
            logger.info("Event loop closed.")

    async def _run_all_workers(self) -> None:
        """
        Instantiate a shared GroqKeyRotator, then launch all 5 worker
        coroutines concurrently using asyncio.gather().

        Each worker is wrapped in _safe_worker() which catches any
        uncaught exception so one worker's crash can't kill the rest.
        """
        rotator = GroqKeyRotator()

        if not rotator.has_valid_keys:
            db.add_log(
                "Engine",
                "⚠️ No Groq API keys found. Add keys in Settings before starting.",
                "error",
            )
            logger.warning("Engine started with no Groq API keys configured.")
            # Don't abort — workers will still log their own 'no keys' messages

        db.add_log("Engine", "All 5 workers launched concurrently.", "info")

        await asyncio.gather(
            self._safe_worker("Contact Sniper",    worker_contact_sniper,   rotator),
            self._safe_worker("Blog Bomber",       worker_blog_bomber,      rotator),
            self._safe_worker("YouTube Hijacker",  worker_youtube_hijacker, rotator),
            self._safe_worker("Pingback Engine",   worker_pingback_engine,  rotator),
            self._safe_worker("Reddit Sniper",     worker_reddit_sniper,    rotator),
        )

    async def _safe_worker(self, name: str, worker_fn, rotator: GroqKeyRotator) -> None:
        """
        Wrapper that runs a worker coroutine and catches any unhandled
        top-level exception, logging it without crashing other workers.
        """
        try:
            await worker_fn(rotator, self._stop_event)
        except asyncio.CancelledError:
            logger.info("Worker '%s' was cancelled.", name)
        except Exception as exc:
            logger.error("Worker '%s' crashed with: %s", name, exc)
            db.add_log(f"Worker_{name}", f"💥 Worker crashed: {exc}", "error")


# ---------------------------------------------------------------------------
# Module-level singleton getter
# ---------------------------------------------------------------------------
# Streamlit re-runs the entire script on every interaction.
# We store the EngineManager instance in st.session_state from app.py,
# but this factory function provides a safe fallback.

_global_engine: Optional[EngineManager] = None


def get_engine() -> EngineManager:
    """
    Return the global EngineManager singleton.

    In production (app.py), the engine is stored in st.session_state.
    This function is a safety net for direct module use or testing.
    """
    global _global_engine
    if _global_engine is None:
        _global_engine = EngineManager()
    return _global_engine
