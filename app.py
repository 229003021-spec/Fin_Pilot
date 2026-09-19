import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from finpilot.db import FinPilotDB
from finpilot.demo_data import seed_demo_database, export_sample_files
from finpilot.ingestion.csv_parser import CSVStatementParser
from finpilot.ingestion.json_parser import JSONStatementParser
from finpilot.ingestion.pdf_parser import PDFStatementParser
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector
from finpilot.analytics.committed_spend import CommittedSpendCalculator
from finpilot.analytics.goals_budget import BudgetAndGoalManager
from finpilot.agent.query_router import NLQueryRouter
from finpilot.agent.brief_generator import MonthlyBriefGenerator
from finpilot.agent.privacy import PrivacyMasker


# Page Configuration
st.set_page_config(
    page_title="FinPilot - Personal Finance Decision Support Agent",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State Database Connection
if "db" not in st.session_state:
    st.session_state.db = FinPilotDB(":memory:")
    # Seed default sample data so application works out-of-the-box
    seed_demo_database(st.session_state.db)
    export_sample_files(".")

db = st.session_state.db

# Custom CSS styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left: 4px solid #1E88E5;
    }
    .disclaimer-box {
        background-color: #fff3cd;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #ffe8a1;
        font-size: 0.85rem;
        color: #856404;
        margin-top: 20px;
    }
    .stAppViewContainer {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Controls
st.sidebar.title("✈️ FinPilot Agent")
st.sidebar.caption("Personal Finance Decision Support System")

st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Ingestion")

uploaded_file = st.sidebar.file_uploader(
    "Upload Bank/Credit Statement",
    type=["csv", "json", "pdf"],
    help="Supports CSV statements, JSON exports, and PDF bank/utility statements."
)

if uploaded_file is not None:
    filename = uploaded_file.name
    try:
        if filename.endswith(".csv"):
            parser = CSVStatementParser()
            txs = parser.parse(uploaded_file, filename=filename)
        elif filename.endswith(".json"):
            parser = JSONStatementParser()
            txs = parser.parse(uploaded_file, filename=filename)
        elif filename.endswith(".pdf"):
            parser = PDFStatementParser()
            txs = parser.parse(uploaded_file, filename=filename)
        else:
            txs = []

        if txs:
            db.insert_transactions(txs)
            st.sidebar.success(f"Successfully ingested {len(txs)} transactions from {filename}!")
        else:
            st.sidebar.warning(f"No valid transaction rows found in {filename}.")
    except Exception as e:
        st.sidebar.error(f"Error parsing file {filename}: {str(e)}")

st.sidebar.markdown("---")
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    if st.button("🔄 Reload Demo", help="Reset database with standard demo financial data"):
        seed_demo_database(db)
        st.rerun()
with col_s2:
    if st.button("🗑️ Clear All", help="Clear all stored transactions"):
        db.clear_all()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("📌 **Guardrail Enforced**: All financial arithmetic is calculated deterministically via DuckDB SQL & Python execution prior to agent output.")

# Navigation Tabs
tab_overview, tab_txs, tab_anom, tab_goals, tab_chat = st.tabs([
    "📊 Executive Overview",
    "💳 Transactions & Ingestion",
    "⚠️ Subscriptions & Anomalies",
    "🎯 Budgets & Goal Simulator",
    "💬 FinPilot Q&A Assistant"
])

# -----------------------------------------------------------------------------
# TAB 1: EXECUTIVE OVERVIEW
# -----------------------------------------------------------------------------
with tab_overview:
    st.header("📈 Executive Financial Overview & Brief")

    df = db.get_transactions_df()
    if df.empty:
        st.info("No transaction data available. Upload a statement or click 'Reload Demo' in the sidebar.")
    else:
        brief_gen = MonthlyBriefGenerator(db)
        brief = brief_gen.generate_brief()

        # Key KPI Metric Cards
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Income", f"${brief['total_income']:,.2f}")
        with col2:
            st.metric("Total Expenses", f"${brief['total_expenses']:,.2f}")
        with col3:
            net = brief['net_cash_flow']
            st.metric("Net Cash Flow", f"${net:,.2f}", delta=f"{brief['savings_rate_pct']}% Savings Rate")
        with col4:
            st.metric("Committed Ratio", f"{brief['committed_spend_ratio_pct']}%", help="Fixed obligations due before next income cycle")
        with col5:
            st.metric("Safe-to-Spend", f"${brief['safe_to_spend_balance']:,.2f}", help="Available balance after fixed obligations")

        st.markdown("---")

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("🍰 Spending by Category")
            expenses_df = df[df['amount'] < 0].copy()
            if not expenses_df.empty:
                expenses_df['abs_amount'] = expenses_df['amount'].abs()
                cat_summary = expenses_df.groupby('category')['abs_amount'].sum().reset_index()
                fig_pie = px.pie(
                    cat_summary,
                    values='abs_amount',
                    names='category',
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_right:
            st.subheader("📅 Monthly Income vs Expenses")
            df['dt'] = pd.to_datetime(df['date'])
            df['month_yr'] = df['dt'].dt.strftime('%Y-%m')
            
            inc_df = df[df['amount'] > 0].groupby('month_yr')['amount'].sum().reset_index()
            exp_df = df[df['amount'] < 0].groupby('month_yr')['amount'].apply(lambda x: abs(x.sum())).reset_index()

            comp_df = pd.merge(inc_df, exp_df, on='month_yr', how='outer', suffixes=('_income', '_expense')).fillna(0)
            comp_df = comp_df.rename(columns={'amount_income': 'Income', 'amount_expense': 'Expenses'})

            fig_bar = px.bar(
                comp_df,
                x='month_yr',
                y=['Income', 'Expenses'],
                barmode='group',
                labels={'value': 'Amount ($)', 'month_yr': 'Month'},
                color_discrete_map={'Income': '#2ECC71', 'Expenses': '#E74C3C'}
            )
            fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_bar, use_container_width=True)

        # Executive Summary & Actionable Next Steps
        st.subheader("📋 Monthly Executive Brief & Next Steps")
        st.markdown(f"**Period**: {brief.get('period', 'N/A')}")
        
        for step in brief.get('next_steps', []):
            st.warning(f"💡 {step}") if "Warning" in step or "Exceeded" in step else st.info(f"💡 {step}")

# -----------------------------------------------------------------------------
# TAB 2: TRANSACTIONS & INGESTION
# -----------------------------------------------------------------------------
with tab_txs:
    st.header("💳 Transaction Ledger & Ingestion Engine")

    df = db.get_transactions_df()
    if df.empty:
        st.info("No transaction records found.")
    else:
        col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
        with col_f1:
            cats = ["All"] + sorted(df['category'].unique().tolist())
            selected_cat = st.selectbox("Filter Category", cats)
        with col_f2:
            sort_by = st.selectbox("Sort By", ["Date (Latest)", "Amount (Highest Expense)", "Vendor"])
        with col_f3:
            search_query = st.text_input("Search Vendor / Description", "")

        filtered_df = df.copy()
        if selected_cat != "All":
            filtered_df = filtered_df[filtered_df['category'] == selected_cat]
        if search_query:
            filtered_df = filtered_df[
                filtered_df['raw_vendor'].str.contains(search_query, case=False) |
                filtered_df['normalized_vendor'].str.contains(search_query, case=False)
            ]

        if sort_by == "Date (Latest)":
            filtered_df = filtered_df.sort_values(by="date", ascending=False)
        elif sort_by == "Amount (Highest Expense)":
            filtered_df = filtered_df.sort_values(by="amount", ascending=True)
        elif sort_by == "Vendor":
            filtered_df = filtered_df.sort_values(by="normalized_vendor", ascending=True)

        st.dataframe(
            filtered_df[['date', 'normalized_vendor', 'raw_vendor', 'category', 'amount', 'is_recurring', 'source_file']],
            column_config={
                "amount": st.column_config.NumberColumn("Amount ($)", format="$%.2f"),
                "is_recurring": st.column_config.CheckboxColumn("Recurring?")
            },
            use_container_width=True,
            height=450
        )

# -----------------------------------------------------------------------------
# TAB 3: SUBSCRIPTIONS & ANOMALIES
# -----------------------------------------------------------------------------
with tab_anom:
    st.header("⚠️ Recurring Subscriptions & Spending Anomalies")

    df = db.get_transactions_df()
    if df.empty:
        st.info("No transaction records found.")
    else:
        col_sub, col_anom = st.columns([1, 1])

        with col_sub:
            st.subheader("🔄 Detected Subscriptions & Recurring Bills")
            subs = SubscriptionTracker.detect_subscriptions(df)
            if subs:
                sub_df = pd.DataFrame([s.model_dump() for s in subs])
                total_mo = sum(s.average_amount for s in subs if s.frequency == 'monthly')
                st.metric("Total Monthly Subscription Cost", f"${total_mo:,.2f}")
                st.dataframe(
                    sub_df[['vendor', 'category', 'average_amount', 'frequency', 'price_variance_pct', 'last_payment_date']],
                    column_config={
                        "average_amount": st.column_config.NumberColumn("Avg Cost ($)", format="$%.2f"),
                        "price_variance_pct": st.column_config.NumberColumn("Variance (%)", format="%.1f%%")
                    },
                    use_container_width=True
                )
            else:
                st.write("No recurring 30-day or annual subscription patterns detected.")

        with col_anom:
            st.subheader("🚩 Flagged Outliers & Spending Spikes")
            anomalies = AnomalyDetector.detect_anomalies(df)
            if anomalies:
                for a in anomalies:
                    severity_color = "red" if a.severity == "HIGH" else "orange"
                    st.error(f"**[{a.severity}] {a.vendor} ({a.category})**\n\n{a.reason}")
            else:
                st.success("No standard deviation outliers (>2.5x) or MoM spending spikes (>20%) detected.")

# -----------------------------------------------------------------------------
# TAB 4: BUDGET VARIANCE & GOAL SIMULATOR
# -----------------------------------------------------------------------------
with tab_goals:
    st.header("🎯 Budget Tracking & Goal Impact Simulator")

    df = db.get_transactions_df()
    budgets = db.get_budgets()
    goals = db.get_goals()

    col_b, col_g = st.columns([1, 1])

    with col_b:
        st.subheader("📊 Monthly Budget Variance")
        if budgets:
            variances = BudgetAndGoalManager.calculate_budget_variance(df, budgets)
            for v in variances:
                status_icon = "🟢" if v['status'] == "NORMAL" else ("🟡" if v['status'] == "WARNING" else "🔴")
                st.markdown(f"**{status_icon} {v['category']}**: Spent **${v['spent']:,.2f}** / Limit **${v['allocated_limit']:,.2f}** ({v['pct_used']}% used)")
                pct_val = min(1.0, v['spent'] / v['allocated_limit']) if v['allocated_limit'] > 0 else 0.0
                st.progress(pct_val)
        else:
            st.write("No budgets set.")

    with col_g:
        st.subheader("🚀 Interactive Savings Goal Simulator")
        if goals:
            inc = df[df['amount'] > 0]['amount'].sum() if not df.empty else 4500.0
            exp = abs(df[df['amount'] < 0]['amount'].sum()) if not df.empty else 3200.0
            months_cnt = max(1, pd.to_datetime(df['date']).dt.to_period('M').nunique()) if not df.empty else 1
            net_cf = (inc - exp) / months_cnt

            st.caption(f"Current Monthly Net Cash Flow: **${net_cf:,.2f}** (Income ${inc/months_cnt:,.2f} - Expenses ${exp/months_cnt:,.2f})")

            # What-If Slider
            extra_savings = st.slider(
                "Simulate Discretionary Expense Reduction ($/month)",
                min_value=0,
                max_value=1000,
                value=200,
                step=50,
                help="Test how cutting variable spending accelerates your target goals!"
            )

            for g in goals:
                st.markdown(f"### 🏆 {g.goal_name}")
                sim = BudgetAndGoalManager.simulate_goal_timeline(g, net_cf, monthly_expense_reduction=extra_savings)
                
                st.markdown(f"- Target Amount: **${g.target_amount:,.2f}** | Saved: **${g.current_amount:,.2f}**")
                st.markdown(f"- Remaining: **${sim['remaining_amount']:,.2f}**")
                st.markdown(f"- Projected Completion: **{sim['months_to_target']} months** ({sim['projected_completion_date']})")
                st.info(sim['notes'])
                st.markdown("---")
        else:
            st.write("No goals set.")

# -----------------------------------------------------------------------------
# TAB 5: CONVERSATIONAL Q&A ASSISTANT
# -----------------------------------------------------------------------------
with tab_chat:
    st.header("💬 FinPilot Decision Support Assistant")
    st.caption("Ask natural language questions about your transactions, subscriptions, budgets, or financial goals.")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am **FinPilot**, your personal finance decision support agent. Ask me anything about your spending, subscriptions, budget variances, or savings goals!"}
        ]

    # Quick prompt shortcuts
    col_q1, col_q2, col_q3, col_q4 = st.columns(4)
    with col_q1:
        if st.button("💰 Top Spending"):
            st.session_state.user_prompt_input = "Where did I spend the most this month?"
    with col_q2:
        if st.button("🔄 Subscriptions"):
            st.session_state.user_prompt_input = "Which subscriptions am I paying for?"
    with col_q3:
        if st.button("📈 Expense Spikes"):
            st.session_state.user_prompt_input = "What expenses increased compared to last month?"
    with col_q4:
        if st.button("🛡️ Safe-to-Spend"):
            st.session_state.user_prompt_input = "What is my safe to spend balance?"

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "table" in msg and msg["table"] is not None:
                st.dataframe(msg["table"], use_container_width=True)
            if "sql" in msg and msg["sql"]:
                with st.expander("🔍 View Executed SQL Query / Deterministic Code"):
                    st.code(msg["sql"], language="sql")

    # Handle Input
    prompt = st.chat_input("Ask FinPilot a question...")
    if "user_prompt_input" in st.session_state and st.session_state.user_prompt_input:
        prompt = st.session_state.user_prompt_input
        st.session_state.user_prompt_input = None

    if prompt:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Process with Router
        router = NLQueryRouter(db)
        res = router.process_query(prompt)

        with st.chat_message("assistant"):
            st.markdown(res['answer'])
            if res['data_table'] is not None and not res['data_table'].empty:
                st.dataframe(res['data_table'], use_container_width=True)
            if res['sql_executed']:
                with st.expander("🔍 View Executed SQL Query / Deterministic Code"):
                    st.code(res['sql_executed'], language="sql")

        st.session_state.messages.append({
            "role": "assistant",
            "content": res['answer'],
            "table": res['data_table'],
            "sql": res['sql_executed']
        })

# Global Footer Disclaimer
st.markdown("""
<div class="disclaimer-box">
    <strong>⚖️ FinPilot Decision-Support Boundary:</strong> FinPilot provides data-driven decision support and financial pattern analysis based strictly on ingested data. FinPilot explicitly does not provide certified financial, investment, accounting, or legal tax advice.
</div>
""", unsafe_allow_html=True)
