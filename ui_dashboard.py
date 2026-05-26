"""
ui_dashboard.py — Premium Live Dashboard
Shows: engine control, global metrics, worker grid, recent activity feed.
"""

import streamlit as st
from datetime import datetime
import database as db
from engine import EngineManager

PLATFORM_ICONS = {
    "contact_form": "📧",
    "blog_comment": "📝",
    "youtube":      "▶️",
    "pingback":     "🔗",
    "reddit":       "🤖",
}

WORKER_META = [
    ("Worker_Contact_Sniper",   "📧", "Contact Sniper",   "contact_form"),
    ("Worker_Blog_Bomber",      "📝", "Blog Bomber",      "blog_comment"),
    ("Worker_YouTube_Hijacker", "▶️",  "YouTube Hijacker", "youtube"),
    ("Worker_Pingback_Engine",  "🔗", "Pingback Engine",  "pingback"),
    ("Worker_Reddit_Sniper",    "🤖", "Reddit Sniper",    "reddit"),
]


def render_dashboard_tab(engine: EngineManager) -> None:
    # Auto-refresh when running
    if engine.is_running:
        st.markdown('<meta http-equiv="refresh" content="8">', unsafe_allow_html=True)

    _render_engine_control(engine)
    st.markdown("---")
    _render_global_metrics()
    st.markdown("---")
    _render_worker_grid(engine)
    st.markdown("---")
    _render_activity_feed()


