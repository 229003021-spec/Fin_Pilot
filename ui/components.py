import streamlit as st

def render_topbar(is_demo: bool = True):
    """Renders the top bar header for the FinPilot Command Center shell."""
    status_html = '<span class="fp-status-badge fp-status-demo">● DEMO DATA</span>' if is_demo else '<span class="fp-status-badge fp-status-ready">● DATA READY</span>'
    st.markdown(f"""
    <div class="fp-topbar">
        <div>
            <div class="fp-topbar-title">✦ FINPILOT</div>
            <div class="fp-topbar-sub">Financial Command Center</div>
        </div>
        <div>
            {status_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_hero_header(title: str, subtitle: str):
    """Renders a prominent hero banner."""
    st.markdown(f"""
    <div style="margin-bottom: 24px;">
        <h1 style="font-size: 2.1rem; font-weight: 900; margin-bottom: 4px; color: #F8FAFC;">{title}</h1>
        <p style="font-size: 1rem; color: #94A3B8; margin: 0;">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def render_metric_card(label: str, value: str, subtext: str = ""):
    """Renders a clean fintech metric card."""
    sub_html = f'<div class="fp-metric-sub">{subtext}</div>' if subtext else ""
    st.markdown(f"""
    <div class="fp-metric-card">
        <div class="fp-metric-label">{label}</div>
        <div class="fp-metric-value">{value}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_insight_card(title: str, body: str):
    """Renders a FinPilot Proactive Insight Card."""
    st.markdown(f"""
    <div class="fp-insight-card">
        <div class="fp-insight-title">✦ {title}</div>
        <div class="fp-insight-text">{body}</div>
    </div>
    """, unsafe_allow_html=True)


def render_empty_state(title: str, description: str, icon: str = "📂"):
    """Renders a clean empty state card."""
    st.markdown(f"""
    <div style="text-align: center; padding: 40px 20px; background: #131B2E; border: 1px dashed #334155; border-radius: 14px; margin: 20px 0;">
        <div style="font-size: 2.5rem; margin-bottom: 12px;">{icon}</div>
        <h3 style="font-size: 1.2rem; font-weight: 700; color: #F8FAFC; margin-bottom: 6px;">{title}</h3>
        <p style="font-size: 0.9rem; color: #94A3B8; margin: 0;">{description}</p>
    </div>
    """, unsafe_allow_html=True)
