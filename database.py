"""
database.py
===========
SQLite database layer for the Jarvis AI Marketing Engine.

Tables:
    - api_keys          : Groq API keys (3 slots)
    - credentials       : Platform credentials (YouTube/Gmail, Reddit/PRAW)
    - plugins           : Dynamic plugin registry
    - activity_logs     : Timestamped worker action log entries
    - metrics           : Running counters per action type
    - attempt_reports   : Detailed per-attempt reports (success + failed with reasons)
    - plugin_reports    : Aggregated per-plugin performance stats

Key improvements over v1:
    - Every failed attempt is logged with reason (Hindi/English)
    - Per-plugin detailed reports with success/fail counts
    - Platform credentials storage (Gmail for YouTube, PRAW for Reddit)
    - Auto-retry tracking (attempt count, last strategy used)
    - Keeps 2000 log entries instead of 500
"""

import sqlite3
import threading
import base64
import os
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "marketing_engine.db")
_local = threading.local()


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- API Keys table (3 Groq key slots) ---------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            slot    INTEGER PRIMARY KEY,
            key_val TEXT NOT NULL DEFAULT ''
        )
    """)
    for slot in (1, 2, 3):
        cursor.execute(
            "INSERT OR IGNORE INTO api_keys (slot, key_val) VALUES (?, ?)",
            (slot, "")
        )

    # --- Platform Credentials table ----------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            platform    TEXT PRIMARY KEY,
            cred_json   TEXT NOT NULL DEFAULT '{}'
        )
    """)
    # Pre-populate platform slots
    for platform in ("youtube_gmail", "reddit_praw"):
        cursor.execute(
            "INSERT OR IGNORE INTO credentials (platform, cred_json) VALUES (?, ?)",
            (platform, "{}")
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
            status     TEXT NOT NULL,
            message    TEXT NOT NULL
        )
    """)

    # --- Metrics table (single row, always id=1) ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id                  INTEGER PRIMARY KEY DEFAULT 1,
            forms_filled        INTEGER NOT NULL DEFAULT 0,
            comments_posted     INTEGER NOT NULL DEFAULT 0,
            pingbacks_sent      INTEGER NOT NULL DEFAULT 0,
            youtube_comments    INTEGER NOT NULL DEFAULT 0,
            reddit_replies      INTEGER NOT NULL DEFAULT 0,
            total_retries       INTEGER NOT NULL DEFAULT 0,
            total_failures      INTEGER NOT NULL DEFAULT 0
        )
    """)
    cursor.execute(
        "INSERT OR IGNORE INTO metrics (id) VALUES (1)"
    )

    # --- Attempt Reports table (every single attempt logged) ---------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attempt_reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
            worker          TEXT NOT NULL,
            plugin_id       INTEGER,
            plugin_name     TEXT NOT NULL DEFAULT '',
            target_url      TEXT NOT NULL DEFAULT '',
            action_type     TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'failed',
            attempt_number  INTEGER NOT NULL DEFAULT 1,
            strategy_used   TEXT NOT NULL DEFAULT 'default',
            error_reason    TEXT NOT NULL DEFAULT '',
            error_reason_hi TEXT NOT NULL DEFAULT '',
            response_detail TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE SET NULL
        )
    """)

    # --- Plugin Reports (aggregated per-plugin stats) ----------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plugin_reports (
            plugin_id           INTEGER PRIMARY KEY,
            plugin_name         TEXT NOT NULL DEFAULT '',
            total_attempts      INTEGER NOT NULL DEFAULT 0,
            successful_attempts INTEGER NOT NULL DEFAULT 0,
            failed_attempts     INTEGER NOT NULL DEFAULT 0,
            retry_count         INTEGER NOT NULL DEFAULT 0,
            last_success_at     TEXT,
            last_failure_at     TEXT,
            last_error          TEXT NOT NULL DEFAULT '',
            platforms_used      TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE CASCADE
        )
    """)

    conn.commit()


# ---------------------------------------------------------------------------
# Obfuscation helpers
# ---------------------------------------------------------------------------

def _obfuscate(value: str) -> str:
    return base64.b64encode(value.encode()).decode() if value else ""

def _deobfuscate(value: str) -> str:
    try:
        return base64.b64decode(value.encode()).decode() if value else ""
    except Exception:
        return value


# ---------------------------------------------------------------------------
# API Key CRUD
# ---------------------------------------------------------------------------

def save_api_key(slot: int, key_value: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE api_keys SET key_val = ? WHERE slot = ?",
        (_obfuscate(key_value), slot)
    )
    conn.commit()

def get_api_key(slot: int) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT key_val FROM api_keys WHERE slot = ?", (slot,)
    ).fetchone()
    return _deobfuscate(row["key_val"]) if row else ""

