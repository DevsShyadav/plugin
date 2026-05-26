"""
ui_dashboard.py
===============
Renders Tab 2: 📊 Live Dashboard & Logs

Sections:
    1. Engine Status Banner  — Live running/stopped indicator at the top
    2. Success Metrics Row   — Three animated counters: Forms | Comments | Pingbacks
    3. Worker Activity Grid  — Per-worker last-action status cards
    4. Live Terminal Console — Scrollable real-time log viewer with auto-refresh
    5. Controls Row          — Refresh button, log limit slider, clear logs button

Auto-refresh strategy:
    Streamlit doesn't natively push updates. We use st_autorefresh (from
    streamlit-autorefresh) OR a manual "Refresh" button + a countdown hint.
    The dashboard is designed to work without st_autorefresh as a fallback
    so the app has zero extra dependencies beyond requirements.txt.
"""

import streamlit as st
from datetime import datetime

import database as db
from engine import EngineManager


# ---------------------------------------------------------------------------
# Public entry point — called from app.py
# ---------------------------------------------------------------------------

def render_dashboard_tab(engine: EngineManager) -> None:
    """
    Render the entire Live Dashboard & Logs tab.

    Args:
        engine: The shared EngineManager singleton from st.session_state.
    """
    # ── Auto-refresh while engine is running ────────────────────────────────
    # Injects a lightweight meta-refresh every 8 seconds when engine is active.
    # This keeps the dashboard live without any extra pip package.
    if engine.is_running:
        st.markdown(
            '<meta http-equiv="refresh" content="8">',
            unsafe_allow_html=True,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 1. ENGINE STATUS BANNER
    # ═══════════════════════════════════════════════════════════════════════
    _render_status_banner(engine)
    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. SUCCESS METRICS ROW
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("### 📈 Success Metrics")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_metrics_row()
    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. WORKER ACTIVITY GRID
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("### 🤖 Worker Activity")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_worker_grid()
    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 4. LIVE TERMINAL CONSOLE
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("### 🖥️ Live Activity Console")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_terminal_console()


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_status_banner(engine: EngineManager) -> None:
    """Full-width status banner showing engine state + uptime hint."""
    is_running = engine.is_running
    now_str    = datetime.now().strftime("%b %d, %Y  %I:%M:%S %p")

    if is_running:
        st.markdown(
            f"""
            <div class="dashboard-banner banner-running">
                <span class="banner-icon">🟢</span>
                <span class="banner-title">Engine is <strong>LIVE</strong></span>
                <span class="banner-time">Last refreshed: {now_str}</span>
                <span class="banner-hint">Auto-refreshing every 8s</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="dashboard-banner banner-stopped">
                <span class="banner-icon">🔴</span>
                <span class="banner-title">Engine is <strong>STOPPED</strong></span>
                <span class="banner-time">As of: {now_str}</span>
                <span class="banner-hint">Go to ⚙️ Settings to start the engine</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_metrics_row() -> None:
    """
    Three large metric cards in a row:
        Forms Filled  |  Comments Posted  |  Pingbacks Sent
    Uses custom HTML cards for the green-accented design.
    Also renders st.metric() as a fallback for screen readers.
    """
    metrics = db.get_metrics()

    forms     = metrics.get("forms_filled",    0)
    comments  = metrics.get("comments_posted", 0)
    pingbacks = metrics.get("pingbacks_sent",  0)
    total     = forms + comments + pingbacks

    # ── Metric cards (styled) ───────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.markdown(
            _metric_card("📧", "Forms Filled", forms, "#27ae60"),
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            _metric_card("💬", "Comments Posted", comments, "#2ecc71"),
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            _metric_card("🔗", "Pingbacks Sent", pingbacks, "#1abc9c"),
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            _metric_card("⚡", "Total Actions", total, "#16a085"),
            unsafe_allow_html=True,
        )

    # Accessible native metrics (collapsed under expander to avoid clutter)
    with st.expander("📊 Raw metric values", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Forms Filled",    forms)
        c2.metric("Comments Posted", comments)
        c3.metric("Pingbacks Sent",  pingbacks)
        c4.metric("Total Actions",   total)

    # Reset button (aligned right)
    _, reset_col = st.columns([3, 1])
    with reset_col:
        if st.button("🔄 Reset Counters", key="reset_metrics_btn", help="Zero out all metric counters."):
            db.reset_metrics()
            st.rerun()


def _metric_card(icon: str, label: str, value: int, color: str) -> str:
    """Return HTML for a styled metric card."""
    return f"""
    <div class="metric-card" style="border-top: 4px solid {color};">
        <div class="metric-icon">{icon}</div>
        <div class="metric-value" style="color: {color};">{value:,}</div>
        <div class="metric-label">{label}</div>
    </div>
    """


def _render_worker_grid() -> None:
    """
    5 worker status cards showing the last log entry per worker.
    Green border = last action was success, red = error, grey = info/idle.
    """
    worker_definitions = [
        ("Worker_Contact_Sniper",   "📧", "Contact Form Sniper"),
        ("Worker_Blog_Bomber",      "📝", "Blog Comment Bomber"),
        ("Worker_YouTube_Hijacker", "▶️",  "YouTube Hijacker"),
        ("Worker_Pingback_Engine",  "🔗", "Pingback Engine"),
        ("Worker_Reddit_Sniper",    "🤖", "Reddit Sniper"),
    ]

    # Pull last log per worker from DB
    all_logs = db.get_recent_logs(limit=200)
    last_log_by_worker: dict[str, dict] = {}
    for log in reversed(all_logs):   # oldest-first so latest wins
        last_log_by_worker[log["worker"]] = log

    cols = st.columns(5)
    for col, (wkey, icon, label) in zip(cols, worker_definitions):
        with col:
            last = last_log_by_worker.get(wkey)
            if last:
                status     = last["status"]
                msg_short  = last["message"][:55] + "…" if len(last["message"]) > 55 else last["message"]
                try:
                    from datetime import datetime as _dt
                    ts = _dt.fromisoformat(last["timestamp"]).strftime("%H:%M:%S")
                except Exception:
                    ts = last["timestamp"]
            else:
                status    = "idle"
                msg_short = "No activity yet."
                ts        = "—"

            border_color = {
                "success": "#27ae60",
                "error":   "#e74c3c",
                "info":    "#95a5a6",
                "idle":    "#bdc3c7",
            }.get(status, "#bdc3c7")

            status_dot = {
                "success": "🟢",
                "error":   "🔴",
                "info":    "🔵",
                "idle":    "⚪",
            }.get(status, "⚪")

            st.markdown(
                f"""
                <div class="worker-card" style="border-left: 4px solid {border_color};">
                    <div class="wc-header">
                        <span class="wc-icon">{icon}</span>
                        <span class="wc-label">{label}</span>
                        <span class="wc-dot">{status_dot}</span>
                    </div>
                    <div class="wc-msg">{msg_short}</div>
                    <div class="wc-ts">{ts}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_terminal_console() -> None:
    """
    Scrollable terminal-style log console.
    Shows timestamped entries with colour-coded status icons.
    Includes a log-limit slider and a manual refresh button.
    """
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])

    with ctrl1:
        log_limit = st.slider(
            "Lines to display",
            min_value=20,
            max_value=300,
            value=80,
            step=20,
            key="log_limit_slider",
            help="Number of recent log lines shown in the console.",
        )
    with ctrl2:
        if st.button("🔄 Refresh Logs", key="refresh_logs_btn", use_container_width=True):
            st.rerun()
    with ctrl3:
        if st.button("🗑️ Clear All Logs", key="clear_logs_btn", use_container_width=True,
                     help="Permanently deletes all log entries from the database."):
            _clear_all_logs()
            st.rerun()

    # Pull formatted log text from DB
    log_text = db.get_logs_as_text(limit=log_limit)
    log_count = db.get_log_count()

    st.markdown(
        f"<p class='log-count-label'>Showing latest <strong>{log_limit}</strong> "
        f"of <strong>{log_count}</strong> total log entries.</p>",
        unsafe_allow_html=True,
    )

    # Terminal box — styled via CSS in app.py
    st.markdown(
        f'<div class="terminal-box"><pre class="terminal-text">{log_text}</pre></div>',
        unsafe_allow_html=True,
    )

    # Download button for full log export
    st.download_button(
        label="⬇️ Export Full Log as .txt",
        data=db.get_logs_as_text(limit=500),
        file_name=f"marketing_engine_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        key="export_logs_btn",
    )


def _clear_all_logs() -> None:
    """Delete all rows from activity_logs table."""
    import sqlite3
    conn = db.get_connection()
    conn.execute("DELETE FROM activity_logs")
    conn.commit()
