"""
ui_reports.py — Action Reports Page (White + Green theme)
Shows every action taken: exact URL, generated text, plugin name, platform, timestamp.
Manual verification pe click karke dekh sako kahan post hua aur kya likha.
"""

import streamlit as st
from datetime import datetime
import database as db

# Platform metadata
PLATFORM_META = {
    "contact_form": ("📧", "Contact Form",  "#27ae60"),
    "blog_comment": ("📝", "Blog Comment",  "#3498db"),
    "youtube":      ("▶️",  "YouTube",       "#e74c3c"),
    "pingback":     ("🔗", "Pingback",      "#e67e22"),
    "reddit":       ("🤖", "Reddit",        "#9b59b6"),
}

STATUS_META = {
    "success": ("✅", "#27ae60", "#f0faf4", "#c8f0dc"),
    "dry_run": ("📝", "#e67e22", "#fff8f0", "#ffe8c8"),
    "error":   ("❌", "#e74c3c", "#fff0f0", "#ffd0d0"),
}


def render_reports_tab() -> None:
    # ── Header ──────────────────────────────────────────────────
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">📊</span>
        <span class="sec-title">Action Reports</span>
        <span class="sec-badge">FULL DETAILS</span>
    </div>
    <p style="font-size:0.82rem; color:#888; margin-bottom:20px;">
        Har action ka complete record — exact URL, generated text, plugin name.
        Click karke manually verify karo kahan post hua.
    </p>
    """, unsafe_allow_html=True)

    # ── Summary Cards ────────────────────────────────────────────
    platform_totals = db.get_platform_totals()
    total = sum(platform_totals.values())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    summary_cards = [
        (c1, "⚡", "Total Actions",   total,                                   "#27ae60"),
        (c2, "📧", "Contact Forms",   platform_totals.get("contact_form", 0),  "#27ae60"),
        (c3, "📝", "Blog Comments",   platform_totals.get("blog_comment", 0),  "#3498db"),
        (c4, "▶️",  "YouTube",         platform_totals.get("youtube", 0),       "#e74c3c"),
        (c5, "🔗", "Pingbacks",       platform_totals.get("pingback", 0),      "#e67e22"),
        (c6, "🤖", "Reddit",          platform_totals.get("reddit", 0),        "#9b59b6"),
    ]
    for col, icon, label, val, color in summary_cards:
        with col:
            st.markdown(f"""
            <div style="background:#FFFFFF; border:1.5px solid #e8f8f0;
                        border-top:3px solid {color}; border-radius:10px;
                        padding:14px 10px; text-align:center;
                        box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                <div style="font-size:1.2rem; margin-bottom:4px;">{icon}</div>
                <div style="font-size:1.5rem; font-weight:800; color:{color};">{val:,}</div>
                <div style="font-size:0.65rem; color:#aaa; font-weight:700;
                            text-transform:uppercase; letter-spacing:0.5px; margin-top:2px;">
                    {label}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Filters ──────────────────────────────────────────────────
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">🔍</span>
        <span class="sec-title">Filter & Search</span>
    </div>
    """, unsafe_allow_html=True)

    fc1, fc2, fc3, fc4 = st.columns([2, 2, 1, 1])
    with fc1:
        platform_opt = st.selectbox(
            "Platform",
            ["All Platforms", "📧 Contact Forms", "📝 Blog Comments",
             "▶️ YouTube", "🔗 Pingbacks", "🤖 Reddit"],
            label_visibility="collapsed",
        )
    with fc2:
        plugins = db.get_all_plugins()
        plugin_opts = ["All Plugins"] + [p["name"] for p in plugins]
        plugin_filter = st.selectbox("Plugin", plugin_opts, label_visibility="collapsed")
    with fc3:
        limit = st.selectbox("Show", [50, 100, 200, 500], label_visibility="collapsed")
    with fc4:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    # Map dropdown to DB key
    platform_map = {
        "All Platforms":    "",
        "📧 Contact Forms": "contact_form",
        "📝 Blog Comments": "blog_comment",
        "▶️ YouTube":        "youtube",
        "🔗 Pingbacks":     "pingback",
        "🤖 Reddit":        "reddit",
    }
    platform_key = platform_map.get(platform_opt, "")

    # Fetch actions
    actions = db.get_all_actions(limit=limit, platform_filter=platform_key)

    # Apply plugin filter
    if plugin_filter != "All Plugins":
        actions = [a for a in actions if a["plugin_name"] == plugin_filter]

    st.markdown("<br>", unsafe_allow_html=True)

    # ── No data state ─────────────────────────────────────────────
    if not actions:
        st.markdown("""
        <div style="text-align:center; padding:60px; color:#aaa;
                    background:#f8fffe; border:1.5px dashed #c8f0dc; border-radius:12px;">
            <div style="font-size:3rem; margin-bottom:12px;">📭</div>
            <div style="font-size:1rem; font-weight:600; color:#1a1a2e; margin-bottom:6px;">
                No actions recorded yet
            </div>
            <div style="font-size:0.82rem;">
                Start the engine and let it run — actions will appear here.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Actions count ─────────────────────────────────────────────
    st.markdown(f"""
    <div style="font-size:0.75rem; color:#888; margin-bottom:12px;">
        Showing <strong style="color:#1a1a2e;">{len(actions)}</strong> actions
    </div>
    """, unsafe_allow_html=True)

    # ── Action Cards ──────────────────────────────────────────────
    for action in actions:
        _render_action_card(action)

    # ── Export ────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _render_export(actions)


