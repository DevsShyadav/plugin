"""
ui_settings.py
==============
Jarvis AI Marketing Engine — Settings & Configuration Tab

Sections:
    1. API Key Manager       — 3 Groq API key slots
    2. YouTube/Gmail Credentials — Gmail email, password, API key for YouTube
    3. Reddit/PRAW Credentials  — client_id, secret, username, password
    4. Plugin Manager        — Add/view/delete plugins
    5. Master Engine Control — Start/Stop with pre-flight checks
"""

import streamlit as st

import database as db
from engine import EngineManager


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_settings_tab(engine: EngineManager) -> None:
    """Render the Settings & Configuration tab."""

    def section(title: str, icon: str) -> None:
        st.markdown(f"### {icon} {title}")
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 1. GROQ API KEY MANAGER
    # ═══════════════════════════════════════════════════════════════════════
    section("Groq API Keys", "🔑")


    st.markdown(
        "<p class='sub-label'>Enter up to 3 Groq API keys. "
        "Engine auto-rotates on rate-limit errors for uninterrupted operation.</p>",
        unsafe_allow_html=True,
    )

    keys = db.get_all_api_keys()

    col1, col2, col3 = st.columns(3)
    with col1:
        k1 = st.text_input(
            "Key 1 (Primary)", value=keys[1], type="password",
            placeholder="gsk_...", key="api_key_1",
            help="Primary key — tried first for every request.",
        )
    with col2:
        k2 = st.text_input(
            "Key 2 (Failover)", value=keys[2], type="password",
            placeholder="gsk_...", key="api_key_2",
            help="Used when Key 1 hits rate limit.",
        )
    with col3:
        k3 = st.text_input(
            "Key 3 (Last Resort)", value=keys[3], type="password",
            placeholder="gsk_...", key="api_key_3",
            help="Used when Keys 1 & 2 are exhausted.",
        )

    if st.button("💾  Save API Keys", key="save_keys_btn", use_container_width=True):
        db.save_api_key(1, k1.strip())
        db.save_api_key(2, k2.strip())
        db.save_api_key(3, k3.strip())
        saved_count = sum(1 for k in (k1, k2, k3) if k.strip())
        st.success(f"✅ {saved_count} API key(s) saved successfully.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. YOUTUBE / GMAIL CREDENTIALS
    # ═══════════════════════════════════════════════════════════════════════
    section("YouTube / Gmail Credentials", "▶️")

    st.markdown(
        "<p class='sub-label'>Required for posting YouTube comments. "
        "Enter your Gmail credentials and YouTube Data API key.</p>",
        unsafe_allow_html=True,
    )

    yt_creds = db.get_credentials("youtube_gmail")

    yt_col1, yt_col2 = st.columns(2)
    with yt_col1:
        yt_email = st.text_input(
            "Gmail Email Address",
            value=yt_creds.get("email", ""),
            placeholder="your.email@gmail.com",
            key="yt_email",
            help="Gmail account linked to your YouTube channel.",
        )
    with yt_col2:
        yt_password = st.text_input(
            "Gmail App Password",
            value=yt_creds.get("password", ""),
            type="password",
            placeholder="xxxx xxxx xxxx xxxx",
            key="yt_password",
            help="Use a Google App Password (not your main password). Generate at myaccount.google.com/apppasswords",
        )

    yt_col3, yt_col4 = st.columns(2)
    with yt_col3:
        yt_api_key = st.text_input(
            "YouTube Data API Key",
            value=yt_creds.get("api_key", ""),
            type="password",
            placeholder="AIza...",
            key="yt_api_key",
            help="Get from Google Cloud Console → APIs & Services → YouTube Data API v3.",
        )
    with yt_col4:
        yt_access_token = st.text_input(
            "OAuth2 Access Token (Optional)",
            value=yt_creds.get("access_token", ""),
            type="password",
            placeholder="ya29...",
            key="yt_access_token",
            help="OAuth2 token for posting comments. Refresh periodically.",
        )

    if st.button("💾  Save YouTube Credentials", key="save_yt_creds_btn", use_container_width=True):
        db.save_credentials("youtube_gmail", {
            "email": yt_email.strip(),
            "password": yt_password.strip(),
            "api_key": yt_api_key.strip(),
            "access_token": yt_access_token.strip(),
        })
        st.success("✅ YouTube/Gmail credentials saved!")

    # Status indicator
    if db.has_credentials("youtube_gmail"):
        st.markdown(
            '<div style="background:#e8f8f0;border:1px solid #27ae60;border-radius:8px;'
            'padding:8px 16px;margin-top:8px;"><span style="color:#27ae60;font-weight:600;">'
            '🟢 YouTube credentials configured — Live posting enabled</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#fef3e8;border:1px solid #f39c12;border-radius:8px;'
            'padding:8px 16px;margin-top:8px;"><span style="color:#e67e22;font-weight:600;">'
            '🟡 YouTube credentials missing — Running in dry-run mode</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)


    # ═══════════════════════════════════════════════════════════════════════
    # 3. REDDIT / PRAW CREDENTIALS
    # ═══════════════════════════════════════════════════════════════════════
    section("Reddit / PRAW Credentials", "🤖")

    st.markdown(
        "<p class='sub-label'>Required for posting Reddit replies. "
        "Create a Reddit app at <a href='https://www.reddit.com/prefs/apps' "
        "target='_blank'>reddit.com/prefs/apps</a> (select 'script' type).</p>",
        unsafe_allow_html=True,
    )

    reddit_creds = db.get_credentials("reddit_praw")

    rd_col1, rd_col2 = st.columns(2)
    with rd_col1:
        rd_client_id = st.text_input(
            "Reddit Client ID",
            value=reddit_creds.get("client_id", ""),
            placeholder="e.g. aB1cD2eF3gH4iJ",
            key="rd_client_id",
            help="Found under your app name on reddit.com/prefs/apps",
        )
    with rd_col2:
        rd_client_secret = st.text_input(
            "Reddit Client Secret",
            value=reddit_creds.get("client_secret", ""),
            type="password",
            placeholder="e.g. xY5zW6vU7tS8rQ...",
            key="rd_client_secret",
            help="The 'secret' shown below your app on reddit.com/prefs/apps",
        )

    rd_col3, rd_col4 = st.columns(2)
    with rd_col3:
        rd_username = st.text_input(
            "Reddit Username",
            value=reddit_creds.get("username", ""),
            placeholder="your_reddit_username",
            key="rd_username",
            help="Your Reddit account username (without u/).",
        )
    with rd_col4:
        rd_password = st.text_input(
            "Reddit Password",
            value=reddit_creds.get("password", ""),
            type="password",
            placeholder="your_reddit_password",
            key="rd_password",
            help="Your Reddit account password.",
        )

    rd_ua = st.text_input(
        "User Agent String (Optional)",
        value=reddit_creds.get("user_agent", "JarvisMarketingBot/2.0"),
        placeholder="JarvisMarketingBot/2.0",
        key="rd_user_agent",
        help="Custom user agent for PRAW. Default: JarvisMarketingBot/2.0",
    )

    if st.button("💾  Save Reddit Credentials", key="save_rd_creds_btn", use_container_width=True):
        db.save_credentials("reddit_praw", {
            "client_id": rd_client_id.strip(),
            "client_secret": rd_client_secret.strip(),
            "username": rd_username.strip(),
            "password": rd_password.strip(),
            "user_agent": rd_ua.strip() or "JarvisMarketingBot/2.0",
        })
        st.success("✅ Reddit/PRAW credentials saved!")

    # Status indicator
    if db.has_credentials("reddit_praw"):
        st.markdown(
            '<div style="background:#e8f8f0;border:1px solid #27ae60;border-radius:8px;'
            'padding:8px 16px;margin-top:8px;"><span style="color:#27ae60;font-weight:600;">'
            '🟢 Reddit credentials configured — Live posting enabled</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#fef3e8;border:1px solid #f39c12;border-radius:8px;'
            'padding:8px 16px;margin-top:8px;"><span style="color:#e67e22;font-weight:600;">'
            '🟡 Reddit credentials missing — Running in dry-run mode</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)


    # ═══════════════════════════════════════════════════════════════════════
    # 4. PLUGIN MANAGER
    # ═══════════════════════════════════════════════════════════════════════
    section("Plugin Manager", "🧩")

    st.markdown(
        "<p class='sub-label'>Add unlimited plugins. "
        "Jarvis AI automatically selects the most relevant one for each target.</p>",
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
                help="Human-readable product name.",
            )
        with fc2:
            plugin_link = st.text_input(
                "Shortlink URL *",
                placeholder="e.g. https://bit.ly/speedboost",
                help="Trackable link used in all generated copy.",
            )

        plugin_desc = st.text_area(
            "Description / Core Selling Point *",
            placeholder=(
                "e.g. Cuts WordPress page load time by 70% with one-click "
                "optimization — no coding needed."
            ),
            height=90,
            help="Used by AI to match this plugin to the right context.",
        )

        submitted = st.form_submit_button("➕  Add Plugin", use_container_width=True)

        if submitted:
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

    # ── Plugins Table ─────────────────────────────────────────────────────
    st.markdown("##### 📋 Registered Plugins")

    plugins = db.get_all_plugins()

    if not plugins:
        st.info("No plugins added yet. Use the form above to add your first plugin.")
    else:
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
                    link_display = plugin['shortlink'][:35] + "…" if len(plugin['shortlink']) > 35 else plugin['shortlink']
                    st.markdown(
                        f"<a href='{plugin['shortlink']}' target='_blank' "
                        f"class='plugin-link'>{link_display}</a>",
                        unsafe_allow_html=True,
                    )
                with row_cols[3]:
                    desc_display = plugin['description'][:80] + "…" if len(plugin['description']) > 80 else plugin['description']
                    st.markdown(
                        f"<span class='plugin-desc'>{desc_display}</span>",
                        unsafe_allow_html=True,
                    )
                with row_cols[4]:
                    if st.button("🗑️", key=f"del_plugin_{plugin['id']}",
                                 help=f"Remove '{plugin['name']}'"):
                        db.delete_plugin(plugin["id"])
                        st.rerun()

                st.markdown('<div class="plugin-row-divider"></div>', unsafe_allow_html=True)

        st.markdown(
            f"<p class='plugin-count'>Total plugins: <strong>{len(plugins)}</strong></p>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. MASTER ENGINE CONTROL
    # ═══════════════════════════════════════════════════════════════════════
    section("Master Engine Control", "⚡")
    _render_master_switch(engine)



# ---------------------------------------------------------------------------
# Master switch sub-renderer
# ---------------------------------------------------------------------------

def _render_master_switch(engine: EngineManager) -> None:
    """Start/Stop engine toggle with pre-flight checks."""
    is_running = engine.is_running

    status_class = "status-running" if is_running else "status-stopped"
    status_text = "JARVIS ACTIVE" if is_running else "OFFLINE"
    status_icon = "🟢" if is_running else "🔴"

    st.markdown(
        f"""
        <div class="master-switch-card">
            <div class="engine-status-badge {status_class}">
                {status_icon} Engine: <strong>{status_text}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_running:
        st.markdown(
            f"<p style='text-align:center;color:#27ae60;font-size:0.85rem;'>"
            f"⏱️ Uptime: {engine.uptime}</p>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])

    with btn_col2:
        if not is_running:
            # Pre-flight checks
            keys = db.get_all_api_keys()
            plugins = db.get_all_plugins()
            has_key = any(v.strip() for v in keys.values())
            has_plugin = len(plugins) > 0

            if not has_key:
                st.warning("⚠️ Add at least one Groq API key before starting.")
            if not has_plugin:
                st.warning("⚠️ Add at least one plugin before starting.")

            # Credential status summary
            yt_status = "🟢" if db.has_credentials("youtube_gmail") else "🟡 Dry-run"
            rd_status = "🟢" if db.has_credentials("reddit_praw") else "🟡 Dry-run"
            st.markdown(
                f"<p style='text-align:center;font-size:0.82rem;color:#666;'>"
                f"YouTube: {yt_status} &nbsp;|&nbsp; Reddit: {rd_status}</p>",
                unsafe_allow_html=True,
            )

            start_disabled = not (has_key and has_plugin)

            if st.button(
                "🚀  START JARVIS ENGINE",
                key="engine_start_btn",
                use_container_width=True,
                disabled=start_disabled,
                help="Launch all 5 workers with aggressive scheduling.",
                type="primary",
            ):
                engine.start()
                db.add_log("UI", "Engine started via Master Switch.", "info")
                st.success("🚀 Jarvis Engine started! Switch to Dashboard to monitor.")
                st.rerun()
        else:
            if st.button(
                "🛑  STOP ENGINE",
                key="engine_stop_btn",
                use_container_width=True,
                help="Stop signal — workers finish current cycle then exit.",
                type="secondary",
            ):
                engine.stop()
                db.add_log("UI", "Engine stopped via Master Switch.", "info")
                st.info("🛑 Stop signal sent. Workers winding down.")
                st.rerun()

    # Worker list when running
    if is_running:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 🔄 Active Workers")
        workers = [
            ("📧", "Contact Sniper", "Scraping forms & submitting pitches (every 35s)"),
            ("📝", "Blog Bomber", "Posting contextual blog comments (every 40s)"),
            ("▶️", "YouTube Hijacker", "Commenting on YouTube videos (every 50s)"),
            ("🔗", "Pingback Engine", "Sending XML-RPC pingbacks (every 55s)"),
            ("🤖", "Reddit Sniper", "Monitoring Reddit & posting replies (every 40s)"),
        ]
        for icon, name, desc in workers:
            st.markdown(
                f"""
                <div class="worker-row">
                    <span class="worker-dot">●</span>
                    <span class="worker-icon">{icon}</span>
                    <span class="worker-name">{name}</span>
                    <span class="worker-desc"> — {desc}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
