"""
app.py
======
JARVIS AI Marketing Engine — Main Entry Point

Silicon Valley Premium White + Green UI
Jarvis-level 24/7 Automated Marketing System

Run with:
    streamlit run app.py

Architecture:
    app.py          — Page config, CSS, header, tab router
    ui_settings.py  — Settings & Configuration tab
    ui_dashboard.py — Live Dashboard & Reports tab
    engine.py       — EngineManager + RetryManager + ErrorTranslator
    workers.py      — 5 async background workers (aggressive scheduling)
    groq_engine.py  — Groq API + strategy-aware content generation
    database.py     — SQLite with detailed reporting
"""

import streamlit as st

import database as db
from engine import EngineManager
from ui_settings import render_settings_tab
from ui_dashboard import render_dashboard_tab


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="JARVIS AI Marketing Engine",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)



# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS — Silicon Valley Premium White + Green Theme
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ══════════ GLOBAL ══════════ */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stApp, .main .block-container,
section[data-testid="stSidebar"],
div[data-testid="stAppViewContainer"] {
    background-color: #FAFBFC !important;
}
.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1440px !important;
}

/* ══════════ HEADER ══════════ */
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.1rem 1.8rem;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 14px;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.15);
    border: 1px solid rgba(39,174,96,0.3);
}
.app-header-left {
    display: flex;
    align-items: center;
    gap: 14px;
}
.app-header-logo {
    font-size: 2.2rem;
    line-height: 1;
    filter: drop-shadow(0 0 8px rgba(46,204,113,0.5));
}
.app-header-title {
    color: #FFFFFF;
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0;
    background: linear-gradient(90deg, #2ecc71, #27ae60, #1abc9c);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.app-header-subtitle {
    color: rgba(255,255,255,0.7);
    font-size: 0.76rem;
    margin: 0;
    font-weight: 400;
    letter-spacing: 0.3px;
}
.app-header-status {
    background: rgba(46,204,113,0.15);
    border: 1px solid rgba(46,204,113,0.4);
    border-radius: 24px;
    padding: 8px 18px;
    color: #2ecc71;
    font-size: 0.82rem;
    font-weight: 600;
    backdrop-filter: blur(8px);
}

/* ══════════ TABS ══════════ */
div[data-testid="stTabs"] button[role="tab"] {
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    color: #555 !important;
    padding: 12px 24px !important;
    border-radius: 10px 10px 0 0 !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #27ae60 !important;
    background: rgba(46,204,113,0.06) !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #27ae60 !important;
    border-bottom: 3px solid #27ae60 !important;
    background: rgba(46,204,113,0.04) !important;
}
</style>
"""


CUSTOM_CSS_2 = """
<style>
/* ══════════ BUTTONS ══════════ */
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #27ae60, #2ecc71) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.6rem 1.4rem !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 15px rgba(46,204,113,0.3) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(46,204,113,0.45) !important;
}
div[data-testid="stButton"] > button[kind="secondary"],
div[data-testid="stButton"] > button:not([kind="primary"]) {
    background: #FFFFFF !important;
    color: #27ae60 !important;
    border: 1.5px solid #27ae60 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover,
div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    background: rgba(46,204,113,0.06) !important;
    transform: translateY(-1px) !important;
}

/* ══════════ INPUTS ══════════ */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    border: 1.5px solid #e0e0e0 !important;
    border-radius: 10px !important;
    font-size: 0.87rem !important;
    background: #FFFFFF !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: #27ae60 !important;
    box-shadow: 0 0 0 3px rgba(46,204,113,0.1) !important;
}

/* ══════════ SECTIONS ══════════ */
hr.section-divider {
    border: none !important;
    border-top: 2px solid #f0f0f0 !important;
    margin: 0.3rem 0 1.2rem 0 !important;
}
p.sub-label {
    color: #888;
    font-size: 0.83rem;
    margin-top: -0.5rem;
    margin-bottom: 1rem;
}

