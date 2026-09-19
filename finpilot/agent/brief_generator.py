import pandas as pd
from typing import Dict, Any, List
from finpilot.db import FinPilotDB
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector
from finpilot.analytics.committed_spend import CommittedSpendCalculator
from finpilot.analytics.goals_budget import BudgetAndGoalManager


class MonthlyBriefGenerator:
    """
    Produces comprehensive monthly financial executive summaries containing
    key observations, budget status tables, anomaly flags, and actionable next steps.
    """

    def __init__(self, db: FinPilotDB):
        self.db = db

    def generate_brief(self) -> Dict[str, Any]:
        df = self.db.get_transactions_df()
        budgets = self.db.get_budgets()
        goals = self.db.get_goals()

        if df.empty:
            return {
                "title": "FinPilot Monthly Financial Executive Brief",
                "status": "NO_DATA",
                "summary_text": "No transaction records found in database.",
                "disclaimer": self._disclaimer()
            }

        df['dt'] = pd.to_datetime(df['date'])
        df['month_yr'] = df['dt'].dt.strftime('%Y-%m')
        latest_month = df['month_yr'].max()

        # Monthly metrics
        month_df = df[df['month_yr'] == latest_month]
        income = month_df[month_df['amount'] > 0]['amount'].sum()
        expenses = abs(month_df[month_df['amount'] < 0]['amount'].sum())
        net_cash_flow = income - expenses
        savings_rate_pct = (net_cash_flow / income * 100.0) if income > 0 else 0.0

        # Committed spend
        committed_res = CommittedSpendCalculator.calculate_committed_spend(df, monthly_income=income)

        # Category spending breakdown
        cat_df = month_df[month_df['amount'] < 0].groupby('category')['amount'].apply(lambda x: abs(x.sum())).reset_index()
        cat_df = cat_df.sort_values(by='amount', ascending=False)
        top_categories = dict(zip(cat_df['category'], cat_df['amount']))

        # Subscriptions
        subs = SubscriptionTracker.detect_subscriptions(df)
        total_sub_cost = sum(s.average_amount for s in subs if s.frequency == 'monthly')

        # Anomalies
        anomalies = AnomalyDetector.detect_anomalies(df)

        # Budget variance
        budget_variance = BudgetAndGoalManager.calculate_budget_variance(df, budgets)

        # Next Steps / Recommendations
        next_steps = []
        if net_cash_flow > 0:
            next_steps.append(f"Allocation Opportunity: You have a positive net cash flow of ${net_cash_flow:,.2f} this month. Consider routing 50% toward active savings goals.")
        else:
            next_steps.append(f"Cash Flow Warning: Expenses (${expenses:,.2f}) exceeded income (${income:,.2f}) by ${abs(net_cash_flow):,.2f}. Review variable discretionary categories.")

        if committed_res['committed_spend_ratio_pct'] > 50.0:
            next_steps.append(f"High Committed Obligations: Fixed spend accounts for {committed_res['committed_spend_ratio_pct']}% of income. Target subscription pruning or utility efficiency.")

        for b in budget_variance:
            if b['status'] == "EXCEEDED":
                next_steps.append(f"Budget Exceeded: Category '{b['category']}' spent ${b['spent']:,.2f} vs limit ${b['allocated_limit']:,.2f} ({b['pct_used']}% used).")

        if anomalies:
            next_steps.append(f"Anomaly Review: {len(anomalies)} spending anomaly/spike flags detected. Inspect flagged transactions.")

        return {
            "title": f"FinPilot Executive Brief - {latest_month}",
            "status": "SUCCESS",
            "period": latest_month,
            "total_income": round(income, 2),
            "total_expenses": round(expenses, 2),
            "net_cash_flow": round(net_cash_flow, 2),
            "savings_rate_pct": round(savings_rate_pct, 1),
            "committed_spend_ratio_pct": committed_res['committed_spend_ratio_pct'],
            "safe_to_spend_balance": committed_res['safe_to_spend_balance'],
            "active_subscriptions_count": len(subs),
            "monthly_subscriptions_cost": round(total_sub_cost, 2),
            "top_spending_categories": top_categories,
            "budget_variance": budget_variance,
            "anomalies": [a.model_dump() for a in anomalies],
            "next_steps": next_steps,
            "disclaimer": self._disclaimer()
        }

    @staticmethod
    def _disclaimer() -> str:
        return "FinPilot Decision Support Disclaimer: Summaries and metrics are calculated deterministically. FinPilot provides decision-support tools and does not provide certified financial, investment, or legal advice."
