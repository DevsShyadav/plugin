"""
app.py
======
Main entry point for the 24/7 AI Marketing Dashboard.

Run with:
    streamlit run app.py

Architecture recap:
    • app.py          — Streamlit page config, CSS injection, tab router
    • ui_settings.py  — Tab 1: Settings & Configuration
    • ui_dashboard.py — Tab 2: Live Dashboard & Logs
    • engine.py       — EngineManager (asyncio thread bridge)
    • workers.py      — 5 async background workers
    • groq_engine.py  — Groq key rotator + prompt builders
    • database.py     — SQLite persistence layer

Session state keys used:
    st.session_state["engine"]  — singleton EngineManager instance
"""

import os

import streamlit as st

import database as db
from engine import EngineManager
from ui_settings import render_settings_tab
from ui_dashboard import render_dashboard_tab

# ── Hugging Face environment detection ───────────────────────────────────────
# HF Spaces sets the SPACE_ID environment variable automatically.
# We use this to show a friendly first-run banner guiding users to add keys.
IS_HF_SPACE: bool = bool(os.environ.get("SPACE_ID"))


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be the very first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Marketing Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS  — White + Green theme
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>

/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ══════════════════════════════════════════════════
   GLOBAL RESET & BASE
══════════════════════════════════════════════════ */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Force white background everywhere */
.stApp,
.main .block-container,
section[data-testid="stSidebar"],
div[data-testid="stAppViewContainer"] {
    background-color: #FFFFFF !important;
}

/* Remove default top padding */
.main .block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px !important;
}

/* ══════════════════════════════════════════════════
   HEADER / LOGO BAR
══════════════════════════════════════════════════ */
.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 15px rgba(46, 204, 113, 0.25);
}
.app-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}
.app-header-logo {
    font-size: 2rem;
    line-height: 1;
}
.app-header-title {
    color: #FFFFFF;
    font-size: 1.45rem;
    font-weight: 700;
    letter-spacing: -0.3px;
    margin: 0;
}
.app-header-subtitle {
    color: rgba(255,255,255,0.85);
    font-size: 0.78rem;
    margin: 0;
    font-weight: 400;
}
.app-header-status {
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.4);
    border-radius: 20px;
    padding: 6px 16px;
    color: #FFFFFF;
    font-size: 0.82rem;
    font-weight: 500;
    backdrop-filter: blur(4px);
}

/* ══════════════════════════════════════════════════
   STREAMLIT TABS
══════════════════════════════════════════════════ */
div[data-testid="stTabs"] button[role="tab"] {
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    color: #555 !important;
    padding: 10px 20px !important;
    border-radius: 8px 8px 0 0 !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #27ae60 !important;
    background: rgba(46, 204, 113, 0.08) !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #27ae60 !important;
    border-bottom: 3px solid #27ae60 !important;
    background: rgba(46, 204, 113, 0.06) !important;
}

/* ══════════════════════════════════════════════════
   BUTTONS
══════════════════════════════════════════════════ */
/* Primary green button */
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #27ae60, #2ecc71) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.55rem 1.2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(46, 204, 113, 0.3) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 15px rgba(46, 204, 113, 0.45) !important;
}

/* Secondary / default buttons */
div[data-testid="stButton"] > button[kind="secondary"],
div[data-testid="stButton"] > button:not([kind="primary"]) {
    background: #FFFFFF !important;
    color: #27ae60 !important;
    border: 1.5px solid #27ae60 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover,
div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    background: rgba(46, 204, 113, 0.08) !important;
}

/* Stop engine button — red accent */
div[data-testid="stButton"] > button[kind="secondary"]#engine_stop_btn {
    color: #e74c3c !important;
    border-color: #e74c3c !important;
}

/* ══════════════════════════════════════════════════
   INPUTS & TEXT AREAS
══════════════════════════════════════════════════ */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    border: 1.5px solid #e0e0e0 !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    background: #fafafa !important;
    transition: border-color 0.2s ease !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: #27ae60 !important;
    box-shadow: 0 0 0 3px rgba(46, 204, 113, 0.12) !important;
    background: #FFFFFF !important;
}

