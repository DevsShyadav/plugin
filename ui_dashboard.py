"""
ui_dashboard.py
===============
Jarvis AI Marketing Engine — Live Dashboard & Reports Tab

Silicon Valley Premium White + Green UI with:
    1. Engine Status Banner — Live/stopped with uptime
    2. Success Metrics Row — 7 metric cards with animations
    3. Worker Activity Grid — Per-worker last-action cards
    4. Plugin Performance Reports — Detailed per-plugin stats
    5. Failed Attempts Report — Every failure with reason (Hindi/English)
    6. Live Terminal Console — Real-time log viewer
"""

import json
import streamlit as st
from datetime import datetime

import database as db
from engine import EngineManager


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_dashboard_tab(engine: EngineManager) -> None:
    """Render the Live Dashboard & Reports tab."""

    # Auto-refresh when running
    if engine.is_running:
        st.markdown(
            '<meta http-equiv="refresh" content="6">',
            unsafe_allow_html=True,
        )

    # 1. Status Banner
    _render_status_banner(engine)
    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Metrics Row
    st.markdown("### 📈 Performance Metrics")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_metrics_row()
    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Worker Activity Grid
    st.markdown("### 🤖 Worker Status")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_worker_grid()
    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Plugin Reports
    st.markdown("### 📊 Plugin Performance Reports")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_plugin_reports()
    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Failed Attempts
    st.markdown("### ❌ Failed Attempts & Diagnostics")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_failed_attempts()
    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Live Console
    st.markdown("### 🖥️ Live Activity Console")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
    _render_terminal_console()



# ---------------------------------------------------------------------------
# 1. Status Banner
# ---------------------------------------------------------------------------