def get_all_api_keys() -> dict:
    return {slot: get_api_key(slot) for slot in (1, 2, 3)}


# ---------------------------------------------------------------------------
# Platform Credentials CRUD
# ---------------------------------------------------------------------------

def save_credentials(platform: str, cred_dict: dict) -> None:
    """Save platform credentials as JSON string."""
    import json
    conn = get_connection()
    conn.execute(
        "UPDATE credentials SET cred_json = ? WHERE platform = ?",
        (_obfuscate(json.dumps(cred_dict)), platform)
    )
    conn.commit()

def get_credentials(platform: str) -> dict:
    """Retrieve platform credentials as dict."""
    import json
    conn = get_connection()
    row = conn.execute(
        "SELECT cred_json FROM credentials WHERE platform = ?", (platform,)
    ).fetchone()
    if row and row["cred_json"]:
        try:
            return json.loads(_deobfuscate(row["cred_json"]))
        except Exception:
            return {}
    return {}

def has_credentials(platform: str) -> bool:
    """Check if valid credentials exist for a platform."""
    creds = get_credentials(platform)
    if platform == "youtube_gmail":
        return bool(creds.get("email") and creds.get("password"))
    elif platform == "reddit_praw":
        return bool(
            creds.get("client_id") and creds.get("client_secret")
            and creds.get("username") and creds.get("password")
        )
    return False


# ---------------------------------------------------------------------------
# Plugin CRUD
# ---------------------------------------------------------------------------

def add_plugin(name: str, shortlink: str, description: str) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO plugins (name, shortlink, description) VALUES (?, ?, ?)",
        (name.strip(), shortlink.strip(), description.strip())
    )
    plugin_id = cursor.lastrowid
    # Initialize plugin report entry
    conn.execute(
        "INSERT OR IGNORE INTO plugin_reports (plugin_id, plugin_name) VALUES (?, ?)",
        (plugin_id, name.strip())
    )
    conn.commit()
    return plugin_id

def delete_plugin(plugin_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))
    conn.execute("DELETE FROM plugin_reports WHERE plugin_id = ?", (plugin_id,))
    conn.commit()

def get_all_plugins() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, shortlink, description, created_at FROM plugins ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Activity Log CRUD
# ---------------------------------------------------------------------------

def add_log(worker: str, message: str, status: str = "info") -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_logs (worker, status, message) VALUES (?, ?, ?)",
        (worker, status, message)
    )
    # Keep latest 2000 rows
    conn.execute("""
        DELETE FROM activity_logs
        WHERE id NOT IN (
            SELECT id FROM activity_logs ORDER BY id DESC LIMIT 2000
        )
    """)
    conn.commit()

def get_recent_logs(limit: int = 100) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, timestamp, worker, status, message "
        "FROM activity_logs ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [dict(row) for row in reversed(rows)]

def get_log_count() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM activity_logs").fetchone()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Attempt Reports CRUD
# ---------------------------------------------------------------------------

def log_attempt(
    worker: str,
    plugin_id: Optional[int],
    plugin_name: str,
    target_url: str,
    action_type: str,
    status: str,
    attempt_number: int = 1,
    strategy_used: str = "default",
    error_reason: str = "",
    error_reason_hi: str = "",
    response_detail: str = "",
) -> int:
    """
    Log every single attempt (success or failure) with full details.
    Returns the attempt report ID.
    """
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO attempt_reports 
           (worker, plugin_id, plugin_name, target_url, action_type, status,
            attempt_number, strategy_used, error_reason, error_reason_hi, response_detail)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (worker, plugin_id, plugin_name, target_url, action_type, status,
         attempt_number, strategy_used, error_reason, error_reason_hi, response_detail)
    )
    # Keep only latest 5000 attempt reports
    conn.execute("""
        DELETE FROM attempt_reports
        WHERE id NOT IN (
            SELECT id FROM attempt_reports ORDER BY id DESC LIMIT 5000
        )
    """)
    conn.commit()

    # Update plugin report aggregates
    if plugin_id:
        _update_plugin_report(plugin_id, plugin_name, status, error_reason, worker)

    return cursor.lastrowid


def get_attempt_reports(
    limit: int = 100,
    status_filter: Optional[str] = None,
    worker_filter: Optional[str] = None,
    plugin_id_filter: Optional[int] = None,
) -> list[dict]:
    """Get attempt reports with optional filters."""
    conn = get_connection()
    query = "SELECT * FROM attempt_reports WHERE 1=1"
    params = []

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if worker_filter:
        query += " AND worker = ?"
        params.append(worker_filter)
    if plugin_id_filter:
        query += " AND plugin_id = ?"
        params.append(plugin_id_filter)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_failed_attempts(limit: int = 50) -> list[dict]:
    """Get only failed attempts with reasons."""
    return get_attempt_reports(limit=limit, status_filter="failed")


