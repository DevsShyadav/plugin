"""
database.py
===========
SQLite database layer for the AI Marketing Dashboard.
Handles all persistence: API keys, plugins, logs, and metrics counters.

Tables:
    - api_keys      : Stores up to 3 Groq API keys (encrypted at rest via base64 obfuscation)
    - plugins       : Dynamic plugin registry (name, shortlink, description)
    - activity_logs : Timestamped worker action log entries
    - metrics       : Running counters for forms, comments, pingbacks
"""

import sqlite3
import threading
import base64
import json
import os
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Database path — stored alongside the app so it persists between runs
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "marketing_engine.db")

# Thread-local storage so each thread gets its own SQLite connection
# (SQLite connections are NOT safe to share across threads)
_local = threading.local()


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Return a per-thread SQLite connection with row_factory set to
    sqlite3.Row so columns are accessible by name.
    """
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")   # better concurrency
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


# ---------------------------------------------------------------------------
# Schema bootstrap — call once at app startup
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- API Keys table (single row, slot-based) ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            slot    INTEGER PRIMARY KEY,   -- 1, 2, or 3
            key_val TEXT NOT NULL DEFAULT ''
        )
    """)

    # Pre-populate 3 empty slots so we can always UPDATE instead of INSERT
    for slot in (1, 2, 3):
        cursor.execute(
            "INSERT OR IGNORE INTO api_keys (slot, key_val) VALUES (?, ?)",
            (slot, "")
        )

    # --- Plugins table ------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plugins (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            shortlink   TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- Activity logs table ------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT NOT NULL DEFAULT (datetime('now')),
            worker     TEXT NOT NULL,
            status     TEXT NOT NULL,   -- 'success' | 'error' | 'info'
            message    TEXT NOT NULL
        )
    """)

    # --- Metrics table (single row, always id=1) ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id              INTEGER PRIMARY KEY DEFAULT 1,
            forms_filled    INTEGER NOT NULL DEFAULT 0,
            comments_posted INTEGER NOT NULL DEFAULT 0,
            pingbacks_sent  INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Pre-populate the single metrics row
    cursor.execute(
        "INSERT OR IGNORE INTO metrics (id, forms_filled, comments_posted, pingbacks_sent) "
        "VALUES (1, 0, 0, 0)"
    )

    conn.commit()


# ---------------------------------------------------------------------------
# Lightweight obfuscation helpers (NOT encryption — just avoids plain-text
# storage of API keys in case someone casually opens the .db file)
# ---------------------------------------------------------------------------

def _obfuscate(value: str) -> str:
    """Base64-encode a string for light obfuscation."""
    return base64.b64encode(value.encode()).decode() if value else ""


def _deobfuscate(value: str) -> str:
    """Decode a base64-encoded string."""
    try:
        return base64.b64decode(value.encode()).decode() if value else ""
    except Exception:
        return value   # fallback: return as-is if decode fails


# ---------------------------------------------------------------------------
# API Key CRUD
# ---------------------------------------------------------------------------

def save_api_key(slot: int, key_value: str) -> None:
    """Persist an API key to a given slot (1–3)."""
    conn = get_connection()
    conn.execute(
        "UPDATE api_keys SET key_val = ? WHERE slot = ?",
        (_obfuscate(key_value), slot)
    )
    conn.commit()


def get_api_key(slot: int) -> str:
    """Retrieve and decode an API key from a slot (1–3). Returns '' if empty."""
    conn = get_connection()
    row = conn.execute(
        "SELECT key_val FROM api_keys WHERE slot = ?", (slot,)
    ).fetchone()
    return _deobfuscate(row["key_val"]) if row else ""


def get_all_api_keys() -> dict:
    """
    Return all 3 API keys as a dict: {1: 'key_or_empty', 2: ..., 3: ...}
    """
    return {slot: get_api_key(slot) for slot in (1, 2, 3)}


# ---------------------------------------------------------------------------
# Plugin CRUD
# ---------------------------------------------------------------------------

def add_plugin(name: str, shortlink: str, description: str) -> int:
    """Insert a new plugin. Returns the new row's id."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO plugins (name, shortlink, description) VALUES (?, ?, ?)",
        (name.strip(), shortlink.strip(), description.strip())
    )
    conn.commit()
    return cursor.lastrowid


