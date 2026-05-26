"""
database.py
===========
SQLite database layer — AI Marketing Dashboard
Tables:
    api_keys      — 3 Groq key slots
    plugins       — plugin registry
    plugin_stats  — per-plugin per-platform action tracking
    activity_logs — timestamped worker log entries
    metrics       — global running counters
"""

import sqlite3
import threading
import base64
import os
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# DB Path — uses /data on HF Spaces (persistent volume), else local
# ---------------------------------------------------------------------------
_HF_DATA_DIR = "/data"
if os.path.isdir(_HF_DATA_DIR) and os.access(_HF_DATA_DIR, os.W_OK):
    DB_PATH = os.path.join(_HF_DATA_DIR, "marketing_engine.db")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marketing_engine.db")

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db() -> None:
    conn = get_connection()
    c = conn.cursor()

    # API Keys
    c.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            slot    INTEGER PRIMARY KEY,
            key_val TEXT NOT NULL DEFAULT ''
        )
    """)
    for slot in (1, 2, 3):
        c.execute("INSERT OR IGNORE INTO api_keys (slot, key_val) VALUES (?, ?)", (slot, ""))

    # Plugins
    c.execute("""
        CREATE TABLE IF NOT EXISTS plugins (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            shortlink   TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Per-plugin per-platform stats  ← NEW
    c.execute("""
        CREATE TABLE IF NOT EXISTS plugin_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            plugin_id   INTEGER NOT NULL,
            platform    TEXT NOT NULL,
            action      TEXT NOT NULL,
            target_url  TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE CASCADE
        )
    """)

    # Activity logs
    c.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            worker    TEXT NOT NULL,
            status    TEXT NOT NULL,
            message   TEXT NOT NULL
        )
    """)

    # Global metrics
    c.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id              INTEGER PRIMARY KEY DEFAULT 1,
            forms_filled    INTEGER NOT NULL DEFAULT 0,
            comments_posted INTEGER NOT NULL DEFAULT 0,
            pingbacks_sent  INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("INSERT OR IGNORE INTO metrics VALUES (1, 0, 0, 0)")
    conn.commit()


# ---------------------------------------------------------------------------
# Obfuscation
# ---------------------------------------------------------------------------
def _obfuscate(v: str) -> str:
    return base64.b64encode(v.encode()).decode() if v else ""

def _deobfuscate(v: str) -> str:
    try:
        return base64.b64decode(v.encode()).decode() if v else ""
    except Exception:
        return v


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------
def save_api_key(slot: int, key_value: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE api_keys SET key_val = ? WHERE slot = ?", (_obfuscate(key_value), slot))
    conn.commit()

def get_api_key(slot: int) -> str:
    row = get_connection().execute("SELECT key_val FROM api_keys WHERE slot = ?", (slot,)).fetchone()
    return _deobfuscate(row["key_val"]) if row else ""

def get_all_api_keys() -> dict:
    return {slot: get_api_key(slot) for slot in (1, 2, 3)}


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------
def add_plugin(name: str, shortlink: str, description: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO plugins (name, shortlink, description) VALUES (?, ?, ?)",
        (name.strip(), shortlink.strip(), description.strip())
    )
    conn.commit()
    return cur.lastrowid

def delete_plugin(plugin_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))
    conn.commit()

def get_all_plugins() -> list[dict]:
    rows = get_connection().execute(
        "SELECT id, name, shortlink, description, created_at FROM plugins ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Plugin Stats  ← NEW — per-plugin per-platform tracking
# ---------------------------------------------------------------------------
def record_plugin_action(plugin_id: int, platform: str, action: str, target_url: str = "") -> None:
    """
    Record every action taken for a plugin.
    platform: 'contact_form' | 'blog_comment' | 'youtube' | 'pingback' | 'reddit'
    action:   'submitted'    | 'commented'    | 'commented'| 'sent'     | 'replied'
    """
    conn = get_connection()
    conn.execute(
        "INSERT INTO plugin_stats (plugin_id, platform, action, target_url) VALUES (?, ?, ?, ?)",
        (plugin_id, platform, action, target_url)
    )
    conn.commit()

def get_plugin_stats(plugin_id: int) -> dict:
    """
    Returns stats for a single plugin:
    {
        'total': int,
        'by_platform': {'contact_form': n, 'blog_comment': n, ...},
        'recent': [{'platform', 'action', 'target_url', 'created_at'}, ...]
    }
    """
    conn = get_connection()

    total_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM plugin_stats WHERE plugin_id = ?", (plugin_id,)
    ).fetchone()
    total = total_row["cnt"] if total_row else 0

    platform_rows = conn.execute(
        "SELECT platform, COUNT(*) as cnt FROM plugin_stats WHERE plugin_id = ? GROUP BY platform",
        (plugin_id,)
    ).fetchall()
    by_platform = {r["platform"]: r["cnt"] for r in platform_rows}

    recent_rows = conn.execute(
        "SELECT platform, action, target_url, created_at FROM plugin_stats "
        "WHERE plugin_id = ? ORDER BY id DESC LIMIT 20",
        (plugin_id,)
    ).fetchall()
    recent = [dict(r) for r in recent_rows]

    return {"total": total, "by_platform": by_platform, "recent": recent}

def get_all_plugin_stats_summary() -> list[dict]:
    """
    Returns a summary row per plugin joining plugins + plugin_stats counts.
    Used for the dashboard overview table.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            p.id,
            p.name,
            p.shortlink,
            COUNT(ps.id)                                        AS total_actions,
            SUM(CASE WHEN ps.platform='contact_form'  THEN 1 ELSE 0 END) AS forms,
            SUM(CASE WHEN ps.platform='blog_comment'  THEN 1 ELSE 0 END) AS blog_comments,
            SUM(CASE WHEN ps.platform='youtube'       THEN 1 ELSE 0 END) AS yt_comments,
            SUM(CASE WHEN ps.platform='pingback'      THEN 1 ELSE 0 END) AS pingbacks,
            SUM(CASE WHEN ps.platform='reddit'        THEN 1 ELSE 0 END) AS reddit_replies,
            MAX(ps.created_at)                                  AS last_action
        FROM plugins p
        LEFT JOIN plugin_stats ps ON ps.plugin_id = p.id
        GROUP BY p.id
        ORDER BY total_actions DESC
    """).fetchall()
    return [dict(r) for r in rows]

def get_platform_totals() -> dict:
    """Global totals across all plugins by platform."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT platform, COUNT(*) as cnt FROM plugin_stats GROUP BY platform"
    ).fetchall()
    return {r["platform"]: r["cnt"] for r in rows}

