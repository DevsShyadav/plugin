"""
ui_settings.py
==============
Renders Tab 1: ⚙️ Settings & Configuration

Sections:
    1. API Key Manager      — Save/update 3 Groq API key slots with masked inputs
    2. Dynamic Plugin Manager — Add unlimited plugins, view table, delete rows
    3. Master Switch        — Start Engine / Stop Engine toggle button

All state mutations go directly to SQLite via database.py.
The EngineManager is retrieved from st.session_state so start/stop
actions take effect on the shared singleton.
"""

import streamlit as st
import pandas as pd

import database as db
from engine import EngineManager


# ---------------------------------------------------------------------------
# Public entry point — called from app.py
# ---------------------------------------------------------------------------

def render_settings_tab(engine: EngineManager) -> None:
    """
    Render the entire Settings & Configuration tab.

    Args:
        engine: The shared EngineManager singleton from st.session_state.
    """
    # ── Section divider helper ──────────────────────────────────────────────
    def section(title: str, icon: str) -> None:
        st.markdown(f"### {icon} {title}")
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 1. API KEY MANAGER
    # ═══════════════════════════════════════════════════════════════════════
    section("API Key Manager", "🔑")

    st.markdown(
        "<p class='sub-label'>Enter up to 3 Groq API keys. "
        "The engine rotates automatically on rate-limit errors.</p>",
        unsafe_allow_html=True,
    )

    keys = db.get_all_api_keys()   # {1: 'key_or_empty', 2: ..., 3: ...}

    col1, col2, col3 = st.columns(3)

    with col1:
        k1 = st.text_input(
            "Groq API Key 1 (Primary)",
            value=keys[1],
            type="password",
            placeholder="gsk_...",
            key="api_key_1",
            help="This key is tried first for every Groq request.",
        )
    with col2:
        k2 = st.text_input(
            "Groq API Key 2 (Failover)",
            value=keys[2],
            type="password",
            placeholder="gsk_...",
            key="api_key_2",
            help="Used when Key 1 hits a rate limit.",
        )
    with col3:
        k3 = st.text_input(
            "Groq API Key 3 (Last Resort)",
            value=keys[3],
            type="password",
            placeholder="gsk_...",
            key="api_key_3",
            help="Used when both Key 1 and Key 2 are exhausted.",
        )

    if st.button("💾  Save API Keys", key="save_keys_btn", use_container_width=True):
        db.save_api_key(1, k1.strip())
        db.save_api_key(2, k2.strip())
        db.save_api_key(3, k3.strip())
        saved_count = sum(1 for k in (k1, k2, k3) if k.strip())
        st.success(f"✅ {saved_count} API key(s) saved successfully.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. PLUGIN MANAGER
    # ═══════════════════════════════════════════════════════════════════════
    section("Plugin Manager", "🧩")

    st.markdown(
        "<p class='sub-label'>Add unlimited plugins. "
        "The AI selects the most relevant one for each target automatically.</p>",
        unsafe_allow_html=True,
    )

    # ── Add Plugin Form ──────────────────────────────────────────────────
    with st.form("add_plugin_form", clear_on_submit=True):
        st.markdown("##### ➕ Add New Plugin")

        fc1, fc2 = st.columns([1, 1])
        with fc1:
            plugin_name = st.text_input(
                "Plugin Name *",
                placeholder="e.g. SpeedBoost Pro",
                help="The human-readable product name.",
            )
        with fc2:
            plugin_link = st.text_input(
                "Shortlink URL *",
                placeholder="e.g. https://bit.ly/speedboost",
                help="The trackable link dropped into all generated copy.",
            )

        plugin_desc = st.text_area(
            "Description / Core Selling Point *",
            placeholder=(
                "e.g. Cuts WordPress page load time by 70% with one-click "
                "optimization — no coding needed."
            ),
            height=90,
            help="Used by the AI to match this plugin to the right context.",
        )

        submitted = st.form_submit_button(
            "➕  Add Plugin",
            use_container_width=True,
        )

        if submitted:
            # Validate required fields
            errors = []
            if not plugin_name.strip():
                errors.append("Plugin Name is required.")
            if not plugin_link.strip():
                errors.append("Shortlink URL is required.")
            if not plugin_desc.strip():
                errors.append("Description is required.")

            if errors:
                for err in errors:
                    st.error(f"⚠️ {err}")
            else:
                new_id = db.add_plugin(
                    name=plugin_name.strip(),
                    shortlink=plugin_link.strip(),
                    description=plugin_desc.strip(),
                )
                st.success(f"✅ Plugin '{plugin_name.strip()}' added (ID: {new_id}).")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Plugins Data Table ────────────────────────────────────────────────
    st.markdown("##### 📋 Registered Plugins")

    plugins = db.get_all_plugins()

    if not plugins:
        st.info("No plugins added yet. Use the form above to add your first plugin.")
    else:
        # Render each plugin as a styled card row with a Delete button
        for plugin in plugins:
            with st.container():
                row_cols = st.columns([0.05, 0.22, 0.25, 0.38, 0.10])

                with row_cols[0]:
                    st.markdown(
                        f"<span class='plugin-id'>#{plugin['id']}</span>",
                        unsafe_allow_html=True,
                    )
                with row_cols[1]:
                    st.markdown(
                        f"<span class='plugin-name'>{plugin['name']}</span>",
                        unsafe_allow_html=True,
                    )
                with row_cols[2]:
                    st.markdown(
                        f"<a href='{plugin['shortlink']}' target='_blank' "
                        f"class='plugin-link'>{plugin['shortlink'][:35]}…</a>"
                        if len(plugin['shortlink']) > 35
                        else f"<a href='{plugin['shortlink']}' target='_blank' "
                             f"class='plugin-link'>{plugin['shortlink']}</a>",
                        unsafe_allow_html=True,
                    )
                with row_cols[3]:
                    st.markdown(
                        f"<span class='plugin-desc'>{plugin['description'][:80]}…</span>"
                        if len(plugin['description']) > 80
                        else f"<span class='plugin-desc'>{plugin['description']}</span>",
                        unsafe_allow_html=True,
                    )
                with row_cols[4]:
                    if st.button(
                        "🗑️ Delete",
                        key=f"del_plugin_{plugin['id']}",
                        help=f"Remove '{plugin['name']}' from the plugin list.",
                    ):
                        db.delete_plugin(plugin["id"])
                        st.rerun()

                st.markdown('<div class="plugin-row-divider"></div>', unsafe_allow_html=True)

        st.markdown(
            f"<p class='plugin-count'>Total plugins: <strong>{len(plugins)}</strong></p>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. MASTER SWITCH — Start Engine / Stop Engine
    # ═══════════════════════════════════════════════════════════════════════
    section("Master Engine Control", "⚡")

    _render_master_switch(engine)


# ---------------------------------------------------------------------------
# Master switch sub-renderer
# ---------------------------------------------------------------------------

def _render_master_switch(engine: EngineManager) -> None:
    """
    Renders the prominent Start/Stop engine toggle with status indicators.
    Includes pre-flight validation (keys + plugins must exist to start).
    """
    is_running = engine.is_running

    # Status badge
    status_class = "status-running" if is_running else "status-stopped"
    status_text  = "RUNNING" if is_running else "STOPPED"
    status_icon  = "🟢" if is_running else "🔴"

    st.markdown(
        f"""
        <div class="master-switch-card">
            <div class="engine-status-badge {status_class}">
                {status_icon} Engine Status: <strong>{status_text}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])

    with btn_col2:
        if not is_running:
            # ── PRE-FLIGHT CHECKS before allowing start ──────────────────
            keys    = db.get_all_api_keys()
            plugins = db.get_all_plugins()
            has_key = any(v.strip() for v in keys.values())
            has_plugin = len(plugins) > 0

            if not has_key:
                st.warning("⚠️ Add at least one Groq API key above before starting.")
            if not has_plugin:
                st.warning("⚠️ Add at least one plugin above before starting.")

            start_disabled = not (has_key and has_plugin)

            if st.button(
                "🚀  START ENGINE",
                key="engine_start_btn",
                use_container_width=True,
                disabled=start_disabled,
                help="Launches all 5 background workers concurrently.",
                type="primary",
            ):
                engine.start()
                db.add_log("UI", "Engine started via UI Master Switch.", "info")
                st.success("🚀 Engine started! Switch to the Dashboard tab to monitor activity.")
                st.rerun()
        else:
            if st.button(
                "🛑  STOP ENGINE",
                key="engine_stop_btn",
                use_container_width=True,
                help="Sends stop signal — workers finish current cycle then exit.",
                type="secondary",
            ):
                engine.stop()
                db.add_log("UI", "Engine stopped via UI Master Switch.", "info")
                st.info("🛑 Stop signal sent. Workers will finish their current cycle and exit.")
                st.rerun()

    # Worker checklist (visible when running)
    if is_running:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 🔄 Active Workers")
        workers = [
            ("Worker_Contact_Sniper",   "📧", "Scraping contact forms & submitting pitches"),
            ("Worker_Blog_Bomber",      "📝", "Posting contextual comments on WP blogs"),
            ("Worker_YouTube_Hijacker", "▶️",  "Dropping comments on YouTube tutorials"),
            ("Worker_Pingback_Engine",  "🔗", "Sending XML-RPC pingbacks to competitor blogs"),
            ("Worker_Reddit_Sniper",    "🤖", "Monitoring Reddit RSS for trigger words"),
        ]
        for wname, icon, desc in workers:
            st.markdown(
                f"""
                <div class="worker-row">
                    <span class="worker-dot">●</span>
                    <span class="worker-icon">{icon}</span>
                    <span class="worker-name">{wname}</span>
                    <span class="worker-desc"> — {desc}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