/* ══════════════════════════════════════════════════
   SECTION DIVIDER
══════════════════════════════════════════════════ */
hr.section-divider {
    border: none !important;
    border-top: 2px solid #f0f0f0 !important;
    margin: 0.3rem 0 1.2rem 0 !important;
}

/* ══════════════════════════════════════════════════
   SUB-LABELS
══════════════════════════════════════════════════ */
p.sub-label {
    color: #888;
    font-size: 0.83rem;
    margin-top: -0.5rem;
    margin-bottom: 1rem;
}

/* ══════════════════════════════════════════════════
   PLUGIN TABLE ROWS
══════════════════════════════════════════════════ */
span.plugin-id {
    display: inline-block;
    background: #f0faf4;
    color: #27ae60;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 0.78rem;
    font-weight: 700;
}
span.plugin-name {
    font-weight: 600;
    font-size: 0.88rem;
    color: #1a1a2e;
}
a.plugin-link {
    color: #27ae60 !important;
    font-size: 0.82rem;
    text-decoration: none !important;
    word-break: break-all;
}
a.plugin-link:hover { text-decoration: underline !important; }
span.plugin-desc {
    color: #666;
    font-size: 0.82rem;
}
div.plugin-row-divider {
    border-top: 1px solid #f5f5f5;
    margin: 6px 0;
}
p.plugin-count {
    color: #aaa;
    font-size: 0.78rem;
    text-align: right;
    margin-top: 0.5rem;
}

