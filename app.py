import streamlit as st
import pandas as pd
import plotly.express as px
from finpilot.db import FinPilotDB
from finpilot.demo_data import seed_demo_database, export_sample_files
from finpilot.models import Budget, Goal
from finpilot.ingestion.csv_parser import CSVStatementParser
from finpilot.ingestion.json_parser import JSONStatementParser
from finpilot.ingestion.pdf_parser import PDFStatementParser
from finpilot.ingestion.processor import BackgroundDocumentProcessor
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

# Helper function for configurable currency formatting
def fmt_money(val: float, currency: str = None) -> str:
    if currency is None:
        currency = st.session_state.get("currency", "$") if hasattr(st, "session_state") else "$"
    v = float(val)
    if v < 0:
        return f"-{currency}{abs(v):,.2f}"
    return f"{currency}{v:,.2f}"


# Initialize Session State
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

# Custom CSS styling
st.markdown("""
<style>
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
st.sidebar.subheader("⚙️ Settings")

# Currency Selector
currency_choice = st.sidebar.selectbox(
    "Currency Symbol",
    options=["$", "₹", "€", "£"],
    index=["$", "₹", "€", "£"].index(st.session_state.get("currency", "$")),
    help="Select your preferred currency symbol."
)
st.session_state["currency"] = currency_choice
currency = st.session_state["currency"]

st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Ingestion")

# Mode Badge
if st.session_state.get("using_demo", True):
    st.sidebar.info("ℹ️ **Data Mode**: Using demo data")
else:
    st.sidebar.success("✅ **Data Mode**: Using your uploaded data")

uploaded_file = st.sidebar.file_uploader(
    "Upload Bank/Credit Statement",
    type=["csv", "json", "pdf"],
    key=f"file_uploader_{st.session_state['uploader_key']}",
    help="Supports CSV statements, JSON exports, and PDF bank/utility statements."
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
                st.sidebar.success(f"Successfully processed {stats.total_transactions} records!")
            else:
                msg = stats.message if stats and stats.message else f"No valid transaction rows found in {uploaded_file.name}."
                st.sidebar.error(msg)
        except Exception as e:
            st.sidebar.error(f"Failed to process document: {str(e)}")

# Render Sidebar Stats Expander if available
if st.session_state.get("last_stats"):
    stats = st.session_state["last_stats"]
    with st.sidebar.expander("📊 Document Analytics & Health Stats", expanded=True):
        st.markdown(f"**Format**: `{stats.file_format}` | **Confidence**: `{stats.parsing_confidence_pct}%`")
        st.markdown(f"**Date Range**: `{stats.date_range_start}` to `{stats.date_range_end}`")
        st.markdown(f"**Gross Inflow**: +{fmt_money(stats.gross_income)}")
        st.markdown(f"**Gross Outflow**: -{fmt_money(stats.gross_expenses)}")
        st.markdown(f"**Net Impact**: {fmt_money(stats.net_cash_flow)}")
        st.markdown(f"**Top Category**: {stats.top_category} ({fmt_money(stats.top_category_amount)})")
        st.markdown(f"**Top Vendor**: {stats.top_vendor} ({fmt_money(stats.top_vendor_amount)})")
        st.markdown(f"**Detected**: 🔄 {stats.subscriptions_detected} Subs | 🚩 {stats.anomalies_detected} Outliers")

st.sidebar.markdown("---")
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    if st.button("🔄 Reload Demo", help="Reset database with standard demo financial data"):
        seed_demo_database(db)
        st.session_state["last_uploaded"] = None
        st.session_state["last_stats"] = None
        st.session_state["using_demo"] = True
        st.session_state["uploader_key"] += 1
        st.rerun()
with col_s2:
    with st.popover("🗑️ Clear All"):
        st.warning("Erases all transactions, budgets, and goals!")
        if st.button("Confirm Clear All", type="primary"):
            db.clear_all()
            st.session_state["last_uploaded"] = None
            st.session_state["last_stats"] = None
            st.session_state["using_demo"] = False
            st.session_state["uploader_key"] += 1
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.warning("🔒 **Privacy Notice**: Data lives only in this session's memory. Do not upload real statements to public demos.")

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
            st.metric("Total Income", fmt_money(brief['total_income']))
        with col2:
            st.metric("Total Expenses", fmt_money(brief['total_expenses']))
        with col3:
            net = brief['net_cash_flow']
            st.metric("Net Cash Flow", fmt_money(net), delta=f"{brief['savings_rate_pct']}% Savings Rate")
        with col4:
            st.metric("Committed Ratio", f"{brief['committed_spend_ratio_pct']}%", help="Fixed obligations due before next income cycle")
        with col5:
            st.metric("Safe-to-Spend", fmt_money(brief['safe_to_spend_balance']), help="Available balance after fixed obligations")

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
                labels={'value': f'Amount ({currency})', 'month_yr': 'Month'},
                color_discrete_map={'Income': '#2ECC71', 'Expenses': '#E74C3C'}
            )
            fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_bar, use_container_width=True)

        # Executive Summary & Actionable Next Steps
        st.subheader("📋 Monthly Executive Brief & Next Steps")
        st.markdown(f"**Period**: {brief.get('period', 'N/A')}")
        
        for step in brief.get('next_steps', []):
            if "Warning" in step or "Exceeded" in step:
                st.warning(f"💡 {step}")
            else:
                st.info(f"💡 {step}")

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
            # Mask vendors in search display for privacy
            filtered_df = filtered_df[
                filtered_df['raw_vendor'].astype(str).str.contains(search_query, case=False, regex=False, na=False) |
                filtered_df['normalized_vendor'].astype(str).str.contains(search_query, case=False, regex=False, na=False)
            ]

        if sort_by == "Date (Latest)":
            filtered_df = filtered_df.sort_values(by="date", ascending=False)
        elif sort_by == "Amount (Highest Expense)":
            filtered_df = filtered_df.sort_values(by="amount", ascending=True)
        elif sort_by == "Vendor":
            filtered_df = filtered_df.sort_values(by="normalized_vendor", ascending=True)

        # Apply PrivacyMasker to Ledger table output
        display_df = filtered_df.copy()
        display_df['raw_vendor'] = display_df['raw_vendor'].apply(PrivacyMasker.mask_text)
        display_df['normalized_vendor'] = display_df['normalized_vendor'].apply(PrivacyMasker.mask_text)

        st.dataframe(
            display_df[['date', 'normalized_vendor', 'raw_vendor', 'category', 'amount', 'is_recurring', 'source_file']],
            column_config={
                "amount": st.column_config.NumberColumn(f"Amount ({currency})", format=f"{currency}%.2f"),
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
                sub_df['vendor'] = sub_df['vendor'].apply(PrivacyMasker.mask_text)
                total_mo = sum(s.average_amount for s in subs if s.frequency == 'monthly')
                st.metric("Total Monthly Subscription Cost", fmt_money(total_mo))
                st.dataframe(
                    sub_df[['vendor', 'category', 'average_amount', 'frequency', 'price_variance_pct', 'last_payment_date']],
                    column_config={
                        "average_amount": st.column_config.NumberColumn(f"Avg Cost ({currency})", format=f"{currency}%.2f"),
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
                    masked_reason = PrivacyMasker.mask_text(a.reason)
                    masked_vendor = PrivacyMasker.mask_text(a.vendor)
                    if a.severity == "HIGH":
                        st.error(f"**[HIGH] {masked_vendor} ({a.category})**\n\n{masked_reason}")
                    else:
                        st.warning(f"**[{a.severity}] {masked_vendor} ({a.category})**\n\n{masked_reason}")
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
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{status_icon} {v['category']}**: Spent **{fmt_money(v['spent'])}** / Limit **{fmt_money(v['allocated_limit'])}** ({v['pct_used']}% used)")
                    pct_val = min(1.0, v['spent'] / v['allocated_limit']) if v['allocated_limit'] > 0 else 0.0
                    st.progress(pct_val)
                with c2:
                    if st.button("🗑️", key=f"del_budget_{v['category']}", help=f"Delete budget for {v['category']}"):
                        db.delete_budget(v['category'])
                        st.rerun()
        else:
            st.write("No budgets configured.")

        st.markdown("---")
        st.markdown("#### ➕ Add / Update Budget")
        with st.form("add_budget_form", clear_on_submit=True):
            all_categories = ["Housing", "Utilities", "Groceries", "Dining Out", "Transportation", "Subscriptions", "Shopping", "General"]
            existing_cats = df['category'].unique().tolist() if not df.empty else []
            cat_options = sorted(list(set(all_categories + existing_cats)))

            b_cat = st.selectbox("Category", cat_options)
            b_limit = st.number_input(f"Monthly Limit ({currency})", min_value=0.0, step=50.0, value=250.0)
            b_submit = st.form_submit_button("Save Budget")

            if b_submit:
                try:
                    db.upsert_budget(Budget(category=b_cat, allocated_limit=b_limit))
                    st.success(f"Saved budget for {b_cat}: {fmt_money(b_limit)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save budget: {str(e)}")

    with col_g:
        st.subheader("🚀 Interactive Savings Goal Simulator")
        if df.empty:
            st.info("Upload a statement to simulate goals.")
        else:
            dt = pd.to_datetime(df['date'])
            days_span = max(1, (dt.max() - dt.min()).days + 1)
            months_cnt = max(1.0, days_span / 30.4375)

            inc = float(df[df['amount'] > 0]['amount'].sum()) if not df[df['amount'] > 0].empty else 0.0
            exp = float(abs(df[df['amount'] < 0]['amount'].sum())) if not df[df['amount'] < 0].empty else 0.0

            monthly_inc = inc / months_cnt
            monthly_exp = exp / months_cnt
            net_cf = monthly_inc - monthly_exp

            st.caption(f"Estimated Monthly Net Cash Flow: **{fmt_money(net_cf)}** (Avg Income {fmt_money(monthly_inc)} - Avg Expenses {fmt_money(monthly_exp)} over {days_span} days)")

            # What-If Slider
            extra_savings = st.slider(
                f"Simulate Discretionary Expense Reduction ({currency}/month)",
                min_value=0,
                max_value=1000,
                value=200,
                step=50,
                help="Test how cutting variable spending accelerates your target goals!"
            )

            if goals:
                for g in goals:
                    c_g1, c_g2 = st.columns([4, 1])
                    with c_g1:
                        st.markdown(f"### 🏆 {g.goal_name}")
                    with c_g2:
                        if st.button("🗑️", key=f"del_goal_{g.goal_name}", help=f"Delete goal {g.goal_name}"):
                            db.delete_goal(g.goal_name)
                            st.rerun()

                    sim = BudgetAndGoalManager.simulate_goal_timeline(g, net_cf, monthly_expense_reduction=extra_savings)
                    st.markdown(f"- Target Amount: **{fmt_money(g.target_amount)}** | Saved: **{fmt_money(g.current_amount)}**")
                    st.markdown(f"- Remaining: **{fmt_money(sim['remaining_amount'])}**")
                    if sim['is_feasible']:
                        st.markdown(f"- Projected Completion: **{sim['months_to_target']} months** ({sim['projected_completion_date']})")
                        st.info(sim['notes'])
                    else:
                        st.warning(f"Goal cannot be reached at the current cash flow. ({sim['notes']})")
                    st.markdown("---")
            else:
                st.write("No savings goals configured.")

        st.markdown("---")
        st.markdown("#### ➕ Add New Savings Goal")
        with st.form("add_goal_form", clear_on_submit=True):
            g_name = st.text_input("Goal Name (e.g. Emergency Fund)")
            g_target = st.number_input(f"Target Amount ({currency})", min_value=0.0, step=100.0, value=5000.0)
            g_current = st.number_input(f"Current Savings ({currency})", min_value=0.0, step=100.0, value=1000.0)
            g_date = st.date_input("Target Completion Date (Optional)")
            g_submit = st.form_submit_button("Save Goal")

            if g_submit:
                try:
                    if not g_name.strip():
                        st.error("Goal name cannot be empty.")
                    elif g_target <= 0:
                        st.error("Target amount must be greater than 0.")
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
                except Exception as e:
                    st.error(f"Failed to save goal: {str(e)}")

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

    # Display chat messages with PrivacyMasker applied
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(PrivacyMasker.mask_text(msg["content"]))
            if "table" in msg and msg["table"] is not None:
                display_table = msg["table"].copy()
                if "Vendor" in display_table.columns:
                    display_table["Vendor"] = display_table["Vendor"].apply(PrivacyMasker.mask_text)
                if "normalized_vendor" in display_table.columns:
                    display_table["normalized_vendor"] = display_table["normalized_vendor"].apply(PrivacyMasker.mask_text)
                st.dataframe(display_table, use_container_width=True)
            if "sql" in msg and msg["sql"]:
                with st.expander("🔍 View Executed SQL Query / Deterministic Code"):
                    st.code(msg["sql"], language="sql")

    # Handle Input
    prompt = st.chat_input("Ask FinPilot a question...")
    if "user_prompt_input" in st.session_state and st.session_state.user_prompt_input:
        prompt = st.session_state.user_prompt_input
        st.session_state.user_prompt_input = None

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Process with Router
        router = NLQueryRouter(db)
        res = router.process_query(prompt)
        masked_answer = PrivacyMasker.mask_text(res['answer'])

        with st.chat_message("assistant"):
            st.markdown(masked_answer)
            if res['data_table'] is not None and not res['data_table'].empty:
                display_table = res['data_table'].copy()
                if "Vendor" in display_table.columns:
                    display_table["Vendor"] = display_table["Vendor"].apply(PrivacyMasker.mask_text)
                if "normalized_vendor" in display_table.columns:
                    display_table["normalized_vendor"] = display_table["normalized_vendor"].apply(PrivacyMasker.mask_text)
                st.dataframe(display_table, use_container_width=True)
            if res['sql_executed']:
                with st.expander("🔍 View Executed SQL Query / Deterministic Code"):
                    st.code(res['sql_executed'], language="sql")

        st.session_state.messages.append({
            "role": "assistant",
            "content": masked_answer,
            "table": res['data_table'],
            "sql": res['sql_executed']
        })

# Global Footer Disclaimer
st.markdown("""
<div class="disclaimer-box">
    <strong>⚖️ FinPilot Decision-Support Boundary:</strong> FinPilot provides data-driven decision support and financial pattern analysis based strictly on ingested data. FinPilot explicitly does not provide certified financial, investment, accounting, or legal tax advice.
</div>
""", unsafe_allow_html=True)