def get_daily_activity(days: int = 14) -> list[dict]:
    """Returns daily action counts for the last N days (for sparkline chart)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DATE(created_at) as day, COUNT(*) as cnt
        FROM plugin_stats
        WHERE created_at >= DATE('now', ? || ' days')
        GROUP BY day
        ORDER BY day ASC
    """, (f"-{days}",)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Activity Logs
# ---------------------------------------------------------------------------
def add_log(worker: str, message: str, status: str = "info") -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_logs (worker, status, message) VALUES (?, ?, ?)",
        (worker, status, message)
    )
    conn.execute("""
        DELETE FROM activity_logs WHERE id NOT IN (
            SELECT id FROM activity_logs ORDER BY id DESC LIMIT 500
        )
    """)
    conn.commit()

def get_recent_logs(limit: int = 100) -> list[dict]:
    rows = get_connection().execute(
        "SELECT id, timestamp, worker, status, message "
        "FROM activity_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in reversed(rows)]

def get_log_count() -> int:
    row = get_connection().execute("SELECT COUNT(*) as cnt FROM activity_logs").fetchone()
    return row["cnt"] if row else 0

def get_logs_as_text(limit: int = 100) -> str:
    logs = get_recent_logs(limit)
    if not logs:
        return "No activity yet. Start the engine to begin.\n"
    lines = []
    for e in logs:
        try:
            ts = datetime.fromisoformat(e["timestamp"]).strftime("%I:%M:%S %p")
        except Exception:
            ts = e["timestamp"]
        icon = {"success": "✅", "error": "❌", "info": "ℹ️ "}.get(e["status"], "•")
        lines.append(f"[{ts}] {icon} [{e['worker']}] {e['message']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Global Metrics
# ---------------------------------------------------------------------------
def increment_metric(field: str, amount: int = 1) -> None:
    allowed = {"forms_filled", "comments_posted", "pingbacks_sent"}
    if field not in allowed:
        raise ValueError(f"Invalid metric: {field}")
    get_connection().execute(
        f"UPDATE metrics SET {field} = {field} + ? WHERE id = 1", (amount,)
    )
    get_connection().commit()

def get_metrics() -> dict:
    row = get_connection().execute(
        "SELECT forms_filled, comments_posted, pingbacks_sent FROM metrics WHERE id = 1"
    ).fetchone()
    return dict(row) if row else {"forms_filled": 0, "comments_posted": 0, "pingbacks_sent": 0}

def reset_metrics() -> None:
    conn = get_connection()
    conn.execute("UPDATE metrics SET forms_filled=0, comments_posted=0, pingbacks_sent=0 WHERE id=1")
    conn.commit()
