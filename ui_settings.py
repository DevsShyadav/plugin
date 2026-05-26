"""
ui_settings.py — Settings & Configuration
API keys, plugin manager, engine master switch.
"""

import streamlit as st
import database as db
from engine import EngineManager


def render_settings_tab(engine: EngineManager) -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">⚙️</span>
        <span class="stitle">Settings & Configuration</span>
    </div>
    """, unsafe_allow_html=True)

    _render_api_keys()
    st.markdown("---")
    _render_plugin_manager()
    st.markdown("---")
    _render_master_switch(engine)


# ─────────────────────────────────────────────────────────────────
# API Key Manager
# ─────────────────────────────────────────────────────────────────
def _render_api_keys() -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">🔑</span>
        <span class="stitle">Groq API Keys</span>
        <span class="sbadge">AUTO ROTATE</span>
    </div>
    <div style="font-size:0.8rem;color:#8b949e;margin-bottom:16px;">
        Add up to 3 keys. Engine automatically rotates on rate-limit.
        Get a free key at
        <a href="https://console.groq.com" target="_blank"
           style="color:#00ff88;">console.groq.com</a>
    </div>
    """, unsafe_allow_html=True)

    keys = db.get_all_api_keys()
    labels = ["Primary (tried first)", "Failover (Key 2)", "Last Resort (Key 3)"]

    c1, c2, c3 = st.columns(3)
    inputs = {}
    for col, slot, label in zip([c1, c2, c3], [1, 2, 3], labels):
        with col:
            val = keys[slot]
            active = bool(val.strip())
            badge = '<span style="color:#00ff88;font-size:0.68rem;">● ACTIVE</span>' if active \
                    else '<span style="color:#8b949e;font-size:0.68rem;">○ EMPTY</span>'
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:space-between;
                        margin-bottom:6px;">
                <span style="font-size:0.78rem;font-weight:600;color:#e2e8f0;">
                    Key {slot} — {label}
                </span>
                {badge}
            </div>
            """, unsafe_allow_html=True)
            inputs[slot] = st.text_input(
                f"key_{slot}", value=val, type="password",
                placeholder="gsk_...", label_visibility="collapsed",
                key=f"api_key_input_{slot}"
            )

    if st.button("💾  Save API Keys", type="primary", use_container_width=True):
        for slot in (1, 2, 3):
            db.save_api_key(slot, inputs[slot].strip())
        saved = sum(1 for v in inputs.values() if v.strip())
        st.success(f"✅ {saved} key(s) saved successfully.")


# ─────────────────────────────────────────────────────────────────
# Plugin Manager
# ─────────────────────────────────────────────────────────────────
def _render_plugin_manager() -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">🧩</span>
        <span class="stitle">Plugin Manager</span>
        <span class="sbadge">UNLIMITED</span>
    </div>
    """, unsafe_allow_html=True)

    # Add form
    with st.expander("➕  Add New Plugin", expanded=False):
        with st.form("add_plugin_form", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                name = st.text_input("Plugin Name *", placeholder="e.g. SpeedBoost Pro")
            with col2:
                link = st.text_input("Shortlink URL *", placeholder="https://bit.ly/yourlink")
            desc = st.text_area(
                "Description / Core Selling Point *",
                placeholder="e.g. Cuts WordPress load time by 70% with one click. No coding needed.",
                height=80
            )
            submitted = st.form_submit_button("➕  Add Plugin", type="primary",
                                              use_container_width=True)
            if submitted:
                errs = []
                if not name.strip(): errs.append("Plugin Name required.")
                if not link.strip(): errs.append("Shortlink URL required.")
                if not desc.strip(): errs.append("Description required.")
                if errs:
                    for e in errs:
                        st.error(f"⚠️ {e}")
                else:
                    pid = db.add_plugin(name.strip(), link.strip(), desc.strip())
                    st.success(f"✅ '{name.strip()}' added (ID #{pid})")

    # Plugin list
    plugins = db.get_all_plugins()
    summary = {row["id"]: row for row in db.get_all_plugin_stats_summary()}

    if not plugins:
        st.markdown("""
        <div style="text-align:center;padding:30px;color:#8b949e;
                    background:#161b22;border-radius:10px;border:1px dashed #21262d;">
            No plugins yet. Use the form above to add your first plugin.
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"""
    <div style="font-size:0.72rem;color:#8b949e;margin-bottom:10px;">
        {len(plugins)} plugin(s) registered
    </div>
    """, unsafe_allow_html=True)

    for p in plugins:
        stats = summary.get(p["id"], {})
        total = stats.get("total_actions") or 0

        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        with col1:
            st.markdown(f"""
            <div style="padding:8px 0;">
                <div style="font-size:0.9rem;font-weight:700;color:#e2e8f0;">
                    {p['name']}
                    <span class="plugin-badge" style="margin-left:8px;">#{p['id']}</span>
                </div>
                <div style="font-size:0.75rem;color:#8b949e;margin-top:2px;">
                    {p['description'][:70]}{'…' if len(p['description'])>70 else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div style="padding:8px 0;">
                <a href="{p['shortlink']}" target="_blank"
                   style="font-size:0.75rem;color:#00ff88;text-decoration:none;
                          font-family:monospace;">
                    🔗 {p['shortlink'][:40]}{'…' if len(p['shortlink'])>40 else ''}
                </a>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div style="padding:8px 0;text-align:center;">
                <div style="font-size:1.1rem;font-weight:800;color:#00ff88;">{total:,}</div>
                <div style="font-size:0.65rem;color:#8b949e;">actions</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            if st.button("🗑️ Delete", key=f"del_{p['id']}", use_container_width=True):
                db.delete_plugin(p["id"])
                st.rerun()

        st.markdown("<div style='border-bottom:1px solid #161b22;'></div>",
                    unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Master Switch
# ─────────────────────────────────────────────────────────────────
def _render_master_switch(engine: EngineManager) -> None:
    is_running = engine.is_running

    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">⚡</span>
        <span class="stitle">Master Engine Control</span>
    </div>
    """, unsafe_allow_html=True)

    # Status
    if is_running:
        st.markdown("""
        <div style="background:rgba(0,255,136,0.05);border:1px solid rgba(0,255,136,0.3);
                    border-radius:14px;padding:20px 24px;margin-bottom:20px;">
            <div style="display:flex;align-items:center;gap:14px;">
                <div style="font-size:2rem;">🟢</div>
                <div>
                    <div style="font-size:1.1rem;font-weight:700;color:#00ff88;">
                        Engine is LIVE
                    </div>
                    <div style="font-size:0.8rem;color:#8b949e;margin-top:2px;">
                        All 5 workers running concurrently in the background
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.3);
                    border-radius:14px;padding:20px 24px;margin-bottom:20px;">
            <div style="display:flex;align-items:center;gap:14px;">
                <div style="font-size:2rem;">🔴</div>
                <div>
                    <div style="font-size:1.1rem;font-weight:700;color:#ef4444;">
                        Engine Stopped
                    </div>
                    <div style="font-size:0.8rem;color:#8b949e;margin-top:2px;">
                        Configure keys and plugins above, then start the engine
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Workers list
    workers = [
        ("📧", "Worker_Contact_Sniper",   "Scrapes contact pages, submits AI-written pitches"),
        ("📝", "Worker_Blog_Bomber",      "Posts contextual comments on WP plugin blogs"),
        ("▶️",  "Worker_YouTube_Hijacker", "Drops helpful comments on YouTube WP tutorials"),
        ("🔗", "Worker_Pingback_Engine",  "Sends XML-RPC pingbacks to competitor blogs"),
        ("🤖", "Worker_Reddit_Sniper",    "Monitors Reddit RSS, replies to trigger-word posts"),
    ]

    cols = st.columns(5)
    for col, (icon, name, desc) in zip(cols, workers):
        with col:
            active_style = "border-color:rgba(0,255,136,0.4);" if is_running else ""
            dot = '<span style="color:#00ff88;" class="pulse">●</span>' if is_running \
                  else '<span style="color:#8b949e;">●</span>'
            st.markdown(f"""
            <div class="premium-card" style="padding:14px;{active_style}">
                <div style="font-size:1.2rem;margin-bottom:6px;">{icon}</div>
                <div style="font-size:0.72rem;font-weight:700;color:#e2e8f0;margin-bottom:4px;">
                    {name.replace('Worker_','')}
                </div>
                <div style="font-size:0.65rem;color:#8b949e;line-height:1.4;">
                    {desc}
                </div>
                <div style="margin-top:8px;">{dot}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Buttons
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
                    st.success("🚀 Engine started! Switch to Dashboard to monitor.")
                    st.rerun()
        else:
            if st.button("🛑  STOP ENGINE — Graceful Shutdown",
                         use_container_width=True):
                engine.stop()
                db.add_log("UI", "Engine stopped via Settings.", "info")
                st.info("🛑 Stop signal sent. Workers will finish current cycle.")
                st.rerun()
