"""
ui_analytics.py — Per-Plugin Analytics (White + Green theme)
"""
import streamlit as st
from datetime import datetime
import database as db

PLATFORM_META = {
    "contact_form": ("📧", "Contact Forms", "#27ae60"),
    "blog_comment": ("📝", "Blog Comments", "#3498db"),
    "youtube":      ("▶️",  "YouTube",       "#e74c3c"),
    "pingback":     ("🔗", "Pingbacks",     "#e67e22"),
    "reddit":       ("🤖", "Reddit",        "#9b59b6"),
}


def render_analytics_tab() -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">🔌</span>
        <span class="sec-title">Plugin Analytics</span>
        <span class="sec-badge">PER PLUGIN</span>
    </div>
    """, unsafe_allow_html=True)

    plugins = db.get_all_plugins()
    if not plugins:
        st.markdown("""
        <div style="text-align:center; padding:60px; color:#aaa;
                    background:#f8fffe; border:1.5px dashed #c8f0dc;
                    border-radius:12px;">
            <div style="font-size:3rem; margin-bottom:12px;">🧩</div>
            <div style="font-size:1rem; font-weight:600; color:#1a1a2e;">
                No plugins added yet
            </div>
            <div style="font-size:0.82rem; margin-top:6px;">
                Go to ⚙️ Settings and add your first plugin.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Summary Table ─────────────────────────────────────────────
    summary = db.get_all_plugin_stats_summary()

    st.markdown("""
    <div style="font-size:0.72rem; font-weight:700; color:#aaa;
                text-transform:uppercase; letter-spacing:1px; margin-bottom:12px;">
        All Plugins Overview
    </div>
    """, unsafe_allow_html=True)

    # Header
    h1, h2, h3, h4, h5, h6, h7 = st.columns([3, 1, 1, 1, 1, 1, 2])
    headers = ["Plugin", "📧 Forms", "📝 Blogs", "▶️ YT", "🔗 Pings", "🤖 Reddit", "Last Action"]
    for col, txt in zip([h1,h2,h3,h4,h5,h6,h7], headers):
        with col:
            st.markdown(f"<div style='font-size:0.7rem;color:#aaa;font-weight:700;padding:4px 0;'>{txt}</div>",
                        unsafe_allow_html=True)

    st.markdown("<div style='border-bottom:2px solid #f0faf4; margin-bottom:6px;'></div>",
                unsafe_allow_html=True)

    for row in summary:
        c1,c2,c3,c4,c5,c6,c7 = st.columns([3,1,1,1,1,1,2])
        total = row["total_actions"] or 0
        try:
            last_str = datetime.fromisoformat(row["last_action"]).strftime("%m/%d %H:%M") \
                       if row["last_action"] else "—"
        except Exception:
            last_str = row["last_action"] or "—"

        with c1:
            st.markdown(f"""
            <div style="padding:7px 0;">
                <span style="font-size:0.88rem;font-weight:700;color:#1a1a2e;">{row['name']}</span>
                <span style="background:#e8f8f0;color:#27ae60;border-radius:4px;
                             padding:1px 7px;font-size:0.65rem;font-weight:700;
                             margin-left:6px;">{total:,} total</span>
            </div>
            """, unsafe_allow_html=True)

        for col, val in zip([c2,c3,c4,c5,c6],
                            [row["forms"], row["blog_comments"],
                             row["yt_comments"], row["pingbacks"], row["reddit_replies"]]):
            v = val or 0
            color = "#27ae60" if v > 0 else "#aaa"
            with col:
                st.markdown(f"<div style='font-size:0.88rem;font-weight:700;color:{color};padding:7px 0;'>{v:,}</div>",
                            unsafe_allow_html=True)
        with c7:
            st.markdown(f"<div style='font-size:0.75rem;color:#aaa;padding:7px 0;'>{last_str}</div>",
                        unsafe_allow_html=True)

        st.markdown("<div style='border-bottom:1px solid #f5f5f5;'></div>",
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Deep Dive ─────────────────────────────────────────────────
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">🔍</span>
        <span class="sec-title">Plugin Deep Dive</span>
    </div>
    """, unsafe_allow_html=True)

    plugin_names = {p["id"]: p["name"] for p in plugins}
    selected_name = st.selectbox(
        "Select plugin", list(plugin_names.values()),
        label_visibility="collapsed"
    )
    selected_id = next(pid for pid, n in plugin_names.items() if n == selected_name)
    plugin_obj  = next(p for p in plugins if p["id"] == selected_id)
    stats       = db.get_plugin_stats(selected_id)

    # Plugin info card
    st.markdown(f"""
    <div class="wg-card" style="margin-bottom:20px;">
        <div style="display:flex; align-items:flex-start; gap:20px; flex-wrap:wrap;">
            <div style="flex:1;">
                <div style="font-size:1.1rem; font-weight:700;
                            color:#1a1a2e; margin-bottom:4px;">
                    🧩 {plugin_obj['name']}
                </div>
                <div style="font-size:0.8rem; color:#888; margin-bottom:8px;">
                    {plugin_obj['description']}
                </div>
                <a href="{plugin_obj['shortlink']}" target="_blank"
                   style="font-size:0.78rem; color:#27ae60;
                          font-weight:600; text-decoration:none;">
                    🔗 {plugin_obj['shortlink']}
                </a>
            </div>
            <div style="text-align:center; min-width:90px;">
                <div style="font-size:2.5rem; font-weight:800;
                            color:#27ae60; line-height:1;">
                    {stats['total']:,}
                </div>
                <div style="font-size:0.7rem; color:#aaa; text-transform:uppercase;
                            letter-spacing:1px; margin-top:4px;">Total Actions</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Platform breakdown
    if stats["total"] > 0:
        cols = st.columns(5)
        for col, (platform, (icon, label, color)) in zip(cols, PLATFORM_META.items()):
            cnt = stats["by_platform"].get(platform, 0)
            pct = int(cnt / stats["total"] * 100) if stats["total"] > 0 else 0
            with col:
                st.markdown(f"""
                <div class="wg-card" style="border-top:3px solid {color};
                            text-align:center; padding:16px 10px;">
                    <div style="font-size:1.3rem; margin-bottom:4px;">{icon}</div>
                    <div style="font-size:1.5rem; font-weight:800;
                                color:{color}; margin-bottom:4px;">{cnt:,}</div>
                    <div style="font-size:0.7rem; color:#aaa; margin-bottom:8px;">{label}</div>
                    <div class="prog-bg">
                        <div class="prog-fill" style="width:{pct}%; background:{color};"></div>
                    </div>
                    <div style="font-size:0.65rem; color:#aaa; margin-top:4px;">{pct}%</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No actions recorded yet. Start the engine to begin tracking.")

    # Recent history
    if stats["recent"]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="sec-hdr">
            <span style="font-size:1.1rem;">📋</span>
            <span class="sec-title">Recent Actions History</span>
        </div>
        """, unsafe_allow_html=True)

        rows_html = ""
        for entry in stats["recent"]:
            icon, label, color = PLATFORM_META.get(
                entry["platform"], ("•", entry["platform"], "#888"))
            try:
                ts = datetime.fromisoformat(entry["created_at"]).strftime("%b %d  %H:%M:%S")
            except Exception:
                ts = entry["created_at"]
            url = entry["target_url"] or "—"
            url_disp = (url[:60] + "…") if len(url) > 60 else url

            rows_html += f"""
            <div style="display:grid; grid-template-columns:140px 150px 1fr;
                        gap:12px; padding:9px 14px; border-bottom:1px solid #f5f5f5;
                        align-items:center;">
                <span style="font-size:0.72rem; color:#aaa; font-family:monospace;">{ts}</span>
                <span style="font-size:0.78rem; color:{color};">{icon} {label}</span>
                <span style="font-size:0.72rem; color:#888;
                             overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                    {url_disp}
                </span>
            </div>
            """

        st.markdown(f"""
        <div style="background:#FFFFFF; border:1.5px solid #e8f8f0;
                    border-radius:10px; overflow:hidden;
                    max-height:300px; overflow-y:auto;">
            <div style="display:grid; grid-template-columns:140px 150px 1fr;
                        gap:12px; padding:8px 14px; background:#f8fffe;
                        font-size:0.68rem; font-weight:700; color:#aaa;
                        text-transform:uppercase; letter-spacing:0.5px;">
                <span>Timestamp</span>
                <span>Platform</span>
                <span>Target URL</span>
            </div>
            {rows_html}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        export = ["Timestamp,Platform,Action,Target URL"]
        for e in stats["recent"]:
            export.append(f"{e['created_at']},{e['platform']},{e['action']},{e['target_url']}")
        st.download_button(
            label=f"⬇️  Export {selected_name} history as CSV",
            data="\n".join(export),
            file_name=f"{selected_name.replace(' ', '_')}_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