/* ══════════ PLUGIN TABLE ══════════ */
span.plugin-id {
    display: inline-block;
    background: #e8f8f0;
    color: #27ae60;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.76rem;
    font-weight: 700;
}
span.plugin-name { font-weight: 600; font-size: 0.88rem; color: #1a1a2e; }
a.plugin-link {
    color: #27ae60 !important;
    font-size: 0.82rem;
    text-decoration: none !important;
    word-break: break-all;
}
a.plugin-link:hover { text-decoration: underline !important; }
span.plugin-desc { color: #666; font-size: 0.82rem; }
div.plugin-row-divider { border-top: 1px solid #f5f5f5; margin: 6px 0; }
p.plugin-count {
    color: #aaa; font-size: 0.78rem;
    text-align: right; margin-top: 0.5rem;
}
</style>
"""


CUSTOM_CSS_3 = """
<style>
/* ══════════ MASTER SWITCH ══════════ */
div.master-switch-card {
    display: flex;
    justify-content: center;
    margin-bottom: 1rem;
}
div.engine-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 14px 36px;
    border-radius: 40px;
    font-size: 1.05rem;
    font-weight: 600;
}
div.status-running {
    background: linear-gradient(135deg, #e8f8f0, #d4f5e2);
    color: #1e8449;
    border: 2px solid #27ae60;
    box-shadow: 0 0 0 4px rgba(46,204,113,0.12), 0 4px 15px rgba(46,204,113,0.2);
}
div.status-stopped {
    background: #fdf2f2;
    color: #c0392b;
    border: 2px solid #e74c3c;
    box-shadow: 0 2px 8px rgba(231,76,60,0.1);
}

/* ══════════ WORKER ROWS ══════════ */
div.worker-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: 8px;
    background: #f8fffe;
    border: 1px solid #e8f8f0;
    margin-bottom: 6px;
    font-size: 0.84rem;
}
span.worker-dot {
    color: #27ae60;
    font-size: 0.6rem;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}
span.worker-name { font-weight: 600; color: #1a1a2e; }
span.worker-desc { color: #777; }
span.worker-icon { font-size: 1rem; }

/* ══════════ DASHBOARD BANNER ══════════ */
div.dashboard-banner {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px 24px;
    border-radius: 12px;
    font-size: 0.92rem;
}
div.banner-running {
    background: linear-gradient(135deg, #e8f8f0, #d4f5e2);
    border: 1.5px solid #27ae60;
    box-shadow: 0 2px 12px rgba(46,204,113,0.1);
}
div.banner-stopped {
    background: #fdf2f2;
    border: 1.5px solid #e74c3c;
}
span.banner-title { font-size: 1rem; font-weight: 600; flex: 1; }
span.banner-time { color: #666; font-size: 0.78rem; }
span.banner-hint {
    background: rgba(0,0,0,0.05);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.76rem;
    color: #555;
}

/* ══════════ METRIC CARDS ══════════ */
div.metric-card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 20px 16px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    min-height: 125px;
}
div.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
}
div.metric-icon { font-size: 1.5rem; margin-bottom: 6px; }
div.metric-value {
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 4px;
}
div.metric-label {
    font-size: 0.74rem;
    font-weight: 600;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

/* ══════════ WORKER CARDS ══════════ */
div.worker-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    min-height: 105px;
    position: relative;
}
div.wc-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
}
span.wc-icon { font-size: 1rem; }
span.wc-label { font-size: 0.76rem; font-weight: 700; color: #1a1a2e; flex: 1; }
span.wc-dot { font-size: 0.8rem; }
div.wc-msg { font-size: 0.73rem; color: #555; line-height: 1.4; margin-bottom: 8px; }
div.wc-ts {
    font-size: 0.66rem; color: #aaa;
    position: absolute; bottom: 10px; right: 12px;
}
</style>
"""


CUSTOM_CSS_4 = """
<style>
/* ══════════ TERMINAL ══════════ */
div.terminal-box {
    background: #0d1117;
    border-radius: 12px;
    border: 1px solid #30363d;
    padding: 18px 22px;
    max-height: 450px;
    overflow-y: auto;
    box-shadow: inset 0 2px 8px rgba(0,0,0,0.3);
}
pre.terminal-text {
    color: #c9d1d9;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace !important;
    font-size: 0.76rem !important;
    line-height: 1.65;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
}
p.log-count-label {
    color: #aaa;
    font-size: 0.78rem;
    margin-bottom: 6px;
}

/* ══════════ ALERTS ══════════ */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
    font-size: 0.86rem !important;
}

/* ══════════ SLIDER ══════════ */
div[data-testid="stSlider"] div[role="slider"] {
    background-color: #27ae60 !important;
}

/* ══════════ SCROLLBAR ══════════ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #f8f8f8; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #27ae60; border-radius: 3px; }
div.terminal-box::-webkit-scrollbar-track { background: #161b22; }
div.terminal-box::-webkit-scrollbar-thumb { background: #30363d; }

/* ══════════ HIDE STREAMLIT BRANDING ══════════ */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap() -> EngineManager:
    """Initialize DB and create EngineManager singleton."""
    db.init_db()
    if "engine" not in st.session_state:
        st.session_state["engine"] = EngineManager()
    return st.session_state["engine"]


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

def _render_header(engine: EngineManager) -> None:
    """Render the Jarvis branded header."""
    status_text = engine.get_status_line()
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-header-left">
                <span class="app-header-logo">🤖</span>
                <div>
                    <p class="app-header-title">JARVIS AI Marketing Engine</p>
                    <p class="app-header-subtitle">
                        24/7 Autonomous Lead Generation &amp; Plugin Promotion System
                    </p>
                </div>
            </div>
            <div class="app-header-status">{status_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # Inject all CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(CUSTOM_CSS_2, unsafe_allow_html=True)
    st.markdown(CUSTOM_CSS_3, unsafe_allow_html=True)
    st.markdown(CUSTOM_CSS_4, unsafe_allow_html=True)

    # Bootstrap
    engine = _bootstrap()

    # Header
    _render_header(engine)

    # Main tabs
    tab_settings, tab_dashboard = st.tabs([
        "⚙️  Settings & Configuration",
        "📊  Live Dashboard & Reports",
    ])

    with tab_settings:
        render_settings_tab(engine)

    with tab_dashboard:
        render_dashboard_tab(engine)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
