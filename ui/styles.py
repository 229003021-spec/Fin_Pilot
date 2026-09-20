import streamlit as st

def inject_custom_css():
    """Injects custom CSS styling for the FinPilot fintech command center."""
    st.markdown("""
    <style>
    /* Global Container Theme */
    .stApp {
        background-color: #0B0E14;
        color: #E2E8F0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top Bar Styling */
    .fp-topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: linear-gradient(135deg, #131B2E 0%, #0F172A 100%);
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 16px 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .fp-topbar-title {
        font-size: 1.4rem;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: #F8FAFC;
        margin: 0;
    }
    .fp-topbar-sub {
        font-size: 0.85rem;
        color: #94A3B8;
        margin-top: 2px;
    }
    .fp-status-badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    .fp-status-ready {
        background: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .fp-status-demo {
        background: rgba(59, 130, 246, 0.15);
        color: #60A5FA;
        border: 1px solid rgba(96, 165, 250, 0.3);
    }
    
    /* Cards */
    .fp-card {
        background: #131B2E;
        border: 1px solid #1E293B;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .fp-card:hover {
        border-color: #334155;
    }
    .fp-card-hero {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
    }
    
    /* Metric Cards */
    .fp-metric-card {
        background: #131B2E;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 18px;
        height: 100%;
    }
    .fp-metric-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94A3B8;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .fp-metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #F8FAFC;
        margin-bottom: 4px;
    }
    .fp-metric-sub {
        font-size: 0.75rem;
        color: #64748B;
    }
    
    /* FinPilot Insight Box */
    .fp-insight-card {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.08) 0%, rgba(30, 58, 138, 0.12) 100%);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 20px;
    }
    .fp-insight-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #38BDF8;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .fp-insight-text {
        font-size: 0.9rem;
        color: #E2E8F0;
        line-height: 1.5;
    }
    
    /* Attention Cards */
    .fp-alert-card {
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 12px;
        border-left: 4px solid #E2E8F0;
        background: #1E293B;
    }
    .fp-alert-high {
        border-left-color: #EF4444;
        background: rgba(239, 68, 68, 0.08);
    }
    .fp-alert-medium {
        border-left-color: #F59E0B;
        background: rgba(245, 158, 11, 0.08);
    }
    .fp-alert-info {
        border-left-color: #3B82F6;
        background: rgba(59, 130, 246, 0.08);
    }
    
    /* Sidebar styling overrides */
    section[data-testid="stSidebar"] {
        background-color: #0B0F19;
        border-right: 1px solid #1E293B;
    }
    
    /* Clean up button hover states */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    </style>
    """, unsafe_allow_html=True)