def _render_status_banner(engine: EngineManager) -> None:
    """Full-width engine status banner."""
    is_running = engine.is_running
    now_str = datetime.now().strftime("%b %d, %Y  %I:%M:%S %p")

    if is_running:
        st.markdown(
            f"""
            <div class="dashboard-banner banner-running">
                <span style="font-size:1.4rem;">🟢</span>
                <span class="banner-title">JARVIS is <strong>LIVE</strong></span>
                <span class="banner-time">⏱️ Uptime: {engine.uptime} &nbsp;|&nbsp; Refreshed: {now_str}</span>
                <span class="banner-hint">Auto-refresh: 6s</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="dashboard-banner banner-stopped">
                <span style="font-size:1.4rem;">🔴</span>
                <span class="banner-title">Engine is <strong>OFFLINE</strong></span>
                <span class="banner-time">As of: {now_str}</span>
                <span class="banner-hint">Go to ⚙️ Settings to start</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# 2. Metrics Row
# ---------------------------------------------------------------------------

def _render_metrics_row() -> None:
    """7 metric cards with green accents."""
    metrics = db.get_metrics()

    forms = metrics.get("forms_filled", 0)
    comments = metrics.get("comments_posted", 0)
    pingbacks = metrics.get("pingbacks_sent", 0)
    yt_comments = metrics.get("youtube_comments", 0)
    reddit_replies = metrics.get("reddit_replies", 0)
    retries = metrics.get("total_retries", 0)
    failures = metrics.get("total_failures", 0)
    total = forms + comments + pingbacks + yt_comments + reddit_replies

    # Row 1: Main metrics
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(_metric_card("📧", "Forms Filled", forms, "#27ae60"), unsafe_allow_html=True)
    with m2:
        st.markdown(_metric_card("💬", "Blog Comments", comments, "#2ecc71"), unsafe_allow_html=True)
    with m3:
        st.markdown(_metric_card("▶️", "YT Comments", yt_comments, "#1abc9c"), unsafe_allow_html=True)
    with m4:
        st.markdown(_metric_card("🤖", "Reddit Replies", reddit_replies, "#16a085"), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Row 2: Secondary metrics
    m5, m6, m7, m8 = st.columns(4)
    with m5:
        st.markdown(_metric_card("🔗", "Pingbacks", pingbacks, "#27ae60"), unsafe_allow_html=True)
    with m6:
        st.markdown(_metric_card("⚡", "Total Actions", total, "#2ecc71"), unsafe_allow_html=True)
    with m7:
        st.markdown(_metric_card("🔄", "Auto-Retries", retries, "#f39c12"), unsafe_allow_html=True)
    with m8:
        st.markdown(_metric_card("❌", "Failures", failures, "#e74c3c"), unsafe_allow_html=True)

    # Reset button
    _, reset_col = st.columns([3, 1])
    with reset_col:
        if st.button("🔄 Reset Counters", key="reset_metrics_btn"):
            db.reset_metrics()
            st.rerun()


def _metric_card(icon: str, label: str, value: int, color: str) -> str:
    """HTML metric card."""
    return f"""
    <div class="metric-card" style="border-top: 4px solid {color};">
        <div class="metric-icon">{icon}</div>
        <div class="metric-value" style="color: {color};">{value:,}</div>
        <div class="metric-label">{label}</div>
    </div>
    """



# ---------------------------------------------------------------------------
# 3. Worker Activity Grid
# ---------------------------------------------------------------------------

def _render_worker_grid() -> None:
    """5 worker status cards with last action."""
    worker_defs = [
        ("Worker_Contact_Sniper", "📧", "Contact Sniper"),
        ("Worker_Blog_Bomber", "📝", "Blog Bomber"),
        ("Worker_YouTube_Hijacker", "▶️", "YouTube Hijacker"),
        ("Worker_Pingback_Engine", "🔗", "Pingback Engine"),
        ("Worker_Reddit_Sniper", "🤖", "Reddit Sniper"),
    ]

    all_logs = db.get_recent_logs(limit=300)
    last_log_by_worker: dict[str, dict] = {}
    for log in reversed(all_logs):
        last_log_by_worker[log["worker"]] = log

    cols = st.columns(5)
    for col, (wkey, icon, label) in zip(cols, worker_defs):
        with col:
            last = last_log_by_worker.get(wkey)
            if last:
                status = last["status"]
                msg_short = last["message"][:60] + "…" if len(last["message"]) > 60 else last["message"]
                try:
                    ts = datetime.fromisoformat(last["timestamp"]).strftime("%H:%M:%S")
                except Exception:
                    ts = last["timestamp"]
            else:
                status = "idle"
                msg_short = "No activity yet."
                ts = "—"

            border_color = {
                "success": "#27ae60", "error": "#e74c3c",
                "info": "#95a5a6", "idle": "#bdc3c7",
                "retry": "#f39c12", "warning": "#f39c12",
            }.get(status, "#bdc3c7")

            status_dot = {
                "success": "🟢", "error": "🔴", "info": "🔵",
                "idle": "⚪", "retry": "🟡", "warning": "🟡",
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



# ---------------------------------------------------------------------------
# 4. Plugin Performance Reports
# ---------------------------------------------------------------------------

def _render_plugin_reports() -> None:
    """Detailed per-plugin performance table."""
    reports = db.get_plugin_reports()

    if not reports:
        st.info("No plugin activity yet. Start the engine to generate reports.")
        return

    for report in reports:
        plugin_name = report.get("plugin_name", "Unknown")
        total = report.get("total_attempts", 0)
        success = report.get("successful_attempts", 0)
        failed = report.get("failed_attempts", 0)
        retries = report.get("retry_count", 0)
        last_success = report.get("last_success_at", "—")
        last_failure = report.get("last_failure_at", "—")
        last_error = report.get("last_error", "—")

        # Success rate
        rate = (success / total * 100) if total > 0 else 0
        rate_color = "#27ae60" if rate >= 70 else "#f39c12" if rate >= 40 else "#e74c3c"

        # Platform breakdown
        try:
            platforms = json.loads(report.get("platforms_used", "{}"))
        except Exception:
            platforms = {}
        platform_str = " | ".join(f"{k}: {v}" for k, v in platforms.items()) if platforms else "—"

        # Format timestamps
        try:
            if last_success and last_success != "—":
                last_success = datetime.fromisoformat(last_success).strftime("%b %d, %I:%M %p")
        except Exception:
            pass
        try:
            if last_failure and last_failure != "—":
                last_failure = datetime.fromisoformat(last_failure).strftime("%b %d, %I:%M %p")
        except Exception:
            pass

        st.markdown(
            f"""
            <div style="background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:16px 20px;
                        margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                    <div>
                        <span style="font-weight:700;font-size:1rem;color:#1a1a2e;">🧩 {plugin_name}</span>
                    </div>
                    <div style="background:{rate_color};color:#fff;border-radius:20px;padding:4px 14px;
                                font-size:0.8rem;font-weight:600;">
                        {rate:.0f}% Success Rate
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;font-size:0.82rem;">
                    <div><span style="color:#888;">Total Attempts:</span><br><strong>{total}</strong></div>
                    <div><span style="color:#888;">Successful:</span><br><strong style="color:#27ae60;">{success}</strong></div>
                    <div><span style="color:#888;">Failed:</span><br><strong style="color:#e74c3c;">{failed}</strong></div>
                    <div><span style="color:#888;">Retries:</span><br><strong style="color:#f39c12;">{retries}</strong></div>
                </div>
                <div style="margin-top:10px;font-size:0.78rem;color:#666;">
                    <strong>Platforms:</strong> {platform_str}<br>
                    <strong>Last Success:</strong> {last_success} &nbsp;|&nbsp;
                    <strong>Last Failure:</strong> {last_failure}
                </div>
                {"<div style='margin-top:6px;font-size:0.76rem;color:#e74c3c;'><strong>Last Error:</strong> " + last_error + "</div>" if last_error and last_error != "—" else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )



# ---------------------------------------------------------------------------
# 5. Failed Attempts Report
# ---------------------------------------------------------------------------

def _render_failed_attempts() -> None:
    """Show every failed attempt with reason in Hindi/English."""
    fail_col1, fail_col2 = st.columns([3, 1])
    with fail_col1:
        fail_limit = st.selectbox(
            "Show recent failures:",
            options=[10, 25, 50, 100],
            index=1,
            key="fail_limit_select",
        )
    with fail_col2:
        if st.button("🗑️ Clear Reports", key="clear_attempts_btn"):
            db.clear_attempt_reports()
            st.rerun()

    failed = db.get_failed_attempts(limit=fail_limit)

    if not failed:
        st.success("✅ No failures recorded! Everything is running smoothly.")
        return

    st.markdown(
        f"<p style='font-size:0.82rem;color:#888;'>Showing {len(failed)} most recent failures</p>",
        unsafe_allow_html=True,
    )

    for attempt in failed:
        worker = attempt.get("worker", "")
        plugin_name = attempt.get("plugin_name", "—")
        target = attempt.get("target_url", "—")
        action = attempt.get("action_type", "—")
        attempt_num = attempt.get("attempt_number", 1)
        strategy = attempt.get("strategy_used", "default")
        reason_en = attempt.get("error_reason", "Unknown error")
        reason_hi = attempt.get("error_reason_hi", "")
        timestamp = attempt.get("timestamp", "")

        try:
            ts_display = datetime.fromisoformat(timestamp).strftime("%b %d, %I:%M:%S %p")
        except Exception:
            ts_display = timestamp

        # Truncate target URL for display
        target_display = target[:50] + "…" if len(target) > 50 else target

        st.markdown(
            f"""
            <div style="background:#fff8f8;border:1px solid #fde0e0;border-radius:10px;
                        padding:12px 16px;margin-bottom:8px;border-left:4px solid #e74c3c;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-weight:600;font-size:0.85rem;color:#c0392b;">
                        ❌ {worker.replace('Worker_', '')} → {action}
                    </span>
                    <span style="font-size:0.72rem;color:#999;">{ts_display}</span>
                </div>
                <div style="font-size:0.8rem;color:#333;margin-bottom:4px;">
                    <strong>🇬🇧 EN:</strong> {reason_en}
                </div>
                {"<div style='font-size:0.8rem;color:#555;margin-bottom:4px;'><strong>🇮🇳 HI:</strong> " + reason_hi + "</div>" if reason_hi else ""}
                <div style="font-size:0.74rem;color:#888;display:flex;gap:16px;flex-wrap:wrap;">
                    <span>🎯 Target: {target_display}</span>
                    <span>🧩 Plugin: {plugin_name}</span>
                    <span>🔄 Attempt #{attempt_num}</span>
                    <span>🎭 Strategy: {strategy}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )



# ---------------------------------------------------------------------------
# 6. Live Terminal Console
# ---------------------------------------------------------------------------

def _render_terminal_console() -> None:
    """Terminal-style log viewer with controls."""
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])

    with ctrl1:
        log_limit = st.slider(
            "Lines to display", min_value=20, max_value=500,
            value=100, step=20, key="log_limit_slider",
        )
    with ctrl2:
        if st.button("🔄 Refresh", key="refresh_logs_btn", use_container_width=True):
            st.rerun()
    with ctrl3:
        if st.button("🗑️ Clear Logs", key="clear_logs_btn", use_container_width=True):
            db.clear_all_logs()
            st.rerun()

    log_text = db.get_logs_as_text(limit=log_limit)
    log_count = db.get_log_count()

    st.markdown(
        f"<p class='log-count-label'>Showing <strong>{log_limit}</strong> of "
        f"<strong>{log_count}</strong> entries</p>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="terminal-box"><pre class="terminal-text">{log_text}</pre></div>',
        unsafe_allow_html=True,
    )

    st.download_button(
        label="⬇️ Export Log",
        data=db.get_logs_as_text(limit=2000),
        file_name=f"jarvis_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        key="export_logs_btn",
    )
