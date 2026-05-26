"""
app.py — AI Marketing Engine
Premium dark + green theme with sidebar navigation.
"""

import os
import streamlit as st
import database as db
from engine import EngineManager
from ui_dashboard import render_dashboard_tab
from ui_settings import render_settings_tab

IS_HF_SPACE: bool = bool(os.environ.get("SPACE_ID"))

st.set_page_config(
    page_title="AI Marketing Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
# PREMIUM CSS — Dark #0f1117 + Neon Green #00ff88
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── GLOBAL ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

.stApp, .main .block-container,
div[data-testid="stAppViewContainer"] {
    background-color: #0f1117 !important;
    color: #e2e8f0 !important;
}
.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1600px !important;
}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0e14 0%, #0f1117 100%) !important;
    border-right: 1px solid #1e2530 !important;
    min-width: 260px !important;
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stRadio label {
    font-size: 0.9rem !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    display: block !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(0,255,136,0.08) !important;
    color: #00ff88 !important;
}

/* ── TABS ── */
div[data-testid="stTabs"] button[role="tab"] {
    background: #161b22 !important;
    color: #8b949e !important;
    border: 1px solid #21262d !important;
    border-radius: 8px 8px 0 0 !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 10px 20px !important;
    transition: all 0.2s !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: #0d1117 !important;
    color: #00ff88 !important;
    border-bottom: 2px solid #00ff88 !important;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #00ff88 !important;
    background: rgba(0,255,136,0.05) !important;
}

/* ── BUTTONS ── */
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #00c96b, #00ff88) !important;
    color: #0a0e14 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.4rem !important;
    box-shadow: 0 0 20px rgba(0,255,136,0.3) !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 0 30px rgba(0,255,136,0.5) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stButton"] > button:not([kind="primary"]) {
    background: #161b22 !important;
    color: #00ff88 !important;
    border: 1px solid #00ff88 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    background: rgba(0,255,136,0.1) !important;
    box-shadow: 0 0 15px rgba(0,255,136,0.2) !important;
}

/* ── INPUTS ── */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] > div {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-size: 0.88rem !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: #00ff88 !important;
    box-shadow: 0 0 0 3px rgba(0,255,136,0.15) !important;
}

/* ── METRICS ── */
div[data-testid="stMetric"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 12px !important;
    padding: 16px !important;
}
div[data-testid="stMetric"] label { color: #8b949e !important; font-size: 0.8rem !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #00ff88 !important;
    font-size: 1.8rem !important;
    font-weight: 800 !important;
}

