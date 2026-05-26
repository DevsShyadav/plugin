"""
ui_logs.py — Live Logs Page (White + Green theme)
"""
import streamlit as st
from datetime import datetime
import database as db


def render_logs_tab() -> None:
    st.markdown("""
    <div class="sec-hdr">
        <span style="font-size:1.1rem;">📋</span>
        <span class="sec-title">Live Activity Console</span>
        <span class="sec-badge">REAL-TIME</span>
    </div>
    """, unsafe_allow_html=True)

    # Controls
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        search = st.text_input("", placeholder="🔍  Search worker or message…",
                               label_visibility="collapsed")
    with c2:
        limit = st.selectbox("", [50, 100, 200, 500], index=1,
                             label_visibility="collapsed")
    with c3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with c4:
        if st.button("🗑️ Clear", use_container_width=True):
            conn = db.get_connection()
            conn.execute("DELETE FROM activity_logs")
            conn.commit()
            st.rerun()

    # Status filter
    status_filter = st.radio(
        "", ["All", "✅ Success", "❌ Error", "ℹ️ Info"],
        horizontal=True, label_visibility="collapsed"
    )

    logs = db.get_recent_logs(limit)
    total_count = db.get_log_count()

    # Apply filters
    if search:
        logs = [l for l in logs if
                search.lower() in l["worker"].lower() or
                search.lower() in l["message"].lower()]
    if status_filter == "✅ Success":
        logs = [l for l in logs if l["status"] == "success"]
    elif status_filter == "❌ Error":
        logs = [l for l in logs if l["status"] == "error"]
    elif status_filter == "ℹ️ Info":
        logs = [l for l in logs if l["status"] == "info"]

    st.markdown(f"""
    <div style="font-size:0.72rem; color:#aaa; margin-bottom:8px;">
        Showing <strong style="color:#1a1a2e;">{len(logs)}</strong> of
        <strong style="color:#1a1a2e;">{total_count:,}</strong> total entries
    </div>
    """, unsafe_allow_html=True)

    if not logs:
        st.markdown("""
        <div style="text-align:center; padding:40px; color:#aaa;
                    background:#f8fffe; border:1.5px solid #e8f8f0;
                    border-radius:10px;">
            <div style="font-size:2rem; margin-bottom:8px;">📭</div>
            No logs match your filter.
        </div>
        """, unsafe_allow_html=True)
        return

    # Terminal box
    lines_html = ""
    for entry in logs:
        try:
            ts = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
        except Exception:
            ts = entry["timestamp"]

        color = {"success": "#27ae60", "error": "#e74c3c",
                 "info": "#3498db"}.get(entry["status"], "#888")
        icon  = {"success": "✅", "error": "❌", "info": "ℹ️"}.get(entry["status"], "•")
        msg   = entry["message"].replace("<", "&lt;").replace(">", "&gt;")

        lines_html += f"""
        <div style="display:flex; gap:10px; padding:4px 0;
                    border-bottom:1px solid #1a1a1a; align-items:flex-start;">
            <span style="color:#666; font-family:monospace; min-width:68px;
                         font-size:0.72rem; white-space:nowrap;">{ts}</span>
            <span style="min-width:16px; font-size:0.78rem;">{icon}</span>
            <span style="color:#666; font-size:0.7rem; min-width:175px;
                         white-space:nowrap;">[{entry['worker'][:24]}]</span>
            <span style="color:{color}; font-size:0.78rem;">{msg}</span>
        </div>
        """

    st.markdown(f"""
    <div class="log-terminal">{lines_html}</div>
    """, unsafe_allow_html=True)

    # Export
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        label="⬇️  Export logs as .txt",
        data=db.get_logs_as_text(limit),
        file_name=f"engine_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True,
    )
