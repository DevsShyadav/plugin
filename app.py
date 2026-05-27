"""
app.py — AI Marketing Engine
Clean White (#FFFFFF) + Green (#27ae60 / #2ecc71) theme
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

# ─────────────────────────────────────────────────────────────
# CSS — White background + Green accents
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* GLOBAL */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: #FFFFFF !important;
    color: #1a1a2e !important;
}
.stApp, .main .block-container,
div[data-testid="stAppViewContainer"] {
    background-color: #FFFFFF !important;
}
.main .block-container {
    padding-top: 1rem !important;
    max-width: 1400px !important;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: #f8fffe !important;
    border-right: 2px solid #e8f8f0 !important;
}
section[data-testid="stSidebar"] * { color: #1a1a2e !important; }

/* SIDEBAR RADIO */
div[data-testid="stSidebar"] .stRadio label {
    padding: 10px 14px !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    margin-bottom: 2px !important;
    display: block !important;
}
div[data-testid="stSidebar"] .stRadio label:hover {
    background: #e8f8f0 !important;
    color: #27ae60 !important;
}

/* BUTTONS */
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #27ae60, #2ecc71) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.4rem !important;
    box-shadow: 0 2px 12px rgba(39,174,96,0.3) !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 4px 20px rgba(39,174,96,0.5) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stButton"] > button:not([kind="primary"]) {
    background: #FFFFFF !important;
    color: #27ae60 !important;
    border: 1.5px solid #27ae60 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button:not([kind="primary"]):hover {
    background: #f0faf4 !important;
}

/* INPUTS */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: #fafafa !important;
    border: 1.5px solid #e0e0e0 !important;
    border-radius: 8px !important;
    color: #1a1a2e !important;
    font-size: 0.88rem !important;
    transition: border-color 0.2s !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: #27ae60 !important;
    box-shadow: 0 0 0 3px rgba(39,174,96,0.12) !important;
    background: #FFFFFF !important;
}

/* TABS */
div[data-testid="stTabs"] button[role="tab"] {
    background: transparent !important;
    color: #777 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 10px 20px !important;
    transition: all 0.2s !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #27ae60 !important;
    border-bottom: 2px solid #27ae60 !important;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #27ae60 !important;
    background: #f0faf4 !important;
}

/* METRICS */
div[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1.5px solid #e8f8f0 !important;
    border-radius: 12px !important;
    padding: 16px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}
div[data-testid="stMetric"] label { color: #888 !important; font-size: 0.78rem !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #27ae60 !important;
    font-weight: 800 !important;
    font-size: 1.8rem !important;
}

/* ALERTS */
div[data-testid="stAlert"] { border-radius: 8px !important; font-size: 0.87rem !important; }

/* HR */
hr { border-color: #f0f0f0 !important; margin: 0.8rem 0 1.2rem 0 !important; }

/* SCROLLBAR */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #f5f5f5; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #27ae60; border-radius: 3px; }

/* HIDE BRANDING */
#MainMenu, footer, header { visibility: hidden; }

/* CARD */
.wg-card {
    background: #FFFFFF;
    border: 1.5px solid #e8f8f0;
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    transition: all 0.2s;
    height: 100%;
}
.wg-card:hover {
    border-color: #27ae60;
    box-shadow: 0 4px 20px rgba(39,174,96,0.12);
    transform: translateY(-2px);
}
.wg-card .card-icon { font-size: 1.8rem; margin-bottom: 8px; }
.wg-card .card-value {
    font-size: 2.2rem;
    font-weight: 800;
    color: #27ae60;
    line-height: 1;
    margin-bottom: 4px;
}
.wg-card .card-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

/* BADGE */
.badge-green {
    display: inline-flex; align-items: center; gap: 6px;
    background: #e8f8f0; border: 1.5px solid #27ae60;
    color: #27ae60; border-radius: 20px;
    padding: 4px 14px; font-size: 0.8rem; font-weight: 700;
}
.badge-red {
    display: inline-flex; align-items: center; gap: 6px;
    background: #fff0f0; border: 1.5px solid #e74c3c;
    color: #e74c3c; border-radius: 20px;
    padding: 4px 14px; font-size: 0.8rem; font-weight: 700;
}
.pulse { animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* SECTION HEADER */
.sec-hdr {
    display: flex; align-items: center; gap: 10px;
    padding-bottom: 12px;
    border-bottom: 2px solid #f0faf4;
    margin-bottom: 18px;
}
.sec-hdr .sec-title { font-size: 1rem; font-weight: 700; color: #1a1a2e; }
.sec-hdr .sec-badge {
    margin-left: auto;
    background: #e8f8f0; color: #27ae60;
    border-radius: 12px; padding: 2px 10px;
    font-size: 0.7rem; font-weight: 700;
}

/* TERMINAL */
.log-terminal {
    background: #0d1117;
    border: 1.5px solid #e0e0e0;
    border-radius: 10px;
    padding: 16px 18px;
    max-height: 380px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    font-size: 0.76rem;
    line-height: 1.7;
}

/* WORKER CARD */
.worker-item {
    background: #FFFFFF;
    border: 1.5px solid #e8f8f0;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: all 0.2s;
}
.worker-item:hover { border-color: #27ae60; background: #f8fffb; }
.worker-item.active { border-color: #27ae60; background: #f0faf4; }

/* PLUGIN ROW */
.plugin-item {
    background: #FFFFFF;
    border: 1.5px solid #e8f8f0;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
}
.plugin-item:hover { border-color: #27ae60; }

/* PROGRESS BAR */
.prog-bg { background: #f0f0f0; border-radius: 4px; height: 7px; overflow: hidden; }
.prog-fill {
    height: 7px; border-radius: 4px;
    background: linear-gradient(90deg, #27ae60, #2ecc71);
}

/* SELECT BOX */
div[data-testid="stSelectbox"] > div {
    background: #fafafa !important;
    border: 1.5px solid #e0e0e0 !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)


def _bootstrap() -> EngineManager:
    db.init_db()
    # Use module-level global engine (survives Streamlit re-runs & session resets)
    # This means workers keep running even when the page auto-refreshes
    from engine import get_engine
    return get_engine()


def _render_sidebar(engine: EngineManager) -> str:
    with st.sidebar:
        # Logo
        st.markdown("""
        <div style="padding: 16px 4px 24px 4px;">
            <div style="font-size:1.5rem; font-weight:800; color:#27ae60;">
                🚀 MarketEngine
            </div>
            <div style="font-size:0.72rem; color:#888; margin-top:3px;">
                AI-Powered 24/7 Lead Generation
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Engine badge
        if engine.is_running:
            st.markdown('<div class="badge-green"><span class="pulse">●</span> ENGINE LIVE</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="badge-red">● ENGINE STOPPED</div>',
                        unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<div style='font-size:0.68rem;color:#aaa;font-weight:700;letter-spacing:1px;margin-bottom:6px;'>NAVIGATION</div>",
                    unsafe_allow_html=True)

        page = st.radio("", [
            "📊  Dashboard",
            "📈  Reports",
            "🔌  Plugin Analytics",
            "⚙️  Settings",
            "📋  Live Logs",
        ], label_visibility="collapsed")

        st.markdown("<br>", unsafe_allow_html=True)

        # Quick stats box
        m = db.get_metrics()
        total = sum(m.values())
        st.markdown(f"""
        <div style="background:#f8fffe; border:1.5px solid #e8f8f0;
                    border-radius:10px; padding:14px 16px;">
            <div style="font-size:0.68rem;color:#aaa;font-weight:700;
                        letter-spacing:1px;margin-bottom:10px;">QUICK STATS</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:0.78rem;color:#888;">Total Actions</span>
                <span style="font-size:0.78rem;color:#27ae60;font-weight:700;">{total:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:0.78rem;color:#888;">Forms Filled</span>
                <span style="font-size:0.78rem;color:#1a1a2e;font-weight:600;">{m['forms_filled']:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:0.78rem;color:#888;">Comments</span>
                <span style="font-size:0.78rem;color:#1a1a2e;font-weight:600;">{m['comments_posted']:,}</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
                <span style="font-size:0.78rem;color:#888;">Pingbacks</span>
                <span style="font-size:0.78rem;color:#1a1a2e;font-weight:600;">{m['pingbacks_sent']:,}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        keys = db.get_all_api_keys()
        active = sum(1 for v in keys.values() if v.strip())
        st.markdown(f"""
        <div style="font-size:0.75rem;color:#888;line-height:1.8;">
            🔑 <span style="color:#1a1a2e;font-weight:600;">{active}/3</span> Groq keys active<br>
            🤖 <code style="font-size:0.68rem;color:#27ae60;">llama-3.3-70b-versatile</code>
        </div>
        """, unsafe_allow_html=True)

    return page


def main():
    engine = _bootstrap()
    page = _render_sidebar(engine)

    if IS_HF_SPACE:
        keys = db.get_all_api_keys()
        if not any(v.strip() for v in keys.values()):
            st.info("👋 **Welcome!** Go to ⚙️ Settings → add your [Groq API key](https://console.groq.com) → add a plugin → Start Engine.")

    clean = page.strip().split("  ")[-1]

    if clean == "Dashboard":
        render_dashboard_tab(engine)
    elif clean == "Reports":
        from ui_reports import render_reports_tab
        render_reports_tab()
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