# ─────────────────────────────────────────────────────────────────
# Engine Control Panel
# ─────────────────────────────────────────────────────────────────
def _render_engine_control(engine: EngineManager) -> None:
    is_running = engine.is_running
    now = datetime.now().strftime("%b %d, %Y  %I:%M:%S %p")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("""
        <div class="section-hdr">
            <span class="sicon">⚡</span>
            <span class="stitle">Engine Control</span>
        </div>
        """, unsafe_allow_html=True)

        if is_running:
            st.markdown(f"""
            <div style="background:rgba(0,255,136,0.05);border:1px solid rgba(0,255,136,0.3);
                        border-radius:12px;padding:18px 20px;margin-bottom:12px;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
                    <span style="font-size:1.5rem;">🟢</span>
                    <div>
                        <div style="font-size:1rem;font-weight:700;color:#00ff88;">All 5 Workers Active</div>
                        <div style="font-size:0.75rem;color:#8b949e;">Auto-refreshing every 8s • {now}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.3);
                        border-radius:12px;padding:18px 20px;margin-bottom:12px;">
                <div style="display:flex;align-items:center;gap:12px;">
                    <span style="font-size:1.5rem;">🔴</span>
                    <div>
                        <div style="font-size:1rem;font-weight:700;color:#ef4444;">Engine Stopped</div>
                        <div style="font-size:0.75rem;color:#8b949e;">As of {now}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.markdown("<div style='height:44px'></div>", unsafe_allow_html=True)
        if not is_running:
            keys    = db.get_all_api_keys()
            plugins = db.get_all_plugins()
            ready   = any(v.strip() for v in keys.values()) and len(plugins) > 0

            if not ready:
                st.warning("⚠️ Add a Groq key + plugin in Settings first.")
            else:
                if st.button("🚀  START ENGINE", type="primary", use_container_width=True):
                    engine.start()
                    st.rerun()
        else:
            if st.button("🛑  STOP ENGINE", use_container_width=True):
                engine.stop()
                st.rerun()


# ─────────────────────────────────────────────────────────────────
# Global Metrics Row
# ─────────────────────────────────────────────────────────────────
def _render_global_metrics() -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">📈</span>
        <span class="stitle">Global Metrics</span>
        <span class="sbadge">ALL TIME</span>
    </div>
    """, unsafe_allow_html=True)

    metrics  = db.get_metrics()
    platform = db.get_platform_totals()
    plugins  = db.get_all_plugins()
    total    = sum(metrics.values())

    c1, c2, c3, c4, c5 = st.columns(5)

    def _card(col, icon, label, value, color="#00ff88"):
        with col:
            st.markdown(f"""
            <div class="premium-card" style="text-align:center;padding:18px 12px;">
                <div style="font-size:1.6rem;margin-bottom:6px;">{icon}</div>
                <div class="card-value" style="font-size:1.8rem;color:{color};">{value:,}</div>
                <div class="card-title" style="margin-top:4px;">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    _card(c1, "⚡", "Total Actions",    total,                        "#00ff88")
    _card(c2, "📧", "Forms Filled",     metrics["forms_filled"],      "#3b82f6")
    _card(c3, "💬", "Comments Posted",  metrics["comments_posted"],   "#8b5cf6")
    _card(c4, "🔗", "Pingbacks Sent",   metrics["pingbacks_sent"],    "#f59e0b")
    _card(c5, "🧩", "Active Plugins",   len(plugins),                 "#ec4899")

    # Platform breakdown bar
    if total > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:0.75rem;font-weight:700;color:#8b949e;
                    text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">
            Actions by Platform
        </div>
        """, unsafe_allow_html=True)

        platform_order = [
            ("contact_form", "📧 Contact Forms", "#3b82f6"),
            ("blog_comment", "📝 Blog Comments", "#8b5cf6"),
            ("youtube",      "▶️ YouTube",        "#ef4444"),
            ("pingback",     "🔗 Pingbacks",      "#f59e0b"),
            ("reddit",       "🤖 Reddit",         "#00ff88"),
        ]
        cols = st.columns(5)
        for col, (key, label, color) in zip(cols, platform_order):
            cnt = platform.get(key, 0)
            pct = int(cnt / total * 100) if total > 0 else 0
            with col:
                st.markdown(f"""
                <div style="background:#161b22;border:1px solid #21262d;border-radius:10px;
                            padding:12px 14px;text-align:center;">
                    <div style="font-size:0.82rem;margin-bottom:4px;">{label}</div>
                    <div style="font-size:1.4rem;font-weight:800;color:{color};">{cnt:,}</div>
                    <div class="prog-bar-bg" style="margin-top:8px;">
                        <div class="prog-bar-fill" style="width:{pct}%;background:{color};"></div>
                    </div>
                    <div style="font-size:0.68rem;color:#8b949e;margin-top:4px;">{pct}%</div>
                </div>
                """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Worker Status Grid
# ─────────────────────────────────────────────────────────────────
def _render_worker_grid(engine: EngineManager) -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">🤖</span>
        <span class="stitle">Worker Status</span>
    </div>
    """, unsafe_allow_html=True)

    all_logs = db.get_recent_logs(300)
    last_by_worker = {}
    for log in reversed(all_logs):
        last_by_worker[log["worker"]] = log

    platform_totals = db.get_platform_totals()
    cols = st.columns(5)

    for col, (wkey, icon, label, platform) in zip(cols, WORKER_META):
        last    = last_by_worker.get(wkey)
        count   = platform_totals.get(platform, 0)
        active  = engine.is_running

        if last:
            status  = last["status"]
            msg     = last["message"][:52] + "…" if len(last["message"]) > 52 else last["message"]
            try:
                ts = datetime.fromisoformat(last["timestamp"]).strftime("%H:%M:%S")
            except Exception:
                ts = "—"
        else:
            status, msg, ts = "idle", "Waiting to start…", "—"

        border = {
            "success": "rgba(0,255,136,0.5)",
            "error":   "rgba(239,68,68,0.5)",
            "info":    "rgba(88,166,255,0.3)",
            "idle":    "#21262d",
        }.get(status, "#21262d")

        dot = {
            "success": '<span style="color:#00ff88;" class="pulse">●</span>',
            "error":   '<span style="color:#ef4444;">●</span>',
            "info":    '<span style="color:#58a6ff;" class="pulse">●</span>',
            "idle":    '<span style="color:#8b949e;">●</span>',
        }.get(status, "")

        with col:
            st.markdown(f"""
            <div class="worker-card {'active' if active else ''}"
                 style="border-color:{border};">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                    <span style="font-size:1rem;">{icon}</span>
                    <span class="wc-name">{label}</span>
                    {dot}
                </div>
                <div class="wc-status">{msg}</div>
                <div style="position:absolute;bottom:10px;left:14px;
                            font-size:0.62rem;color:#8b949e;">{ts}</div>
                <div class="wc-count">{count:,}</div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Recent Activity Feed
# ─────────────────────────────────────────────────────────────────
def _render_activity_feed() -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">📡</span>
        <span class="stitle">Recent Activity</span>
        <span class="sbadge">LIVE</span>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    logs = db.get_recent_logs(50)
    if not logs:
        st.markdown("""
        <div style="text-align:center;padding:40px;color:#8b949e;">
            <div style="font-size:2rem;margin-bottom:8px;">📭</div>
            No activity yet. Start the engine!
        </div>
        """, unsafe_allow_html=True)
        return

    rows_html = ""
    for entry in reversed(logs[-30:]):
        try:
            ts = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
        except Exception:
            ts = entry["timestamp"]

        color_map = {"success": "#00ff88", "error": "#ef4444", "info": "#58a6ff"}
        color = color_map.get(entry["status"], "#8b949e")
        icon  = {"success": "✅", "error": "❌", "info": "ℹ️"}.get(entry["status"], "•")

        rows_html += f"""
        <div style="display:flex;align-items:flex-start;gap:10px;
                    padding:8px 0;border-bottom:1px solid #161b22;">
            <span style="font-size:0.78rem;color:#8b949e;white-space:nowrap;
                         font-family:monospace;min-width:72px;">{ts}</span>
            <span style="font-size:0.78rem;">{icon}</span>
            <span style="font-size:0.72rem;color:#8b949e;white-space:nowrap;
                         min-width:160px;">[{entry['worker']}]</span>
            <span style="font-size:0.78rem;color:{color};">{entry['message']}</span>
        </div>
        """

    st.markdown(f"""
    <div style="background:#0d1117;border:1px solid #21262d;border-radius:10px;
                padding:16px 18px;max-height:340px;overflow-y:auto;">
        {rows_html}
    </div>
    """, unsafe_allow_html=True)
