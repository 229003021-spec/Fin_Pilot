import streamlit as st

def render_sidebar_navigation(db=None) -> str:
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
    
    # Data Ingestion File Uploader in Sidebar
    st.sidebar.caption("📥 DATA INGESTION")

    uploaded_file = st.sidebar.file_uploader(
        "Upload Bank/Credit Statement",
        type=["csv", "json", "pdf"],
        key=f"sidebar_uploader_{st.session_state.get('uploader_key', 0)}",
        help="Supports CSV statements, JSON exports, and PDF bank statements."
    )

    if uploaded_file is not None and db is not None:
        file_bytes = uploaded_file.getvalue()
        file_size = len(file_bytes)
        file_key = f"{uploaded_file.name}:{file_size}"

        if st.session_state.get("last_uploaded") != file_key:
            try:
                from finpilot.ingestion.processor import BackgroundDocumentProcessor
                bg_processor = BackgroundDocumentProcessor()
                res = bg_processor.process_document(file_bytes, filename=uploaded_file.name)
                txs = res["transactions"]
                stats = res["stats"]

                if txs:
                    if st.session_state.get("using_demo", True):
                        db.clear_all()
                        st.session_state["using_demo"] = False

                    db.insert_transactions(txs)
                    st.session_state["last_uploaded"] = file_key
                    st.session_state["last_stats"] = stats
                    st.sidebar.success(f"Successfully processed {stats.total_transactions} records!")
                    st.rerun()
                else:
                    msg = stats.message if stats and stats.message else f"No valid transaction rows identified."
                    st.sidebar.error(msg)
            except Exception as e:
                st.sidebar.error(f"Failed to process document: {str(e)}")

    st.sidebar.markdown("---")

    # Session mode indicator
    if st.session_state.get("using_demo", True):
        st.sidebar.info("ℹ️ **Data Mode**: Using demo data")
    else:
        st.sidebar.success("✅ **Data Mode**: Custom uploaded data")

    st.sidebar.markdown("---")
    st.sidebar.caption("🔒 **Privacy Notice**: Session-only memory. No data is stored externally.")

    return st.session_state["fp_active_page"]
