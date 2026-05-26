"""
ui_logs.py — Dedicated Live Logs Page
Full terminal with filtering, search, and export.
"""

import streamlit as st
from datetime import datetime
import database as db


def render_logs_tab() -> None:
    st.markdown("""
    <div class="section-hdr">
        <span class="sicon">📋</span>
        <span class="stitle">Live Activity Console</span>
        <span class="sbadge">REAL-TIME</span>
    </div>
    """, unsafe_allow_html=True)

    # Controls row
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        search = st.text_input("🔍 Filter logs", placeholder="Search worker name or message…",
                               label_visibility="collapsed")
    with c2:
        limit = st.selectbox("Lines", [50, 100, 200, 500], index=1,
                             label_visibility="collapsed")
    with c3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with c4:
        if st.button("🗑️ Clear All", use_container_width=True):
            conn = db.get_connection()
            conn.execute("DELETE FROM activity_logs")
            conn.commit()
            st.rerun()

    # Status filter
    status_filter = st.radio(
        "Status",
        ["All", "✅ Success", "❌ Error", "ℹ️ Info"],
        horizontal=True,
        label_visibility="collapsed",
    )

    # Fetch logs
    logs = db.get_recent_logs(limit)
    total_count = db.get_log_count()

    # Apply filters
    if search:
        logs = [l for l in logs
                if search.lower() in l["worker"].lower()
                or search.lower() in l["message"].lower()]
    if status_filter == "✅ Success":
        logs = [l for l in logs if l["status"] == "success"]
    elif status_filter == "❌ Error":
        logs = [l for l in logs if l["status"] == "error"]
    elif status_filter == "ℹ️ Info":
        logs = [l for l in logs if l["status"] == "info"]

    st.markdown(f"""
    <div style="font-size:0.72rem;color:#8b949e;margin-bottom:8px;">
        Showing <strong style="color:#e2e8f0;">{len(logs)}</strong> entries
        of <strong style="color:#e2e8f0;">{total_count:,}</strong> total
    </div>
    """, unsafe_allow_html=True)

    if not logs:
        st.markdown("""
        <div style="text-align:center;padding:40px;color:#8b949e;
                    background:#161b22;border-radius:10px;border:1px solid #21262d;">
            <div style="font-size:2rem;margin-bottom:8px;">📭</div>
            No logs match your filter.
        </div>
        """, unsafe_allow_html=True)
        return

    # Build terminal HTML
    lines_html = ""
    for entry in logs:
        try:
            ts = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
        except Exception:
            ts = entry["timestamp"]

        color = {"success": "#00ff88", "error": "#ef4444", "info": "#58a6ff"}.get(
            entry["status"], "#8b949e"
        )
        icon = {"success": "✅", "error": "❌", "info": "ℹ️"}.get(entry["status"], "•")
        msg = entry["message"].replace("<", "&lt;").replace(">", "&gt;")

        lines_html += f"""
        <div style="display:flex;gap:10px;padding:3px 0;align-items:flex-start;">
            <span style="color:#8b949e;font-family:monospace;min-width:68px;
                         font-size:0.72rem;">{ts}</span>
            <span style="min-width:14px;">{icon}</span>
            <span style="color:#8b949e;font-size:0.72rem;min-width:170px;
                         white-space:nowrap;">[{entry['worker']}]</span>
            <span style="color:{color};font-size:0.78rem;">{msg}</span>
        </div>
        """

    st.markdown(f"""
    <div style="background:#010409;border:1px solid #21262d;border-radius:10px;
                padding:16px 18px;max-height:500px;overflow-y:auto;
                font-family:'JetBrains Mono',monospace;">
        {lines_html}
    </div>
    """, unsafe_allow_html=True)

    # Export
    st.markdown("<br>", unsafe_allow_html=True)
    export_text = db.get_logs_as_text(limit)
    st.download_button(
        label="⬇️ Export logs as .txt",
        data=export_text,
        file_name=f"engine_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True,
    )