def _render_action_card(a: dict) -> None:
    """Render one action as a full-detail card."""
    platform_key = a.get("platform", "")
    icon, plabel, pcolor = PLATFORM_META.get(platform_key, ("•", platform_key, "#888"))

    status_key = a.get("status", "success")
    s_icon, s_color, s_bg, s_border = STATUS_META.get(
        status_key, ("•", "#888", "#fafafa", "#e0e0e0")
    )

    # Timestamp
    try:
        ts = datetime.fromisoformat(a["created_at"]).strftime("%b %d, %Y  %I:%M:%S %p")
    except Exception:
        ts = a.get("created_at", "—")

    target_url = a.get("target_url", "") or "—"
    gen_text   = a.get("generated_text", "") or ""
    plugin_name = a.get("plugin_name", "—")
    shortlink   = a.get("shortlink", "")

    # Truncate URL for display (full URL in href)
    url_display = target_url[:70] + "…" if len(target_url) > 70 else target_url

    st.markdown(f"""
    <div style="background:#FFFFFF; border:1.5px solid #e8f8f0;
                border-left:4px solid {pcolor}; border-radius:10px;
                padding:16px 18px; margin-bottom:12px;
                box-shadow:0 2px 8px rgba(0,0,0,0.04);">

        <!-- Row 1: Platform | Plugin | Status | Timestamp -->
        <div style="display:flex; align-items:center; gap:10px;
                    flex-wrap:wrap; margin-bottom:12px;">

            <span style="background:{pcolor}18; color:{pcolor};
                         border:1px solid {pcolor}44; border-radius:6px;
                         padding:3px 10px; font-size:0.75rem; font-weight:700;">
                {icon} {plabel}
            </span>

            <span style="background:#f0faf4; color:#27ae60;
                         border-radius:6px; padding:3px 10px;
                         font-size:0.75rem; font-weight:700;">
                🧩 {plugin_name}
            </span>

            <span style="background:{s_bg}; color:{s_color};
                         border:1px solid {s_border}; border-radius:6px;
                         padding:3px 10px; font-size:0.72rem; font-weight:700;">
                {s_icon} {status_key.upper().replace('_', ' ')}
            </span>

            <span style="margin-left:auto; font-size:0.72rem; color:#aaa;
                         font-family:monospace;">
                🕐 {ts}
            </span>
        </div>

        <!-- Row 2: Target URL -->
        <div style="margin-bottom:10px;">
            <div style="font-size:0.68rem; font-weight:700; color:#aaa;
                        text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">
                🎯 Target URL
            </div>
            <a href="{target_url}" target="_blank"
               style="font-size:0.82rem; color:#27ae60; font-weight:600;
                      text-decoration:none; word-break:break-all;
                      font-family:monospace;">
                {url_display}
            </a>
        </div>

        {'_gen_text_block(gen_text, shortlink)' if gen_text else ''}

    </div>
    """, unsafe_allow_html=True)

    # Generated text rendered separately (Streamlit HTML can't call Python)
    if gen_text:
        st.markdown(f"""
        <div style="background:#f8fffe; border:1px solid #e8f8f0;
                    border-radius:8px; padding:12px 14px; margin-top:-8px;
                    margin-bottom:12px; margin-left:0;">
            <div style="font-size:0.68rem; font-weight:700; color:#aaa;
                        text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">
                ✍️ Generated Content
                {f'&nbsp;<a href="{shortlink}" target="_blank" style="color:#27ae60; font-size:0.7rem; text-decoration:none;">[Plugin Link: {shortlink[:40]}]</a>' if shortlink else ''}
            </div>
            <div style="font-size:0.83rem; color:#1a1a2e; line-height:1.6;
                        white-space:pre-wrap; word-break:break-word;">
                {gen_text.replace("<", "&lt;").replace(">", "&gt;")}
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_export(actions: list[dict]) -> None:
    """Export buttons — CSV and TXT."""
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">⬇️</span>
        <span class="sec-title">Export Report</span>
    </div>
    """, unsafe_allow_html=True)

    ec1, ec2 = st.columns(2)

    # CSV export
    csv_lines = ["Timestamp,Platform,Plugin,Status,Target URL,Generated Text"]
    for a in actions:
        gen = (a.get("generated_text") or "").replace('"', '""').replace("\n", " ")
        url = (a.get("target_url") or "").replace('"', '""')
        csv_lines.append(
            f'"{a.get("created_at","")}","{a.get("platform","")}","'
            f'{a.get("plugin_name","")}","{a.get("status","")}","{url}","{gen}"'
        )
    with ec1:
        st.download_button(
            label="⬇️  Export as CSV",
            data="\n".join(csv_lines),
            file_name=f"action_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary",
        )

    # TXT export
    txt_lines = [f"AI MARKETING ENGINE — ACTION REPORT",
                 f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}",
                 f"Total Actions: {len(actions)}", "=" * 70]
    for a in actions:
        try:
            ts = datetime.fromisoformat(a["created_at"]).strftime("%b %d %Y %I:%M:%S %p")
        except Exception:
            ts = a.get("created_at", "")
        txt_lines += [
            f"\n[{ts}]",
            f"Platform  : {a.get('platform', '')}",
            f"Plugin    : {a.get('plugin_name', '')}",
            f"Status    : {a.get('status', '')}",
            f"Target URL: {a.get('target_url', '')}",
            f"Generated :",
            f"{a.get('generated_text', '')}",
            "-" * 70,
        ]
    with ec2:
        st.download_button(
            label="⬇️  Export as TXT",
            data="\n".join(txt_lines),
            file_name=f"action_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
