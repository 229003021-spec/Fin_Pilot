import streamlit as st
from ui.components import render_topbar, render_hero_header
from finpilot.ingestion.processor import BackgroundDocumentProcessor
from finpilot.demo_data import seed_demo_database

def render_data_page(db, fmt_money_fn):
    """Renders the Data Ingestion and Management page."""
    is_demo = st.session_state.get("using_demo", True)
    render_topbar(is_demo=is_demo)
    render_hero_header("▣ DATA INGESTION & QUALITY", "Upload CSV statements, JSON exports, or PDF bank statements.")

    # Upload Section Card
    st.markdown("### 📥 Import Document")
    uploaded_file = st.file_uploader(
        "Upload Bank / Credit Statement",
        type=["csv", "json", "pdf"],
        key=f"file_uploader_{st.session_state.get('uploader_key', 0)}",
        help="Upload CSV, JSON, or PDF statement files."
    )

    bg_processor = BackgroundDocumentProcessor()

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_size = len(file_bytes)
        file_key = f"{uploaded_file.name}:{file_size}"

        if st.session_state.get("last_uploaded") != file_key:
            try:
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
                    st.success(f"Successfully processed {stats.total_transactions} records from {uploaded_file.name}!")
                    st.rerun()
                else:
                    msg = stats.message if stats and stats.message else f"No valid transaction rows identified in {uploaded_file.name}."
                    st.error(msg)
            except Exception as e:
                st.error(f"Failed to process document: {str(e)}")

    # Display Data Quality Stats if available
    if st.session_state.get("last_stats"):
        stats = st.session_state["last_stats"]
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📊 Document Quality & Analytics Health")
        
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.metric("Format & Confidence", f"{stats.file_format}", f"{stats.parsing_confidence_pct}% score")
        with d2:
            st.metric("Total Records", stats.total_transactions, f"{stats.date_range_start} to {stats.date_range_end}")
        with d3:
            st.metric("Gross Inflow", fmt_money_fn(stats.gross_income))
        with d4:
            st.metric("Gross Outflow", fmt_money_fn(stats.gross_expenses))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ⚙️ Database Controls")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if st.button("🔄 Reload Demo Data", use_container_width=True):
            seed_demo_database(db)
            st.session_state["last_uploaded"] = None
            st.session_state["last_stats"] = None
            st.session_state["using_demo"] = True
            st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
            st.success("Demo database reloaded!")
            st.rerun()

    with col_d2:
        with st.popover("🗑️ Clear All Database Data", use_container_width=True):
            st.warning("This will permanently clear all loaded transactions, budgets, and goals for this session.")
            if st.button("Confirm Clear All Data", type="primary", use_container_width=True):
                db.clear_all()
                st.session_state["last_uploaded"] = None
                st.session_state["last_stats"] = None
                st.session_state["using_demo"] = False
                st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
                st.success("Database cleared.")
                st.rerun()
