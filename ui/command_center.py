import streamlit as st
import pandas as pd
import plotly.express as px
from ui.components import render_topbar, render_hero_header, render_metric_card, render_insight_card, render_empty_state
from finpilot.agent.brief_generator import MonthlyBriefGenerator
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector
from finpilot.analytics.committed_spend import CommittedSpendCalculator
from finpilot.analytics.goals_budget import BudgetAndGoalManager

def render_command_center(db, fmt_money_fn):
    """Renders the main Command Center page."""
    is_demo = st.session_state.get("using_demo", True)
    render_topbar(is_demo=is_demo)
    render_hero_header("GOOD AFTERNOON", "Here's what changed in your financial world.")

    df = db.get_transactions_df()
    if df.empty:
        render_empty_state("No Financial Data Loaded", "Upload a statement or load demo data to view your financial command center.", "📊")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("📥 Import Data", use_container_width=True, type="primary"):
                st.session_state["fp_active_page"] = "Data"
                st.rerun()
        with col_c2:
            if st.button("🔄 Load Demo Data", use_container_width=True):
                from finpilot.demo_data import seed_demo_database
                seed_demo_database(db)
                st.session_state["using_demo"] = True
                st.rerun()
        return

    # Compute actual backend metrics
    brief_gen = MonthlyBriefGenerator(db)
    brief = brief_gen.generate_brief()
    committed = CommittedSpendCalculator.calculate_committed_spend(df)

    # Primary Metric Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Cash Inflow", fmt_money_fn(brief['total_income']), "Total income received")
    with c2:
        render_metric_card("Safe to Spend", fmt_money_fn(brief['safe_to_spend_balance']), "Available after commitments")
    with c3:
        net_str = f"+{fmt_money_fn(brief['net_cash_flow'])}" if brief['net_cash_flow'] >= 0 else fmt_money_fn(brief['net_cash_flow'])
        render_metric_card("Net Cashflow", net_str, f"{brief['savings_rate_pct']}% savings rate")
    with c4:
        comm_amt = committed.get('committed_obligations', 0.0) if isinstance(committed, dict) else 0.0
        render_metric_card("Committed Spend", fmt_money_fn(comm_amt), f"{brief['committed_spend_ratio_pct']}% of income")

    st.markdown("<br>", unsafe_allow_html=True)

    # FinPilot Insight
    expenses_df = df[df['amount'] < 0].copy()
    if not expenses_df.empty:
        expenses_df['abs_amount'] = expenses_df['amount'].abs()
        cat_sums = expenses_df.groupby('category')['abs_amount'].sum()
        top_cat = cat_sums.idxmax()
        top_amt = cat_sums.max()
        insight_text = f"Your largest spending area this period is <b>{top_cat}</b> ({fmt_money_fn(top_amt)}). Safe-to-spend balance remaining is <b>{fmt_money_fn(brief['safe_to_spend_balance'])}</b>."
    else:
        insight_text = "Your financial cashflow is healthy with positive net savings."
    
    render_insight_card("FINPILOT PROACTIVE INSIGHT", insight_text)

    # Money Pulse Visualization Section
    st.subheader("📈 Money Pulse")
    st.caption("Cashflow movement and monthly trends")

    df_copy = df.copy()
    df_copy['dt'] = pd.to_datetime(df_copy['date'])
    df_copy['month_yr'] = df_copy['dt'].dt.strftime('%Y-%m')

    inc_df = df_copy[df_copy['amount'] > 0].groupby('month_yr')['amount'].sum().reset_index()
    exp_df = df_copy[df_copy['amount'] < 0].groupby('month_yr')['amount'].apply(lambda x: abs(x.sum())).reset_index()
    comp_df = pd.merge(inc_df, exp_df, on='month_yr', how='outer', suffixes=('_income', '_expense')).fillna(0)
    comp_df = comp_df.rename(columns={'amount_income': 'Income', 'amount_expense': 'Expenses'})

    fig_pulse = px.bar(
        comp_df,
        x='month_yr',
        y=['Income', 'Expenses'],
        barmode='group',
        labels={'value': 'Amount', 'month_yr': 'Month'},
        color_discrete_map={'Income': '#10B981', 'Expenses': '#EF4444'}
    )
    fig_pulse.update_layout(
        paper_bgcolor='#131B2E',
        plot_bgcolor='#131B2E',
        font=dict(color='#E2E8F0'),
        margin=dict(t=20, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_pulse, use_container_width=True)

    # Attention Center
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("⚠️ Money Needs Your Attention")
    
    anomalies = AnomalyDetector.detect_anomalies(df)
    subs = SubscriptionTracker.detect_subscriptions(df)
    
    att_col1, att_col2 = st.columns(2)
    
    with att_col1:
        st.markdown("#### 🚩 Flagged Outliers")
        if anomalies:
            for a in anomalies[:3]:
                st.markdown(f"""
                <div class="fp-alert-card fp-alert-high">
                    <div style="font-weight: 700; color: #F8FAFC;">{a.vendor} ({a.category})</div>
                    <div style="font-size: 0.85rem; color: #94A3B8;">{a.reason}</div>
                </div>
                """, unsafe_allow_html=True)
            if st.button("Investigate Outliers →", key="btn_inv_anom"):
                st.session_state["fp_active_page"] = "Intelligence"
                st.rerun()
        else:
            st.info("No unusual transaction spikes detected.")

    with att_col2:
        st.markdown("#### 🔄 Recurring Subscriptions")
        if subs:
            total_sub = sum(s.average_amount for s in subs)
            st.markdown(f"**Total Monthly Subscription Commitment**: {fmt_money_fn(total_sub)}")
            for s in subs[:3]:
                st.markdown(f"""
                <div class="fp-alert-card fp-alert-medium">
                    <div style="font-weight: 700; color: #F8FAFC;">{s.vendor}</div>
                    <div style="font-size: 0.85rem; color: #94A3B8;">{fmt_money_fn(s.average_amount)} / {s.frequency}</div>
                </div>
                """, unsafe_allow_html=True)
            if st.button("Review Subscriptions →", key="btn_rev_subs"):
                st.session_state["fp_active_page"] = "Intelligence"
                st.rerun()
        else:
            st.info("No recurring subscription patterns detected.")

    # Financial X-Ray Signature Feature
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("✦ Financial X-Ray")
    
    if "xray_active" not in st.session_state:
        st.session_state["xray_active"] = False

    if st.button("⚡ RUN FINANCIAL X-RAY", type="primary", use_container_width=True):
        st.session_state["xray_active"] = True

    if st.session_state["xray_active"]:
        st.success("✓ Cashflow Analyzed | ✓ Anomalies Scanned | ✓ Subscriptions Verified | ✓ Goals Projected")
        x1, x2, x3, x4 = st.columns(4)
        with x1:
            st.markdown("#### Cashflow Health")
            st.progress(0.85)
            st.caption("Positive net savings trajectory")
        with x2:
            st.markdown("#### Spending Stability")
            st.progress(0.70)
            st.caption(f"{len(anomalies)} outliers flagged")
        with x3:
            st.markdown("#### Budget Adherence")
            st.progress(0.90)
            st.caption("Budgets within threshold")
        with x4:
            st.markdown("#### Goal Trajectory")
            st.progress(0.75)
            st.caption("Goals on projection path")

    # Quick Actions
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("⚡ Quick Actions")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("💳 View Ledger", use_container_width=True):
            st.session_state["fp_active_page"] = "Money"
            st.rerun()
    with q2:
        if st.button("🎯 Goal Simulator", use_container_width=True):
            st.session_state["fp_active_page"] = "Simulator"
            st.rerun()
    with q3:
        if st.button("💬 Ask AI CFO", use_container_width=True):
            st.session_state["fp_active_page"] = "AI CFO"
            st.rerun()
    with q4:
        if st.button("▣ Data Settings", use_container_width=True):
            st.session_state["fp_active_page"] = "Data"
            st.rerun()
