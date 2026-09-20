import streamlit as st
import pandas as pd
from ui.components import render_topbar, render_hero_header, render_empty_state
from finpilot.analytics.goals_budget import BudgetAndGoalManager

def render_simulator_page(db, fmt_money_fn):
    """Renders the 'What If?' Financial Decision Simulator."""
    is_demo = st.session_state.get("using_demo", True)
    render_topbar(is_demo=is_demo)
    render_hero_header("◌ WHAT IF? DECISION SIMULATOR", "Test how discretionary spending adjustments impact your goal timelines and safe-to-spend balance.")

    df = db.get_transactions_df()
    goals = db.get_goals()

    if df.empty:
        render_empty_state("No Financial Data Loaded", "Upload a financial statement to simulate decisions.", "◌")
        return

    # Compute baseline monthly cashflow
    dt = pd.to_datetime(df['date'])
    days_span = max(1, (dt.max() - dt.min()).days + 1)
    months_cnt = max(1.0, days_span / 30.4375)

    inc = float(df[df['amount'] > 0]['amount'].sum()) if not df[df['amount'] > 0].empty else 0.0
    exp = float(abs(df[df['amount'] < 0]['amount'].sum())) if not df[df['amount'] < 0].empty else 0.0

    monthly_inc = inc / months_cnt
    monthly_exp = exp / months_cnt
    baseline_net_cf = monthly_inc - monthly_exp

    st.info(f"💡 **Current Baseline Net Cash Flow**: **{fmt_money_fn(baseline_net_cf)}/month** *(Avg Income {fmt_money_fn(monthly_inc)} - Avg Expenses {fmt_money_fn(monthly_exp)} over {days_span} days)*")

    # Interactive Sliders
    st.markdown("### 🎛️ Simulation Controls")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        extra_savings = st.slider(
            "Monthly Expense Reduction",
            min_value=0,
            max_value=1000,
            value=200,
            step=50,
            help="Simulate cutting discretionary spending (e.g. dining out or subscriptions)."
        )
    with col_c2:
        extra_income = st.slider(
            "Additional Monthly Income",
            min_value=0,
            max_value=2000,
            value=0,
            step=100,
            help="Simulate side income or salary increase."
        )

    simulated_net_cf = baseline_net_cf + extra_savings + extra_income

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📊 Projected Decision Impact")

    # Side-by-Side Impact Comparison Card
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown(f"""
        <div class="fp-card">
            <div style="font-weight: 700; color: #94A3B8; text-transform: uppercase; font-size: 0.8rem;">Current Baseline Plan</div>
            <div style="font-size: 1.8rem; font-weight: 800; color: #F8FAFC; margin: 8px 0;">{fmt_money_fn(baseline_net_cf)}/mo</div>
            <div style="font-size: 0.85rem; color: #64748B;">Standard monthly surplus rate</div>
        </div>
        """, unsafe_allow_html=True)

    with col_p2:
        diff_str = f"+{fmt_money_fn(simulated_net_cf - baseline_net_cf)}"
        st.markdown(f"""
        <div class="fp-card" style="border-color: #10B981; background: linear-gradient(135deg, #131B2E 0%, rgba(16, 185, 129, 0.1) 100%);">
            <div style="font-weight: 700; color: #10B981; text-transform: uppercase; font-size: 0.8rem;">Simulated Plan</div>
            <div style="font-size: 1.8rem; font-weight: 800; color: #10B981; margin: 8px 0;">{fmt_money_fn(simulated_net_cf)}/mo</div>
            <div style="font-size: 0.85rem; color: #34D399;">Cashflow boost: {diff_str}/month</div>
        </div>
        """, unsafe_allow_html=True)

    # Goal Impact Evaluation
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🎯 Goal Timeline Comparison")

    if goals:
        for g in goals:
            base_sim = BudgetAndGoalManager.simulate_goal_timeline(g, baseline_net_cf, monthly_expense_reduction=0)
            new_sim = BudgetAndGoalManager.simulate_goal_timeline(g, baseline_net_cf, monthly_expense_reduction=extra_savings + extra_income)

            st.markdown(f"#### 🏆 Goal: {g.goal_name}")
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                st.markdown(f"**Baseline Completion**: {base_sim['months_to_target']} months ({base_sim['projected_completion_date']})")
            with c_g2:
                if new_sim['is_feasible']:
                    m_saved = max(0.0, round(base_sim['months_to_target'] - new_sim['months_to_target'], 1))
                    st.success(f"**Simulated Completion**: {new_sim['months_to_target']} months ({new_sim['projected_completion_date']}) — **{m_saved} months faster!**")
                else:
                    st.warning(new_sim['notes'])
            st.markdown("---")
    else:
        st.info("No active savings goals configured. Add a goal on the Goals page to see timeline impacts.")
