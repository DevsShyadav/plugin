"""
ui_analytics.py — Per-Plugin Analytics Dashboard
Every plugin has its own stats: total actions, platform breakdown,
recent posts history, and daily activity trend.
"""

import streamlit as st
from datetime import datetime
import database as db

PLATFORM_META = {
    "contact_form": ("📧", "Contact Forms", "#3b82f6"),
    "blog_comment": ("📝", "Blog Comments", "#8b5cf6"),
    "youtube":      ("▶️",  "YouTube",       "#ef4444"),
    "pingback":     ("🔗", "Pingbacks",     "#f59e0b"),
    "reddit":       ("🤖", "Reddit",        "#00ff88"),
}


def render_analytics_tab() -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">🔌</span>
        <span class="stitle">Plugin Analytics</span>
        <span class="sbadge">PER PLUGIN</span>
    </div>
    """, unsafe_allow_html=True)

    plugins = db.get_all_plugins()
    if not plugins:
        st.markdown("""
        <div style="text-align:center;padding:60px;color:#8b949e;">
            <div style="font-size:3rem;margin-bottom:12px;">🧩</div>
            <div style="font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:6px;">
                No plugins added yet
            </div>
            Go to ⚙️ Settings and add your first plugin.
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Summary table ────────────────────────────────────────────
    summary = db.get_all_plugin_stats_summary()

    st.markdown("""
    <div style="font-size:0.75rem;font-weight:700;color:#8b949e;
                text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">
        All Plugins Overview
    </div>
    """, unsafe_allow_html=True)

    # Header row
    h1, h2, h3, h4, h5, h6, h7 = st.columns([3, 1, 1, 1, 1, 1, 2])
    for col, txt in zip([h1,h2,h3,h4,h5,h6,h7],
                        ["Plugin","📧 Forms","📝 Blogs","▶️ YT","🔗 Pings","🤖 Reddit","Last Action"]):
        with col:
            st.markdown(f"<div style='font-size:0.72rem;color:#8b949e;font-weight:700;padding:4px 0;'>{txt}</div>",
                        unsafe_allow_html=True)

    st.markdown("<div style='border-bottom:1px solid #21262d;margin-bottom:6px;'></div>",
                unsafe_allow_html=True)

    for row in summary:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 1, 1, 1, 1, 1, 2])

        total = row["total_actions"] or 0
        last  = row["last_action"]
        try:
            last_str = datetime.fromisoformat(last).strftime("%m/%d %H:%M") if last else "—"
        except Exception:
            last_str = last or "—"

        with c1:
            st.markdown(f"""
            <div style="padding:6px 0;">
                <span style="font-size:0.85rem;font-weight:600;color:#e2e8f0;">{row['name']}</span>
                <span class="plugin-badge" style="margin-left:8px;">{total:,} total</span>
            </div>
            """, unsafe_allow_html=True)

        for col, val in zip([c2,c3,c4,c5,c6],
                            [row["forms"], row["blog_comments"],
                             row["yt_comments"], row["pingbacks"], row["reddit_replies"]]):
            with col:
                v = val or 0
                color = "#00ff88" if v > 0 else "#8b949e"
                st.markdown(f"<div style='font-size:0.85rem;font-weight:700;color:{color};padding:6px 0;'>{v:,}</div>",
                            unsafe_allow_html=True)
        with c7:
            st.markdown(f"<div style='font-size:0.75rem;color:#8b949e;padding:6px 0;'>{last_str}</div>",
                        unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Per-plugin deep dive ─────────────────────────────────────
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">🔍</span>
        <span class="stitle">Plugin Deep Dive</span>
    </div>
    """, unsafe_allow_html=True)

    plugin_names = {p["id"]: p["name"] for p in plugins}
    selected_name = st.selectbox(
        "Select plugin to inspect",
        options=list(plugin_names.values()),
        label_visibility="collapsed",
    )
    selected_id = next(pid for pid, name in plugin_names.items() if name == selected_name)
    plugin_obj  = next(p for p in plugins if p["id"] == selected_id)
    stats       = db.get_plugin_stats(selected_id)

    # Plugin info header
    st.markdown(f"""
    <div class="premium-card" style="margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
            <div style="flex:1;">
                <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-bottom:4px;">
                    🧩 {plugin_obj['name']}
                </div>
                <div style="font-size:0.8rem;color:#8b949e;margin-bottom:6px;">
                    {plugin_obj['description']}
                </div>
                <a href="{plugin_obj['shortlink']}" target="_blank"
                   style="font-size:0.78rem;color:#00ff88;text-decoration:none;
                          font-family:monospace;">
                    🔗 {plugin_obj['shortlink']}
                </a>
            </div>
            <div style="text-align:center;min-width:80px;">
                <div style="font-size:2.4rem;font-weight:800;color:#00ff88;">
                    {stats['total']:,}
                </div>
                <div style="font-size:0.72rem;color:#8b949e;text-transform:uppercase;
                            letter-spacing:1px;">Total Actions</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Platform breakdown cards
    if stats["total"] > 0:
        cols = st.columns(5)
        for col, (platform, (icon, label, color)) in zip(cols, PLATFORM_META.items()):
            cnt = stats["by_platform"].get(platform, 0)
            pct = int(cnt / stats["total"] * 100) if stats["total"] > 0 else 0
            with col:
                st.markdown(f"""
                <div class="premium-card" style="text-align:center;padding:16px 10px;
                            border-top:3px solid {color};">
                    <div style="font-size:1.2rem;margin-bottom:4px;">{icon}</div>
                    <div style="font-size:1.5rem;font-weight:800;color:{color};">{cnt:,}</div>
                    <div style="font-size:0.68rem;color:#8b949e;margin:4px 0;">{label}</div>
                    <div class="prog-bar-bg">
                        <div class="prog-bar-fill"
                             style="width:{pct}%;background:{color};"></div>
                    </div>
                    <div style="font-size:0.65rem;color:#8b949e;margin-top:4px;">{pct}%</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:30px;color:#8b949e;
                    background:#161b22;border-radius:10px;border:1px solid #21262d;">
            No actions recorded yet for this plugin.
            Start the engine to begin tracking.
        </div>
        """, unsafe_allow_html=True)

    # Recent actions history
    if stats["recent"]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="section-hdr">
            <span class="sicon">📋</span>
            <span class="stitle">Recent Actions History</span>
        </div>
        """, unsafe_allow_html=True)

        rows_html = ""
        for entry in stats["recent"]:
            icon, label, color = PLATFORM_META.get(
                entry["platform"], ("•", entry["platform"], "#8b949e")
            )
            try:
                ts = datetime.fromisoformat(entry["created_at"]).strftime("%b %d  %H:%M:%S")
            except Exception:
                ts = entry["created_at"]

            url = entry["target_url"] or "—"
            url_display = (url[:55] + "…") if len(url) > 55 else url

            rows_html += f"""
            <div style="display:grid;grid-template-columns:130px 140px 1fr;
                        gap:12px;padding:9px 14px;border-bottom:1px solid #0d1117;
                        align-items:center;">
                <span style="font-size:0.72rem;color:#8b949e;font-family:monospace;">{ts}</span>
                <span style="font-size:0.78rem;color:{color};">{icon} {label}</span>
                <span style="font-size:0.72rem;color:#8b949e;
                             overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                    {url_display}
                </span>
            </div>
            """

        st.markdown(f"""
        <div style="background:#0d1117;border:1px solid #21262d;border-radius:10px;
                    overflow:hidden;max-height:320px;overflow-y:auto;">
            <div style="display:grid;grid-template-columns:130px 140px 1fr;
                        gap:12px;padding:8px 14px;background:#161b22;
                        font-size:0.68rem;font-weight:700;color:#8b949e;
                        text-transform:uppercase;letter-spacing:0.5px;">
                <span>Timestamp</span>
                <span>Platform</span>
                <span>Target URL</span>
            </div>
            {rows_html}
        </div>
        """, unsafe_allow_html=True)

        # Export button
        st.markdown("<br>", unsafe_allow_html=True)
        export_lines = ["Timestamp,Platform,Action,Target URL"]
        for e in stats["recent"]:
            export_lines.append(
                f"{e['created_at']},{e['platform']},{e['action']},{e['target_url']}"
            )
        st.download_button(
            label=f"⬇️ Export {selected_name} history as CSV",
            data="\n".join(export_lines),
            file_name=f"{selected_name.replace(' ', '_')}_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
