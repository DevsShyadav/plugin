"""
ui_dashboard.py — Live Dashboard (White + Green theme)
"""
import streamlit as st
from datetime import datetime
import database as db
from engine import EngineManager

WORKER_META = [
    ("Worker_Contact_Sniper",   "📧", "Contact Sniper",   "contact_form"),
    ("Worker_Blog_Bomber",      "📝", "Blog Bomber",      "blog_comment"),
    ("Worker_YouTube_Hijacker", "▶️",  "YouTube Hijacker", "youtube"),
    ("Worker_Pingback_Engine",  "🔗", "Pingback Engine",  "pingback"),
    ("Worker_Reddit_Sniper",    "🤖", "Reddit Sniper",    "reddit"),
]

PLATFORM_COLORS = {
    "contact_form": "#27ae60",
    "blog_comment": "#3498db",
    "youtube":      "#e74c3c",
    "pingback":     "#f39c12",
    "reddit":       "#e67e22",
}


def render_dashboard_tab(engine: EngineManager) -> None:
    if engine.is_running:
        st.markdown('<meta http-equiv="refresh" content="8">', unsafe_allow_html=True)

    _engine_control(engine)
    st.markdown("---")
    _metrics_row()
    st.markdown("---")
    _worker_grid(engine)
    st.markdown("---")
    _activity_feed()


# ── Engine Control ────────────────────────────────────────────────
def _engine_control(engine: EngineManager) -> None:
    is_running = engine.is_running
    now = datetime.now().strftime("%b %d, %Y  %I:%M:%S %p")

    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">⚡</span>
        <span class="sec-title">Engine Control</span>
    </div>
    """, unsafe_allow_html=True)

    col_status, col_btn = st.columns([3, 1])

    with col_status:
        if is_running:
            st.markdown(f"""
            <div style="background:#f0faf4; border:1.5px solid #27ae60;
                        border-radius:12px; padding:18px 22px;">
                <div style="display:flex; align-items:center; gap:14px;">
                    <span style="font-size:2rem;">🟢</span>
                    <div>
                        <div style="font-size:1rem; font-weight:700; color:#27ae60;">
                            All 5 Workers Running
                        </div>
                        <div style="font-size:0.75rem; color:#888; margin-top:2px;">
                            Auto-refreshing every 8s &nbsp;·&nbsp; {now}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:#fff8f8; border:1.5px solid #e74c3c;
                        border-radius:12px; padding:18px 22px;">
                <div style="display:flex; align-items:center; gap:14px;">
                    <span style="font-size:2rem;">🔴</span>
                    <div>
                        <div style="font-size:1rem; font-weight:700; color:#e74c3c;">
                            Engine Stopped
                        </div>
                        <div style="font-size:0.75rem; color:#888; margin-top:2px;">
                            Last checked: {now}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_btn:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        keys    = db.get_all_api_keys()
        plugins = db.get_all_plugins()
        ready   = any(v.strip() for v in keys.values()) and len(plugins) > 0

        if not is_running:
            if not ready:
                st.warning("Add a Groq key + plugin in Settings first.")
            else:
                if st.button("🚀 START ENGINE", type="primary", use_container_width=True):
                    engine.start()
                    st.rerun()
        else:
            if st.button("🛑 STOP ENGINE", use_container_width=True):
                engine.stop()
                st.rerun()


