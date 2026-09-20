import streamlit as st
import pandas as pd
from ui.components import render_topbar, render_hero_header, render_empty_state
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector
from finpilot.agent.privacy import PrivacyMasker

def render_intelligence_page(db, fmt_money_fn):
    """Renders the Intelligence page for anomalies, subscriptions, and spending patterns."""
    is_demo = st.session_state.get("using_demo", True)
    render_topbar(is_demo=is_demo)
    render_hero_header("⚠️ INTELLIGENCE & PATTERNS", "Detected unusual activity, recurring bills, and spending anomalies.")

    df = db.get_transactions_df()
    if df.empty:
        render_empty_state("No Analytics Data", "Upload financial records to scan for subscriptions and anomalies.", "🔍")
        return

    col_sub, col_anom = st.columns([1, 1])

    with col_sub:
        st.subheader("🔄 Recurring Subscriptions")
        subs = SubscriptionTracker.detect_subscriptions(df)
        if subs:
            total_mo = sum(s.average_amount for s in subs if s.frequency == 'monthly')
            st.metric("Total Monthly Subscription Cost", fmt_money_fn(total_mo))
            st.markdown("<br>", unsafe_allow_html=True)
            
            for s in subs:
                masked_vendor = PrivacyMasker.mask_text(s.vendor)
                var_str = f"{s.price_variance_pct:.1f}% variance" if hasattr(s, 'price_variance_pct') else "Stable"
                st.markdown(f"""
                <div class="fp-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-weight: 700; font-size: 1.1rem; color: #F8FAFC;">{masked_vendor}</div>
                        <div style="font-weight: 800; font-size: 1.1rem; color: #38BDF8;">{fmt_money_fn(s.average_amount)}</div>
                    </div>
                    <div style="font-size: 0.85rem; color: #94A3B8; margin-top: 4px;">
                        Category: {s.category} | Frequency: {s.frequency} | {var_str}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No recurring monthly or annual subscription patterns detected.")

    with col_anom:
        st.subheader("🚩 Flagged Spending Anomalies")
        anomalies = AnomalyDetector.detect_anomalies(df)
        if anomalies:
            for a in anomalies:
                masked_vendor = PrivacyMasker.mask_text(a.vendor)
                masked_reason = PrivacyMasker.mask_text(a.reason)
                card_class = "fp-alert-high" if a.severity == "HIGH" else "fp-alert-medium"
                badge_text = f"[{a.severity}]"
                
                st.markdown(f"""
                <div class="fp-alert-card {card_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="font-weight: 800; color: #F8FAFC;">{badge_text} {masked_vendor}</span>
                        <span style="font-size: 0.8rem; background: #334155; color: #E2E8F0; padding: 2px 8px; border-radius: 4px;">{a.category}</span>
                    </div>
                    <div style="font-size: 0.88rem; color: #CBD5E1;">{masked_reason}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No unusual spending spikes (>2.5x std deviation) or MoM surges detected.")