def delete_plugin(plugin_id: int) -> None:
    """Delete a plugin by its primary key."""
    conn = get_connection()
    conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))
    conn.commit()


def get_all_plugins() -> list[dict]:
    """
    Return all plugins as a list of dicts with keys:
    id, name, shortlink, description, created_at
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, shortlink, description, created_at FROM plugins ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Activity Log CRUD
# ---------------------------------------------------------------------------

def add_log(worker: str, message: str, status: str = "info") -> None:
    """
    Append a log entry. Status should be 'success', 'error', or 'info'.
    Keeps only the latest 500 rows to prevent unbounded growth.
    """
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_logs (worker, status, message) VALUES (?, ?, ?)",
        (worker, status, message)
    )
    # Prune oldest rows beyond 500
    conn.execute("""
        DELETE FROM activity_logs
        WHERE id NOT IN (
            SELECT id FROM activity_logs ORDER BY id DESC LIMIT 500
        )
    """)
    conn.commit()


def get_recent_logs(limit: int = 100) -> list[dict]:
    """
    Return the most recent log entries (newest-first).
    Each dict: id, timestamp, worker, status, message
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, timestamp, worker, status, message "
        "FROM activity_logs ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    # Reverse so newest is at the bottom (terminal-style)
    return [dict(row) for row in reversed(rows)]


def get_log_count() -> int:
    """Return total number of log entries stored."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM activity_logs").fetchone()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Metrics CRUD
# ---------------------------------------------------------------------------

def increment_metric(field: str, amount: int = 1) -> None:
    """
    Atomically increment one of the three metric counters.
    field must be 'forms_filled', 'comments_posted', or 'pingbacks_sent'.
    """
    allowed = {"forms_filled", "comments_posted", "pingbacks_sent"}
    if field not in allowed:
        raise ValueError(f"Invalid metric field: {field!r}. Must be one of {allowed}")
    conn = get_connection()
    conn.execute(
        f"UPDATE metrics SET {field} = {field} + ? WHERE id = 1",
        (amount,)
    )
    conn.commit()


def get_metrics() -> dict:
    """
    Return the current metrics as a dict:
    {'forms_filled': int, 'comments_posted': int, 'pingbacks_sent': int}
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT forms_filled, comments_posted, pingbacks_sent FROM metrics WHERE id = 1"
    ).fetchone()
    return dict(row) if row else {"forms_filled": 0, "comments_posted": 0, "pingbacks_sent": 0}


def reset_metrics() -> None:
    """Zero out all metric counters (useful for fresh runs)."""
    conn = get_connection()
    conn.execute(
        "UPDATE metrics SET forms_filled = 0, comments_posted = 0, pingbacks_sent = 0 WHERE id = 1"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Convenience: export logs as plain text for the UI terminal
# ---------------------------------------------------------------------------

def get_logs_as_text(limit: int = 100) -> str:
    """
    Return recent logs formatted as a terminal-style multiline string.
    Example line:
        [2024-06-01 10:05:32] [Worker_Blog_Bomber] [SUCCESS] Found post at example.com
    """
    logs = get_recent_logs(limit)
    if not logs:
        return "No activity yet. Start the engine to begin.\n"

    lines = []
    for entry in logs:
        # Parse stored ISO timestamp and reformat to HH:MM:SS
        try:
            dt = datetime.fromisoformat(entry["timestamp"])
            ts = dt.strftime("%I:%M:%S %p")
        except Exception:
            ts = entry["timestamp"]

        status_icon = {
            "success": "✅",
            "error":   "❌",
            "info":    "ℹ️ ",
        }.get(entry["status"], "•")

        lines.append(
            f"[{ts}] {status_icon} [{entry['worker']}] {entry['message']}"
        )

    return "\n".join(lines)
