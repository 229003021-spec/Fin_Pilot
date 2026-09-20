import streamlit as st
from ui.components import render_topbar, render_hero_header
from finpilot.agent.query_router import NLQueryRouter
from finpilot.agent.privacy import PrivacyMasker

def render_ai_cfo_page(db, fmt_money_fn):
    """Renders the AI CFO Conversational Workspace."""
    is_demo = st.session_state.get("using_demo", True)
    render_topbar(is_demo=is_demo)
    render_hero_header("✦ AI CFO & QUERY ASSISTANT", "Ask natural language questions about your transactions, subscriptions, budgets, or savings goals.")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hello! I am your **FinPilot AI CFO**. Ask me anything about your spending patterns, recurring subscriptions, budget limits, or safe-to-spend cashflow!"}
        ]

    # Quick prompt shortcut buttons
    st.markdown("#### ⚡ Quick Prompts")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("💰 Top Spending", use_container_width=True):
            st.session_state["user_prompt_input"] = "Where did I spend the most this month?"
    with q2:
        if st.button("🔄 Subscriptions", use_container_width=True):
            st.session_state["user_prompt_input"] = "Which subscriptions am I paying for?"
    with q3:
        if st.button("📈 Expense Spikes", use_container_width=True):
            st.session_state["user_prompt_input"] = "What expenses increased compared to last month?"
    with q4:
        if st.button("🛡️ Safe-to-Spend", use_container_width=True):
            st.session_state["user_prompt_input"] = "What is my safe to spend balance?"

    st.markdown("<br>", unsafe_allow_html=True)

    # Render previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(PrivacyMasker.mask_text(msg["content"]))
            if "table" in msg and msg["table"] is not None and not msg["table"].empty:
                display_table = msg["table"].copy()
                if "Vendor" in display_table.columns:
                    display_table["Vendor"] = display_table["Vendor"].apply(PrivacyMasker.mask_text)
                if "normalized_vendor" in display_table.columns:
                    display_table["normalized_vendor"] = display_table["normalized_vendor"].apply(PrivacyMasker.mask_text)
                st.dataframe(display_table, use_container_width=True)
            if "sql" in msg and msg["sql"]:
                with st.expander("🔍 View Executed SQL Query / Deterministic Code"):
                    st.code(msg["sql"], language="sql")

    # Chat input
    prompt = st.chat_input("Ask FinPilot AI CFO a question...")
    if "user_prompt_input" in st.session_state and st.session_state.user_prompt_input:
        prompt = st.session_state.user_prompt_input
        st.session_state.user_prompt_input = None

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Execute query via router
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