/* ── DATAFRAME ── */
div[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden !important; }
div[data-testid="stDataFrame"] th {
    background: #161b22 !important;
    color: #00ff88 !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
div[data-testid="stDataFrame"] td {
    background: #0d1117 !important;
    color: #e2e8f0 !important;
    font-size: 0.83rem !important;
    border-color: #21262d !important;
}

/* ── EXPANDER ── */
div[data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 10px !important;
}
div[data-testid="stExpander"] summary { color: #e2e8f0 !important; font-weight: 600 !important; }

/* ── ALERTS ── */
div[data-testid="stAlert"] { border-radius: 8px !important; font-size: 0.87rem !important; }
div[data-testid="stAlert"][data-baseweb="notification"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
}

/* ── DIVIDER ── */
hr { border-color: #21262d !important; margin: 0.5rem 0 1rem 0 !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #00ff88; border-radius: 3px; opacity: 0.6; }

/* ── HIDE BRANDING ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── CARD COMPONENT ── */
.premium-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 12px;
    transition: all 0.2s;
}
.premium-card:hover {
    border-color: #00ff88;
    box-shadow: 0 0 20px rgba(0,255,136,0.1);
}
.premium-card .card-title {
    font-size: 0.78rem;
    font-weight: 700;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}
.premium-card .card-value {
    font-size: 2.2rem;
    font-weight: 800;
    color: #00ff88;
    line-height: 1;
    margin-bottom: 4px;
}
.premium-card .card-sub {
    font-size: 0.75rem;
    color: #8b949e;
}

/* ── STATUS BADGE ── */
.badge-running {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(0,255,136,0.1);
    border: 1px solid #00ff88;
    color: #00ff88;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.82rem;
    font-weight: 600;
}
.badge-stopped {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(239,68,68,0.1);
    border: 1px solid #ef4444;
    color: #ef4444;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.82rem;
    font-weight: 600;
}
.pulse { animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* ── TERMINAL ── */
.terminal-box {
    background: #010409;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px 18px;
    max-height: 380px;
    overflow-y: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    line-height: 1.7;
    color: #8b949e;
}
.terminal-box .log-success { color: #00ff88; }
.terminal-box .log-error   { color: #ef4444; }
.terminal-box .log-info    { color: #58a6ff; }

/* ── PLUGIN ROW ── */
.plugin-row {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: border-color 0.2s;
}
.plugin-row:hover { border-color: #00ff88; }
.plugin-badge {
    background: rgba(0,255,136,0.1);
    color: #00ff88;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    white-space: nowrap;
}

/* ── PROGRESS BAR ── */
.prog-bar-bg {
    background: #21262d;
    border-radius: 4px;
    height: 6px;
    width: 100%;
    overflow: hidden;
}
.prog-bar-fill {
    height: 6px;
    border-radius: 4px;
    background: linear-gradient(90deg, #00c96b, #00ff88);
}

/* ── WORKER CARD ── */
.worker-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 14px;
    height: 120px;
    position: relative;
    overflow: hidden;
}
.worker-card.active { border-color: rgba(0,255,136,0.4); }
.worker-card .wc-name { font-size: 0.75rem; font-weight: 700; color: #e2e8f0; }
.worker-card .wc-status { font-size: 0.68rem; color: #8b949e; margin-top: 4px; }
.worker-card .wc-count {
    position: absolute; bottom: 12px; right: 12px;
    font-size: 1.4rem; font-weight: 800; color: #00ff88;
}

/* ── SECTION HEADER ── */
.section-hdr {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #21262d;
}
.section-hdr .sicon { font-size: 1.1rem; }
.section-hdr .stitle {
    font-size: 1rem; font-weight: 700; color: #e2e8f0;
}
.section-hdr .sbadge {
    background: rgba(0,255,136,0.1);
    color: #00ff88;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-left: auto;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────
def _bootstrap() -> EngineManager:
    db.init_db()
    if "engine" not in st.session_state:
        st.session_state["engine"] = EngineManager()
    return st.session_state["engine"]


# ─────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────
def _render_sidebar(engine: EngineManager) -> str:
    with st.sidebar:
        # Logo
        st.markdown("""
        <div style="padding:20px 10px 24px;">
            <div style="font-size:1.6rem;font-weight:800;color:#00ff88;letter-spacing:-1px;">
                🚀 MarketEngine
            </div>
            <div style="font-size:0.72rem;color:#8b949e;margin-top:2px;">
                AI-Powered 24/7 Lead Generation
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Engine status
        is_running = engine.is_running
        if is_running:
            st.markdown('<div class="badge-running"><span class="pulse">●</span> ENGINE LIVE</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="badge-stopped">● ENGINE STOPPED</div>',
                        unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Navigation
        st.markdown("<div style='font-size:0.7rem;color:#8b949e;font-weight:700;letter-spacing:1px;padding:0 4px;margin-bottom:6px;'>NAVIGATION</div>",
                    unsafe_allow_html=True)
        page = st.radio(
            "",
            ["📊  Dashboard", "🔌  Plugin Analytics", "⚙️  Settings", "📋  Live Logs"],
            label_visibility="collapsed",
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Quick stats
        metrics = db.get_metrics()
        total = sum(metrics.values())
        st.markdown(f"""
        <div style="background:#0a0e14;border:1px solid #21262d;border-radius:10px;padding:14px;">
            <div style="font-size:0.68rem;color:#8b949e;font-weight:700;letter-spacing:1px;margin-bottom:10px;">QUICK STATS</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:0.75rem;color:#8b949e;">Total Actions</span>
                <span style="font-size:0.75rem;color:#00ff88;font-weight:700;">{total:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:0.75rem;color:#8b949e;">Forms Filled</span>
                <span style="font-size:0.75rem;color:#e2e8f0;font-weight:600;">{metrics['forms_filled']:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:0.75rem;color:#8b949e;">Comments</span>
                <span style="font-size:0.75rem;color:#e2e8f0;font-weight:600;">{metrics['comments_posted']:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
                <span style="font-size:0.75rem;color:#8b949e;">Pingbacks</span>
                <span style="font-size:0.75rem;color:#e2e8f0;font-weight:600;">{metrics['pingbacks_sent']:,}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Active Groq key
        keys = db.get_all_api_keys()
        active_keys = sum(1 for v in keys.values() if v.strip())
        st.markdown(f"""
        <div style="font-size:0.72rem;color:#8b949e;padding:0 2px;">
            🔑 <span style="color:#e2e8f0;">{active_keys}/3</span> Groq keys active<br>
            🤖 <span style="color:#00ff88;font-family:monospace;font-size:0.68rem;">llama-3.3-70b-versatile</span>
        </div>
        """, unsafe_allow_html=True)

    return page


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────
def main():
    engine = _bootstrap()
    page = _render_sidebar(engine)

    # HF welcome banner
    if IS_HF_SPACE:
        db.init_db()
        keys = db.get_all_api_keys()
        if not any(v.strip() for v in keys.values()):
            st.info("👋 **Welcome!** Go to ⚙️ Settings → add your [Groq API key](https://console.groq.com) → add a plugin → Start Engine.")

    # Page router
    clean = page.split("  ")[-1]
    if clean == "Dashboard":
        render_dashboard_tab(engine)
    elif clean == "Plugin Analytics":
        from ui_analytics import render_analytics_tab
        render_analytics_tab()
    elif clean == "Settings":
        render_settings_tab(engine)
    elif clean == "Live Logs":
        from ui_logs import render_logs_tab
        render_logs_tab()


if __name__ == "__main__":
    main()