# ── Metrics Row ───────────────────────────────────────────────────
def _metrics_row() -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">📈</span>
        <span class="sec-title">Success Metrics</span>
        <span class="sec-badge">ALL TIME</span>
    </div>
    """, unsafe_allow_html=True)

    m        = db.get_metrics()
    platform = db.get_platform_totals()
    plugins  = db.get_all_plugins()
    total    = sum(m.values())

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "⚡", "Total Actions",   total,               "#27ae60"),
        (c2, "📧", "Forms Filled",    m["forms_filled"],   "#3498db"),
        (c3, "💬", "Comments Posted", m["comments_posted"],"#9b59b6"),
        (c4, "🔗", "Pingbacks Sent",  m["pingbacks_sent"], "#e67e22"),
        (c5, "🧩", "Active Plugins",  len(plugins),        "#1abc9c"),
    ]
    for col, icon, label, val, color in cards:
        with col:
            st.markdown(f"""
            <div class="wg-card" style="border-top:3px solid {color}; text-align:center;">
                <div class="card-icon">{icon}</div>
                <div class="card-value" style="color:{color};">{val:,}</div>
                <div class="card-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    # Platform breakdown
    if total > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:0.72rem; font-weight:700; color:#aaa;
                    text-transform:uppercase; letter-spacing:1px; margin-bottom:10px;">
            Breakdown by Platform
        </div>
        """, unsafe_allow_html=True)

        platforms = [
            ("contact_form", "📧 Contact Forms", "#27ae60"),
            ("blog_comment", "📝 Blog Comments", "#3498db"),
            ("youtube",      "▶️  YouTube",       "#e74c3c"),
            ("pingback",     "🔗 Pingbacks",      "#e67e22"),
            ("reddit",       "🤖 Reddit",         "#9b59b6"),
        ]
        cols = st.columns(5)
        for col, (key, label, color) in zip(cols, platforms):
            cnt = platform.get(key, 0)
            pct = int(cnt / total * 100) if total > 0 else 0
            with col:
                st.markdown(f"""
                <div style="background:#FFFFFF; border:1.5px solid #e8f8f0;
                            border-radius:10px; padding:12px; text-align:center;">
                    <div style="font-size:0.8rem; margin-bottom:4px;">{label}</div>
                    <div style="font-size:1.5rem; font-weight:800;
                                color:{color}; margin-bottom:6px;">{cnt:,}</div>
                    <div class="prog-bg">
                        <div class="prog-fill" style="width:{pct}%;
                             background:{color};"></div>
                    </div>
                    <div style="font-size:0.68rem; color:#aaa; margin-top:4px;">{pct}%</div>
                </div>
                """, unsafe_allow_html=True)


# ── Worker Grid ───────────────────────────────────────────────────
def _worker_grid(engine: EngineManager) -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">🤖</span>
        <span class="sec-title">Worker Status</span>
    </div>
    """, unsafe_allow_html=True)

    all_logs = db.get_recent_logs(300)
    last_by  = {}
    for log in reversed(all_logs):
        last_by[log["worker"]] = log

    platform_totals = db.get_platform_totals()
    cols = st.columns(5)

    for col, (wkey, icon, label, platform) in zip(cols, WORKER_META):
        last   = last_by.get(wkey)
        count  = platform_totals.get(platform, 0)

        if last:
            status = last["status"]
            msg    = last["message"][:50] + "…" if len(last["message"]) > 50 else last["message"]
            try:
                ts = datetime.fromisoformat(last["timestamp"]).strftime("%H:%M:%S")
            except Exception:
                ts = "—"
        else:
            status, msg, ts = "idle", "Waiting to start…", "—"

        border = {
            "success": "#27ae60",
            "error":   "#e74c3c",
            "info":    "#3498db",
            "idle":    "#e8e8e8",
        }.get(status, "#e8e8e8")

        dot_color = {
            "success": "#27ae60",
            "error":   "#e74c3c",
            "info":    "#3498db",
            "idle":    "#ccc",
        }.get(status, "#ccc")

        pulse_class = "pulse" if status in ("success", "info") and engine.is_running else ""

        with col:
            st.markdown(f"""
            <div class="wg-card" style="border-top:3px solid {border};
                        min-height:140px; position:relative; padding:14px;">
                <div style="display:flex; align-items:center; gap:6px; margin-bottom:8px;">
                    <span style="font-size:1rem;">{icon}</span>
                    <span style="font-size:0.78rem; font-weight:700;
                                 color:#1a1a2e; flex:1;">{label}</span>
                    <span style="color:{dot_color}; font-size:0.7rem;"
                          class="{pulse_class}">●</span>
                </div>
                <div style="font-size:0.73rem; color:#666;
                            line-height:1.4; margin-bottom:8px;">{msg}</div>
                <div style="position:absolute; bottom:10px; left:14px;
                            font-size:0.65rem; color:#aaa;">{ts}</div>
                <div style="position:absolute; bottom:10px; right:14px;
                            font-size:1.3rem; font-weight:800;
                            color:#27ae60;">{count:,}</div>
            </div>
            """, unsafe_allow_html=True)


# ── Activity Feed ─────────────────────────────────────────────────
def _activity_feed() -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">📡</span>
        <span class="sec-title">Recent Activity</span>
        <span class="sec-badge">LIVE</span>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    logs = db.get_recent_logs(40)
    if not logs:
        st.info("No activity yet. Start the engine to begin.")
        return

    rows = ""
    for entry in reversed(logs[-30:]):
        try:
            ts = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
        except Exception:
            ts = entry["timestamp"]

        color = {"success": "#27ae60", "error": "#e74c3c", "info": "#3498db"}.get(
            entry["status"], "#888")
        icon  = {"success": "✅", "error": "❌", "info": "ℹ️"}.get(entry["status"], "•")
        msg   = entry["message"].replace("<", "&lt;").replace(">", "&gt;")

        rows += f"""
        <div style="display:grid; grid-template-columns:72px 20px 175px 1fr;
                    gap:8px; padding:7px 0; border-bottom:1px solid #f5f5f5;
                    align-items:start;">
            <span style="font-size:0.72rem; color:#aaa; font-family:monospace;">{ts}</span>
            <span style="font-size:0.78rem;">{icon}</span>
            <span style="font-size:0.7rem; color:#aaa;">[{entry['worker'][:22]}]</span>
            <span style="font-size:0.78rem; color:{color};">{msg}</span>
        </div>
        """

    st.markdown(f"""
    <div style="background:#FFFFFF; border:1.5px solid #e8f8f0;
                border-radius:10px; padding:16px 18px;
                max-height:320px; overflow-y:auto;">
        {rows}
    </div>
    """, unsafe_allow_html=True)