# ---------------------------------------------------------------------------
# Plugin Reports CRUD
# ---------------------------------------------------------------------------

def _update_plugin_report(
    plugin_id: int,
    plugin_name: str,
    status: str,
    error_reason: str,
    worker: str,
) -> None:
    """Update aggregated plugin report after each attempt."""
    import json
    conn = get_connection()

    # Ensure row exists
    conn.execute(
        "INSERT OR IGNORE INTO plugin_reports (plugin_id, plugin_name) VALUES (?, ?)",
        (plugin_id, plugin_name)
    )

    now = datetime.now().isoformat()

    if status == "success":
        conn.execute("""
            UPDATE plugin_reports SET
                total_attempts = total_attempts + 1,
                successful_attempts = successful_attempts + 1,
                last_success_at = ?
            WHERE plugin_id = ?
        """, (now, plugin_id))
    else:
        conn.execute("""
            UPDATE plugin_reports SET
                total_attempts = total_attempts + 1,
                failed_attempts = failed_attempts + 1,
                last_failure_at = ?,
                last_error = ?
            WHERE plugin_id = ?
        """, (now, error_reason, plugin_id))

    # Update platforms_used JSON
    row = conn.execute(
        "SELECT platforms_used FROM plugin_reports WHERE plugin_id = ?",
        (plugin_id,)
    ).fetchone()
    if row:
        try:
            platforms = json.loads(row["platforms_used"])
        except Exception:
            platforms = {}
        platform_key = worker.replace("Worker_", "").lower()
        platforms[platform_key] = platforms.get(platform_key, 0) + 1
        conn.execute(
            "UPDATE plugin_reports SET platforms_used = ? WHERE plugin_id = ?",
            (json.dumps(platforms), plugin_id)
        )

    conn.commit()


def get_plugin_reports() -> list[dict]:
    """Get all plugin performance reports."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM plugin_reports ORDER BY total_attempts DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_plugin_report(plugin_id: int) -> Optional[dict]:
    """Get detailed report for a specific plugin."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM plugin_reports WHERE plugin_id = ?",
        (plugin_id,)
    ).fetchone()
    return dict(row) if row else None


def increment_retry_count(plugin_id: int) -> None:
    """Increment retry count for a plugin."""
    conn = get_connection()
    conn.execute(
        "UPDATE plugin_reports SET retry_count = retry_count + 1 WHERE plugin_id = ?",
        (plugin_id,)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Metrics CRUD
# ---------------------------------------------------------------------------

def increment_metric(field: str, amount: int = 1) -> None:
    allowed = {
        "forms_filled", "comments_posted", "pingbacks_sent",
        "youtube_comments", "reddit_replies", "total_retries", "total_failures"
    }
    if field not in allowed:
        raise ValueError(f"Invalid metric field: {field!r}")
    conn = get_connection()
    conn.execute(
        f"UPDATE metrics SET {field} = {field} + ? WHERE id = 1",
        (amount,)
    )
    conn.commit()

def get_metrics() -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM metrics WHERE id = 1").fetchone()
    if row:
        return dict(row)
    return {
        "forms_filled": 0, "comments_posted": 0, "pingbacks_sent": 0,
        "youtube_comments": 0, "reddit_replies": 0,
        "total_retries": 0, "total_failures": 0
    }

def reset_metrics() -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE metrics SET 
            forms_filled = 0, comments_posted = 0, pingbacks_sent = 0,
            youtube_comments = 0, reddit_replies = 0,
            total_retries = 0, total_failures = 0
        WHERE id = 1
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Log export helpers
# ---------------------------------------------------------------------------

def get_logs_as_text(limit: int = 100) -> str:
    logs = get_recent_logs(limit)
    if not logs:
        return "No activity yet. Start the engine to begin.\n"

    lines = []
    for entry in logs:
        try:
            dt = datetime.fromisoformat(entry["timestamp"])
            ts = dt.strftime("%I:%M:%S %p")
        except Exception:
            ts = entry["timestamp"]

        status_icon = {
            "success": "✅",
            "error":   "❌",
            "info":    "ℹ️ ",
            "retry":   "🔄",
            "warning": "⚠️",
        }.get(entry["status"], "•")

        lines.append(
            f"[{ts}] {status_icon} [{entry['worker']}] {entry['message']}"
        )

    return "\n".join(lines)


def clear_all_logs() -> None:
    """Delete all log entries."""
    conn = get_connection()
    conn.execute("DELETE FROM activity_logs")
    conn.commit()


def clear_attempt_reports() -> None:
    """Delete all attempt reports."""
    conn = get_connection()
    conn.execute("DELETE FROM attempt_reports")
    conn.commit()