/* ══════════════════════════════════════════════════
   MASTER SWITCH CARD
══════════════════════════════════════════════════ */
div.master-switch-card {
    display: flex;
    justify-content: center;
    margin-bottom: 1rem;
}
div.engine-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 14px 32px;
    border-radius: 40px;
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: 0.2px;
}
div.status-running {
    background: linear-gradient(135deg, #e8f8f0, #d4f5e2);
    color: #1e8449;
    border: 2px solid #27ae60;
    box-shadow: 0 0 0 4px rgba(46, 204, 113, 0.12);
}
div.status-stopped {
    background: #fdf2f2;
    color: #c0392b;
    border: 2px solid #e74c3c;
}

/* ── Active worker checklist ── */
div.worker-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 6px;
    background: #f9fffe;
    border: 1px solid #e8f8f0;
    margin-bottom: 6px;
    font-size: 0.85rem;
}
span.worker-dot {
    color: #27ae60;
    font-size: 0.65rem;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.3; }
}
span.worker-name  { font-weight: 600; color: #1a1a2e; }
span.worker-desc  { color: #777; }
span.worker-icon  { font-size: 1rem; }

/* ══════════════════════════════════════════════════
   DASHBOARD BANNER
══════════════════════════════════════════════════ */
div.dashboard-banner {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 24px;
    border-radius: 10px;
    font-size: 0.92rem;
}
div.banner-running {
    background: linear-gradient(135deg, #e8f8f0, #d4f5e2);
    border: 1.5px solid #27ae60;
}
div.banner-stopped {
    background: #fdf2f2;
    border: 1.5px solid #e74c3c;
}
span.banner-title  { font-size: 1rem; font-weight: 600; flex: 1; }
span.banner-time   { color: #777; font-size: 0.8rem; }
span.banner-hint   {
    background: rgba(0,0,0,0.06);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.78rem;
    color: #555;
}

/* ══════════════════════════════════════════════════
   METRIC CARDS
══════════════════════════════════════════════════ */
div.metric-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    min-height: 130px;
}
div.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.11);
}
div.metric-icon  { font-size: 1.6rem; margin-bottom: 6px; }
div.metric-value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.1;
    margin-bottom: 4px;
}
div.metric-label {
    font-size: 0.78rem;
    font-weight: 500;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ══════════════════════════════════════════════════
   WORKER CARDS (dashboard grid)
══════════════════════════════════════════════════ */
div.worker-card {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    min-height: 110px;
    position: relative;
    margin-bottom: 4px;
}
div.wc-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
}
span.wc-icon   { font-size: 1rem; }
span.wc-label  { font-size: 0.78rem; font-weight: 700; color: #1a1a2e; flex: 1; }
span.wc-dot    { font-size: 0.8rem; }
div.wc-msg     { font-size: 0.75rem; color: #555; line-height: 1.4; margin-bottom: 8px; }
div.wc-ts      {
    font-size: 0.68rem;
    color: #aaa;
    position: absolute;
    bottom: 10px;
    right: 12px;
}

/* ══════════════════════════════════════════════════
   TERMINAL CONSOLE
══════════════════════════════════════════════════ */
div.terminal-box {
    background: #0d1117;
    border-radius: 10px;
    border: 1px solid #30363d;
    padding: 16px 20px;
    max-height: 420px;
    overflow-y: auto;
    box-shadow: inset 0 2px 8px rgba(0,0,0,0.3);
}
pre.terminal-text {
    color: #c9d1d9;
    font-family: 'Cascadia Code', 'Fira Code', 'Courier New', monospace !important;
    font-size: 0.78rem !important;
    line-height: 1.6;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
}
/* Colour success lines green, error lines red */
pre.terminal-text:has(✅) { color: #3fb950; }

p.log-count-label {
    color: #aaa;
    font-size: 0.78rem;
    margin-bottom: 6px;
}

/* ══════════════════════════════════════════════════
   ALERTS / SUCCESS / INFO
══════════════════════════════════════════════════ */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 0.87rem !important;
}

/* ══════════════════════════════════════════════════
   SLIDER
══════════════════════════════════════════════════ */
div[data-testid="stSlider"] div[role="slider"] {
    background-color: #27ae60 !important;
}
div[data-testid="stSlider"] div[data-baseweb="slider"] div {
    background-color: #27ae60 !important;
}

/* ══════════════════════════════════════════════════
   SCROLLBAR (webkit)
══════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 3px; }
::-webkit-scrollbar-thumb {
    background: #27ae60;
    border-radius: 3px;
    opacity: 0.7;
}
::-webkit-scrollbar-thumb:hover { background: #1e8449; }

/* Terminal scrollbar */
div.terminal-box::-webkit-scrollbar-track { background: #161b22; }
div.terminal-box::-webkit-scrollbar-thumb { background: #30363d; }

/* ══════════════════════════════════════════════════
   HIDE STREAMLIT BRANDING
══════════════════════════════════════════════════ */
#MainMenu  { visibility: hidden; }
footer     { visibility: hidden; }
header     { visibility: hidden; }

</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap() -> EngineManager:
    """
    One-time setup on the very first script run per session:
      1. Initialise the SQLite schema.
      2. Create and cache the EngineManager singleton in session_state.

    Returns the EngineManager so the rest of the app can use it.
    """
    db.init_db()

    if "engine" not in st.session_state:
        st.session_state["engine"] = EngineManager()

    return st.session_state["engine"]


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

def _render_header(engine: EngineManager) -> None:
    """Render the branded top header bar."""
    status_text = engine.get_status_line()
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-header-left">
                <span class="app-header-logo">🚀</span>
                <div>
                    <p class="app-header-title">AI Marketing Engine</p>
                    <p class="app-header-subtitle">
                        24/7 Automated Lead Generation &amp; Plugin Promotion
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
    # 1. Inject CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # 2. Hugging Face first-run banner
    if IS_HF_SPACE:
        db.init_db()
        keys = db.get_all_api_keys()
        no_keys = not any(v.strip() for v in keys.values())
        if no_keys:
            st.markdown(
                """
                <div style="background:#fffbea;border:1.5px solid #f0c040;border-radius:10px;
                            padding:14px 20px;margin-bottom:1rem;font-size:0.88rem;">
                    👋 <strong>Welcome to AI Marketing Engine on Hugging Face!</strong><br>
                    To get started: go to the <strong>⚙️ Settings</strong> tab,
                    enter your <a href="https://console.groq.com" target="_blank"
                    style="color:#27ae60;">Groq API key</a> (free),
                    add at least one plugin, then click <strong>🚀 Start Engine</strong>.
                    <br><em>Your data is saved to persistent storage — it survives restarts.</em>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 3. Bootstrap DB + engine singleton
    engine = _bootstrap()

    # 4. Branded header
    _render_header(engine)

    # 5. Main tabs
    tab_settings, tab_dashboard = st.tabs([
        "⚙️  Settings & Configuration",
        "📊  Live Dashboard & Logs",
    ])

    with tab_settings:
        render_settings_tab(engine)

    with tab_dashboard:
        render_dashboard_tab(engine)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
