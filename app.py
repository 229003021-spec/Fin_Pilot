import streamlit as st
from finpilot.db import FinPilotDB
from finpilot.demo_data import seed_demo_database, export_sample_files
from ui import (
    inject_custom_css,
    render_sidebar_navigation,
    render_command_center,
    render_money_page,
    render_intelligence_page,
    render_goals_page,
    render_simulator_page,
    render_ai_cfo_page,
    render_data_page
)

# Page Configuration
st.set_page_config(
    page_title="FinPilot - Financial Command Center",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Centralized Fintech Dark CSS System
inject_custom_css()

# Session State Initialization
if "db" not in st.session_state:
    st.session_state.db = FinPilotDB(":memory:")
    seed_demo_database(st.session_state.db)
    export_sample_files(".")

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
if "last_uploaded" not in st.session_state:
    st.session_state["last_uploaded"] = None
if "last_stats" not in st.session_state:
    st.session_state["last_stats"] = None
if "using_demo" not in st.session_state:
    st.session_state["using_demo"] = True
if "currency" not in st.session_state:
    st.session_state["currency"] = "$"

db = st.session_state.db

# Helper function for currency formatting
def fmt_money(val: float, currency: str = None) -> str:
    if currency is None:
        currency = st.session_state.get("currency", "$")
    v = float(val)
    if v < 0:
        return f"-{currency}{abs(v):,.2f}"
    return f"{currency}{v:,.2f}"

# Render Left Sidebar Navigation Rail with File Uploader
active_page = render_sidebar_navigation(db)

# Settings Submenu in Sidebar
with st.sidebar.expander("⚙ Currency & Preferences", expanded=False):
    currency_choice = st.selectbox(
        "Currency Symbol",
        options=["$", "₹", "€", "£"],
        index=["$", "₹", "€", "£"].index(st.session_state.get("currency", "$"))
    )
    st.session_state["currency"] = currency_choice

# Router to render active page canvas
if active_page == "Command Center":
    render_command_center(db, fmt_money)
elif active_page == "Money":
    render_money_page(db, fmt_money)
elif active_page == "Intelligence":
    render_intelligence_page(db, fmt_money)
elif active_page == "Goals":
    render_goals_page(db, fmt_money)
elif active_page == "Simulator":
    render_simulator_page(db, fmt_money)
elif active_page == "AI CFO":
    render_ai_cfo_page(db, fmt_money)
elif active_page == "Data":
    render_data_page(db, fmt_money)
elif active_page == "Settings":
    render_data_page(db, fmt_money)

# Global Footer Disclaimer
st.markdown("""
<div style="background: #131B2E; border-top: 1px solid #1E293B; padding: 12px; font-size: 0.8rem; color: #64748B; margin-top: 30px; text-align: center; border-radius: 8px;">
    <strong>⚖️ FinPilot Decision-Support Boundary:</strong> FinPilot provides data-driven decision support and financial pattern analysis based strictly on ingested data. FinPilot explicitly does not provide certified financial, investment, accounting, or legal tax advice.
</div>
""", unsafe_allow_html=True)
