"""
ui_settings.py — Settings & Configuration (White + Green theme)
"""
import streamlit as st
import database as db
from engine import EngineManager


def render_settings_tab(engine: EngineManager) -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">⚙️</span>
        <span class="sec-title">Settings & Configuration</span>
    </div>
    """, unsafe_allow_html=True)

    _api_keys()
    st.markdown("---")
    _plugin_manager()
    st.markdown("---")
    _master_switch(engine)


# ── API Keys ──────────────────────────────────────────────────────
def _api_keys() -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">🔑</span>
        <span class="sec-title">Groq API Key Manager</span>
        <span class="sec-badge">AUTO ROTATE</span>
    </div>
    <p style="font-size:0.82rem; color:#888; margin-bottom:16px;">
        Add up to 3 keys. Engine rotates automatically on rate-limit (429) errors.
        Get a free key at
        <a href="https://console.groq.com" target="_blank"
           style="color:#27ae60; font-weight:600;">console.groq.com</a>
    </p>
    """, unsafe_allow_html=True)

    keys   = db.get_all_api_keys()
    labels = ["Primary — tried first", "Failover — Key 2", "Last Resort — Key 3"]

    c1, c2, c3 = st.columns(3)
    inputs = {}
    for col, slot, label in zip([c1, c2, c3], [1, 2, 3], labels):
        with col:
            active = bool(keys[slot].strip())
            badge_color = "#27ae60" if active else "#aaa"
            badge_text  = "● ACTIVE" if active else "○ EMPTY"
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between;
                        align-items:center; margin-bottom:6px;">
                <span style="font-size:0.8rem; font-weight:600; color:#1a1a2e;">
                    Key {slot}
                </span>
                <span style="font-size:0.7rem; font-weight:700;
                             color:{badge_color};">{badge_text}</span>
            </div>
            <div style="font-size:0.72rem; color:#888;
                        margin-bottom:6px;">{label}</div>
            """, unsafe_allow_html=True)
            inputs[slot] = st.text_input(
                f"k{slot}", value=keys[slot], type="password",
                placeholder="gsk_...", label_visibility="collapsed",
                key=f"api_key_{slot}"
            )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾  Save API Keys", type="primary", use_container_width=True):
        for slot in (1, 2, 3):
            db.save_api_key(slot, inputs[slot].strip())
        saved = sum(1 for v in inputs.values() if v.strip())
        st.success(f"✅ {saved} key(s) saved successfully.")


# ── Plugin Manager ────────────────────────────────────────────────
def _plugin_manager() -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">🧩</span>
        <span class="sec-title">Plugin Manager</span>
        <span class="sec-badge">UNLIMITED</span>
    </div>
    <p style="font-size:0.82rem; color:#888; margin-bottom:16px;">
        Add unlimited plugins. The AI selects the most relevant one for each target automatically.
    </p>
    """, unsafe_allow_html=True)

    # Add form
    with st.expander("➕  Add New Plugin", expanded=False):
        with st.form("add_plugin_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Plugin Name *", placeholder="e.g. SpeedBoost Pro")
            with c2:
                link = st.text_input("Shortlink URL *", placeholder="https://bit.ly/yourlink")
            desc = st.text_area(
                "Description / Core Selling Point *",
                placeholder="e.g. Cuts WordPress load time by 70% with one click.",
                height=80
            )
            if st.form_submit_button("➕  Add Plugin", type="primary", use_container_width=True):
                errs = []
                if not name.strip(): errs.append("Plugin Name required.")
                if not link.strip(): errs.append("Shortlink URL required.")
                if not desc.strip(): errs.append("Description required.")
                if errs:
                    for e in errs:
                        st.error(f"⚠️ {e}")
                else:
                    pid = db.add_plugin(name.strip(), link.strip(), desc.strip())
                    st.success(f"✅ '{name.strip()}' added successfully (ID #{pid})")

    # Plugin list
    plugins = db.get_all_plugins()
    summary = {r["id"]: r for r in db.get_all_plugin_stats_summary()}

    st.markdown("<br>", unsafe_allow_html=True)

    if not plugins:
        st.markdown("""
        <div style="text-align:center; padding:30px; color:#aaa;
                    background:#f8fffe; border:1.5px dashed #c8f0dc;
                    border-radius:10px;">
            No plugins added yet. Use the form above ↑
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"""
    <div style="font-size:0.72rem; color:#aaa; margin-bottom:10px;">
        {len(plugins)} plugin(s) registered
    </div>
    """, unsafe_allow_html=True)

    # Table header
    h1, h2, h3, h4 = st.columns([3, 2, 1, 1])
    for col, txt in zip([h1, h2, h3, h4], ["Plugin", "Shortlink", "Actions", ""]):
        with col:
            st.markdown(f"<div style='font-size:0.7rem;color:#aaa;font-weight:700;padding:4px 0;'>{txt}</div>",
                        unsafe_allow_html=True)
    st.markdown("<div style='border-bottom:2px solid #f0faf4;margin-bottom:8px;'></div>",
                unsafe_allow_html=True)

    for p in plugins:
        total = (summary.get(p["id"]) or {}).get("total_actions") or 0
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])

        with c1:
            st.markdown(f"""
            <div style="padding:8px 0;">
                <div style="font-size:0.88rem; font-weight:700; color:#1a1a2e;">
                    {p['name']}
                    <span style="background:#e8f8f0; color:#27ae60; border-radius:4px;
                                 padding:1px 6px; font-size:0.65rem;
                                 font-weight:700; margin-left:6px;">#{p['id']}</span>
                </div>
                <div style="font-size:0.72rem; color:#888; margin-top:2px;">
                    {p['description'][:65]}{'…' if len(p['description'])>65 else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="padding:8px 0;">
                <a href="{p['shortlink']}" target="_blank"
                   style="font-size:0.75rem; color:#27ae60;
                          text-decoration:none; font-family:monospace;">
                    🔗 {p['shortlink'][:38]}{'…' if len(p['shortlink'])>38 else ''}
                </a>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            color = "#27ae60" if total > 0 else "#aaa"
            st.markdown(f"""
            <div style="padding:8px 0; text-align:center;">
                <div style="font-size:1.2rem; font-weight:800; color:{color};">{total:,}</div>
                <div style="font-size:0.62rem; color:#aaa;">actions</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            if st.button("🗑️", key=f"del_{p['id']}", use_container_width=True,
                         help=f"Delete {p['name']}"):
                db.delete_plugin(p["id"])
                st.rerun()

        st.markdown("<div style='border-bottom:1px solid #f5f5f5;'></div>",
                    unsafe_allow_html=True)


# ── Master Switch ─────────────────────────────────────────────────
def _master_switch(engine: EngineManager) -> None:
    is_running = engine.is_running

    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">⚡</span>
        <span class="sec-title">Master Engine Control</span>
    </div>
    """, unsafe_allow_html=True)

    # Status card
    if is_running:
        st.markdown("""
        <div style="background:#f0faf4; border:1.5px solid #27ae60;
                    border-radius:14px; padding:20px 24px; margin-bottom:20px;">
            <div style="display:flex; align-items:center; gap:14px;">
                <span style="font-size:2.2rem;">🟢</span>
                <div>
                    <div style="font-size:1.1rem; font-weight:700; color:#27ae60;">
                        Engine is LIVE
                    </div>
                    <div style="font-size:0.8rem; color:#888; margin-top:2px;">
                        All 5 workers running concurrently in the background
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#fff8f8; border:1.5px solid #e74c3c;
                    border-radius:14px; padding:20px 24px; margin-bottom:20px;">
            <div style="display:flex; align-items:center; gap:14px;">
                <span style="font-size:2.2rem;">🔴</span>
                <div>
                    <div style="font-size:1.1rem; font-weight:700; color:#e74c3c;">
                        Engine Stopped
                    </div>
                    <div style="font-size:0.8rem; color:#888; margin-top:2px;">
                        Configure keys and plugins above, then click Start
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Worker cards
    workers = [
        ("📧", "Contact Sniper",   "Scrapes contact pages, submits AI pitches via Playwright"),
        ("📝", "Blog Bomber",      "Posts contextual comments on WP plugin blogs"),
        ("▶️",  "YouTube Hijacker", "Drops helpful comments on WordPress tutorial videos"),
        ("🔗", "Pingback Engine",  "Sends XML-RPC pingbacks to competitor WP blogs"),
        ("🤖", "Reddit Sniper",    "Monitors RSS feeds, replies to trigger-word posts"),
    ]
    cols = st.columns(5)
    for col, (icon, name, desc) in zip(cols, workers):
        with col:
            border_color = "#27ae60" if is_running else "#e8f8f0"
            bg_color     = "#f0faf4" if is_running else "#FFFFFF"
            dot = '<span class="pulse" style="color:#27ae60;">●</span>' if is_running \
                  else '<span style="color:#ccc;">●</span>'
            st.markdown(f"""
            <div class="wg-card" style="border-color:{border_color};
                        background:{bg_color}; padding:14px; text-align:center;">
                <div style="font-size:1.4rem; margin-bottom:6px;">{icon}</div>
                <div style="font-size:0.75rem; font-weight:700;
                             color:#1a1a2e; margin-bottom:4px;">{name}</div>
                <div style="font-size:0.65rem; color:#888;
                            line-height:1.4; margin-bottom:8px;">{desc}</div>
                {dot}
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Start / Stop button
    bc1, bc2, bc3 = st.columns([1, 2, 1])
    with bc2:
        if not is_running:
            keys    = db.get_all_api_keys()
            plugins = db.get_all_plugins()
            has_key = any(v.strip() for v in keys.values())
            if not has_key:
                st.warning("⚠️ Add at least one Groq API key above.")
            elif not plugins:
                st.warning("⚠️ Add at least one plugin above.")
            else:
                if st.button("🚀  START ENGINE — Launch All 5 Workers",
                             type="primary", use_container_width=True):
                    engine.start()
                    db.add_log("UI", "Engine started via Settings.", "info")
                    st.success("🚀 Engine started! Go to Dashboard to monitor.")
                    st.rerun()
        else:
            if st.button("🛑  STOP ENGINE — Graceful Shutdown",
                         use_container_width=True):
                engine.stop()
                db.add_log("UI", "Engine stopped via Settings.", "info")
                st.info("🛑 Stop signal sent. Workers will finish current cycle and exit.")
                st.rerun()
