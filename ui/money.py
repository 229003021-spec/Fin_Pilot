import streamlit as st
import pandas as pd
import plotly.express as px
from ui.components import render_topbar, render_hero_header, render_empty_state
from finpilot.agent.privacy import PrivacyMasker

def render_money_page(db, fmt_money_fn):
    """Renders the Money page for transactions, category breakdown, and financial ledger."""
    is_demo = st.session_state.get("using_demo", True)
    render_topbar(is_demo=is_demo)
    render_hero_header("◇ MONEY & TRANSACTIONS", "Inspect your ledger, spending breakdown, and merchant details.")

    df = db.get_transactions_df()
    if df.empty:
        render_empty_state("No Transactions Found", "Upload a financial statement to view your transaction ledger.", "💳")
        return

    # View Mode Toggle & Filters
    col_m1, col_m2, col_m3, col_m4 = st.columns([1, 1, 2, 1])
    with col_m1:
        cats = ["All"] + sorted(df['category'].unique().tolist())
        selected_cat = st.selectbox("Category", cats)
    with col_m2:
        sort_by = st.selectbox("Sort By", ["Date (Latest)", "Amount (Highest Expense)", "Vendor"])
    with col_m3:
        search_query = st.text_input("Search Vendor / Description", "")
    with col_m4:
        view_mode = st.radio("View Mode", ["Table", "Cards"], horizontal=True)

    filtered_df = df.copy()
    if selected_cat != "All":
        filtered_df = filtered_df[filtered_df['category'] == selected_cat]
    if search_query:
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

    # Breakdown Section
    st.markdown("<br>", unsafe_allow_html=True)
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("🍰 Category Breakdown")
        expenses_df = filtered_df[filtered_df['amount'] < 0].copy()
        if not expenses_df.empty:
            expenses_df['abs_amount'] = expenses_df['amount'].abs()
            cat_summary = expenses_df.groupby('category')['abs_amount'].sum().reset_index()
            fig_pie = px.pie(
                cat_summary,
                values='abs_amount',
                names='category',
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_pie.update_layout(
                paper_bgcolor='#131B2E',
                plot_bgcolor='#131B2E',
                font=dict(color='#E2E8F0'),
                margin=dict(t=20, b=20, l=20, r=20)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No expense categories found in current filter.")

    with col_right:
        st.subheader("📊 Category Totals")
        if not expenses_df.empty:
            cat_sums = expenses_df.groupby('category')['abs_amount'].sum().sort_values(ascending=False)
            for cat, amt in cat_sums.items():
                st.markdown(f"**{cat}**: `{fmt_money_fn(amt)}`")
                st.progress(min(1.0, amt / cat_sums.sum()))

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader(f"💳 Transaction Ledger ({len(filtered_df)} records)")

    if view_mode == "Table":
        display_df = filtered_df.copy()
        display_df['raw_vendor'] = display_df['raw_vendor'].apply(PrivacyMasker.mask_text)
        display_df['normalized_vendor'] = display_df['normalized_vendor'].apply(PrivacyMasker.mask_text)

        st.dataframe(
            display_df[['date', 'normalized_vendor', 'raw_vendor', 'category', 'amount', 'is_recurring', 'source_file']],
            column_config={
                "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                "is_recurring": st.column_config.CheckboxColumn("Recurring?")
            },
            use_container_width=True,
            height=450
        )
    else:
        # Card Grid View
        for idx, row in filtered_df.iterrows():
            amt_str = fmt_money_fn(row['amount'])
            amt_color = "#10B981" if row['amount'] > 0 else "#EF4444"
            masked_v = PrivacyMasker.mask_text(row['normalized_vendor'])
            
            with st.expander(f"{masked_v} | {row['category']} | {amt_str}"):
                st.markdown(f"**Raw Description**: `{PrivacyMasker.mask_text(row['raw_vendor'])}`")
                st.markdown(f"**Date**: `{row['date']}` | **Category**: `{row['category']}` | **Source**: `{row['source_file']}`")
                st.markdown(f"**Amount**: <span style='color: {amt_color}; font-weight: 700;'>{amt_str}</span>", unsafe_allow_html=True)
                st.info(f"💡 **FinPilot Context**: Recorded transaction in {row['category']}.")
