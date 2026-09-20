import streamlit as st
import pandas as pd
from ui.components import render_topbar, render_hero_header, render_empty_state
from finpilot.models import Budget, Goal
from finpilot.analytics.goals_budget import BudgetAndGoalManager

def render_goals_page(db, fmt_money_fn):
    """Renders the Goals and Budgets page."""
    is_demo = st.session_state.get("using_demo", True)
    render_topbar(is_demo=is_demo)
    render_hero_header("🎯 BUDGETS & SAVINGS GOALS", "Set monthly budget limits and track progress toward financial milestones.")

    df = db.get_transactions_df()
    budgets = db.get_budgets()
    goals = db.get_goals()

    col_b, col_g = st.columns([1, 1])

    with col_b:
        st.subheader("📊 Category Budget Limits")
        if budgets:
            variances = BudgetAndGoalManager.calculate_budget_variance(df, budgets)
            for v in variances:
                status_icon = "🟢" if v['status'] == "NORMAL" else ("🟡" if v['status'] == "WARNING" else "🔴")
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{status_icon} {v['category']}**: Spent **{fmt_money_fn(v['spent'])}** / Limit **{fmt_money_fn(v['allocated_limit'])}** ({v['pct_used']}% used)")
                    pct_val = min(1.0, v['spent'] / v['allocated_limit']) if v['allocated_limit'] > 0 else 0.0
                    st.progress(pct_val)
                with c2:
                    if st.button("🗑️", key=f"del_b_{v['category']}", help="Delete budget"):
                        db.delete_budget(v['category'])
                        st.rerun()
        else:
            st.info("No budgets configured yet.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### ➕ Add / Update Budget Limit")
        with st.form("form_add_budget", clear_on_submit=True):
            all_categories = ["Housing", "Utilities", "Groceries", "Dining Out", "Transportation", "Subscriptions", "Shopping", "General"]
            existing_cats = df['category'].unique().tolist() if not df.empty else []
            cat_options = sorted(list(set(all_categories + existing_cats)))

            b_cat = st.selectbox("Category", cat_options)
            b_limit = st.number_input("Monthly Budget Limit", min_value=0.0, step=50.0, value=250.0)
            b_sub = st.form_submit_button("Save Budget Limit")

            if b_sub:
                try:
                    db.upsert_budget(Budget(category=b_cat, allocated_limit=b_limit))
                    st.success(f"Saved budget limit for {b_cat}: {fmt_money_fn(b_limit)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save budget: {str(e)}")

    with col_g:
        st.subheader("🏆 Savings Goals Journey")
        if goals:
            for g in goals:
                c_g1, c_g2 = st.columns([4, 1])
                pct = min(100.0, round((g.current_amount / g.target_amount) * 100.0, 1)) if g.target_amount > 0 else 0.0
                
                with c_g1:
                    st.markdown(f"### 🏆 {g.goal_name}")
                    st.markdown(f"Target: **{fmt_money_fn(g.target_amount)}** | Saved: **{fmt_money_fn(g.current_amount)}** ({pct}% complete)")
                    st.progress(min(1.0, pct / 100.0))
                with c_g2:
                    if st.button("🗑️", key=f"del_g_{g.goal_name}", help="Delete goal"):
                        db.delete_goal(g.goal_name)
                        st.rerun()
                st.markdown("---")
        else:
            st.info("No savings goals created yet.")

        st.markdown("#### ➕ Add New Savings Goal")
        with st.form("form_add_goal", clear_on_submit=True):
            g_name = st.text_input("Goal Name (e.g. Emergency Fund)")
            g_target = st.number_input("Target Amount", min_value=0.0, step=100.0, value=5000.0)
            g_current = st.number_input("Current Savings", min_value=0.0, step=100.0, value=1000.0)
            g_date = st.date_input("Target Completion Date")
            g_sub = st.form_submit_button("Save Goal")

            if g_sub:
                if not g_name.strip():
                    st.error("Goal name cannot be empty.")
                elif g_target <= 0:
                    st.error("Target amount must be > 0.")
                else:
                    target_date_str = g_date.strftime("%Y-%m-%d") if g_date else ""
                    db.add_goal(Goal(
                        goal_name=g_name.strip(),
                        target_amount=g_target,
                        current_amount=g_current,
                        target_date=target_date_str
                    ))
                    st.success(f"Saved goal '{g_name}'!")
                    st.rerun()
