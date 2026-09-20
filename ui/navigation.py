import streamlit as st

def render_sidebar_navigation() -> str:
    """Renders the persistent left navigation rail and returns the active page name."""
    if "fp_active_page" not in st.session_state:
        st.session_state["fp_active_page"] = "Command Center"
        
    st.sidebar.markdown("""
    <div style="padding-bottom: 12px;">
        <h2 style="font-size: 1.4rem; font-weight: 900; color: #38BDF8; margin: 0; display: flex; align-items: center; gap: 8px;">
            ✦ FINPILOT
        </h2>
        <div style="font-size: 0.8rem; color: #64748B; font-weight: 500;">Your Financial Copilot</div>
    </div>
    """, unsafe_allow_html=True)

    pages = [
        ("Command Center", "◉ Command Center"),
        ("Money", "◇ Money"),
        ("Intelligence", "⚠️ Intelligence"),
        ("Goals", "🎯 Goals"),
        ("Simulator", "◌ Simulator"),
        ("AI CFO", "✦ AI CFO"),
        ("Data", "▣ Data"),
        ("Settings", "⚙ Settings")
    ]

    current_page = st.session_state["fp_active_page"]

    st.sidebar.markdown("---")
    st.sidebar.caption("NAVIGATION")

    for page_id, page_label in pages:
        # Use button with highlight if active
        btn_type = "primary" if current_page == page_id else "secondary"
        if st.sidebar.button(page_label, key=f"nav_btn_{page_id}", use_container_width=True, type=btn_type):
            st.session_state["fp_active_page"] = page_id
            st.rerun()

    st.sidebar.markdown("---")
    
    # Session mode indicator
    if st.session_state.get("using_demo", True):
        st.sidebar.info("ℹ️ **Data Mode**: Using demo data")
    else:
        st.sidebar.success("✅ **Data Mode**: Custom uploaded data")

    st.sidebar.markdown("---")
    st.sidebar.caption("🔒 **Privacy Notice**: Session-only memory. No data is stored externally.")

    return st.session_state["fp_active_page"]
