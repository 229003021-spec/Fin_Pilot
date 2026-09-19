import pandas as pd
from typing import Dict, Any, List, Optional
from finpilot.db import FinPilotDB
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector
from finpilot.analytics.committed_spend import CommittedSpendCalculator
from finpilot.analytics.goals_budget import BudgetAndGoalManager
from finpilot.agent.privacy import PrivacyMasker


class NLQueryRouter:
    """
    Translates natural language financial queries into deterministic DuckDB SQL / analytical computations.
    Enforces rule: All math is computed via code, zero LLM hallucinations.
    """

    def __init__(self, db: FinPilotDB):
        self.db = db

    def process_query(self, query_text: str) -> Dict[str, Any]:
        q = query_text.lower().strip()
        df = self.db.get_transactions_df()
        budgets = self.db.get_budgets()
        goals = self.db.get_goals()

        if df.empty:
            return {
                "query": query_text,
                "answer": "No financial transaction data is currently loaded in FinPilot. Please import a CSV, JSON, or PDF statement first.",
                "data_table": None,
                "sql_executed": None,
                "disclaimer": self._disclaimer()
            }

        # Query 1: Spending breakdown / Where did I spend the most?
        if any(w in q for w in ["where did i spend", "most spend", "top category", "highest category", "top spending", "expense breakdown"]):
            sql = """
                SELECT category, 
                       ROUND(SUM(ABS(amount)), 2) AS total_spent,
                       COUNT(*) AS transaction_count,
                       ROUND(AVG(ABS(amount)), 2) AS avg_transaction
                FROM transactions
                WHERE amount < 0
                GROUP BY category
                ORDER BY total_spent DESC
            """
            result_df = self.db.run_query(sql)
            if not result_df.empty:
                top_cat = result_df.iloc[0]['category']
                top_amt = result_df.iloc[0]['total_spent']
                total_all = result_df['total_spent'].sum()
                pct = (top_amt / total_all * 100.0) if total_all > 0 else 0
                
                answer = (
                    f"You spent the most in **{top_cat}** totaling **${top_amt:,.2f}** "
                    f"({pct:.1f}% of total expenses ${total_all:,.2f})."
                )
            else:
                answer = "No expense transactions recorded."

            return {
                "query": query_text,
                "answer": PrivacyMasker.mask_text(answer),
                "data_table": result_df,
                "sql_executed": sql.strip(),
                "disclaimer": self._disclaimer()
            }

        # Query 2: Subscriptions query / Which subscriptions am I paying for?
        elif any(w in q for w in ["subscription", "recurring", "memberships", "paying for"]):
            subs = SubscriptionTracker.detect_subscriptions(df)
            if subs:
                sub_rows = [
                    {
                        "Vendor": s.vendor,
                        "Category": s.category,
                        "Avg Amount": f"${s.average_amount:.2f}",
                        "Frequency": s.frequency,
                        "Variance": f"{s.price_variance_pct:.1f}%",
                        "Last Payment": s.last_payment_date
                    }
                    for s in subs
                ]
                sub_df = pd.DataFrame(sub_rows)
                total_monthly = sum(s.average_amount for s in subs if s.frequency == 'monthly')
                answer = (
                    f"FinPilot detected **{len(subs)} recurring subscription(s)** totaling "
                    f"**${total_monthly:,.2f}/month** in fixed recurring payments."
                )
            else:
                # Fallback to category = Subscriptions in SQL
                sql = "SELECT normalized_vendor, category, ROUND(ABS(amount), 2) as amount, date FROM transactions WHERE category = 'Subscriptions' OR is_recurring = TRUE ORDER BY date DESC"
                sub_df = self.db.run_query(sql)
                answer = f"Found {len(sub_df)} transaction(s) tagged under Subscriptions."

            return {
                "query": query_text,
                "answer": PrivacyMasker.mask_text(answer),
                "data_table": sub_df,
                "sql_executed": "SubscriptionTracker.detect_subscriptions (30-day cycle, <=5% price variance)",
                "disclaimer": self._disclaimer()
            }

        # Query 3: Expense changes / What expenses increased compared to last month?
        elif any(w in q for w in ["increase", "compared to last month", "mom", "spending spike", "more than last month"]):
            anomalies = AnomalyDetector.detect_anomalies(df)
            mom_spikes = [a for a in anomalies if a.anomaly_type == "category_mom_spike"]
            
            # Run exact DuckDB SQL for MoM Comparison
            sql = """
                WITH monthly AS (
                    SELECT category, 
                           SUBSTR(date, 1, 7) as month_yr,
                           SUM(ABS(amount)) as month_spend
                    FROM transactions
                    WHERE amount < 0
                    GROUP BY category, month_yr
                )
                SELECT m1.category,
                       m1.month_yr as previous_month,
                       ROUND(m1.month_spend, 2) as prev_spend,
                       m2.month_yr as current_month,
                       ROUND(m2.month_spend, 2) as curr_spend,
                       ROUND(m2.month_spend - m1.month_spend, 2) as dollar_increase,
                       ROUND(((m2.month_spend - m1.month_spend) / m1.month_spend) * 100.0, 1) as pct_increase
                FROM monthly m1
                JOIN monthly m2 ON m1.category = m2.category AND m2.month_yr > m1.month_yr
                WHERE m2.month_spend > m1.month_spend
                ORDER BY pct_increase DESC
            """
            mom_df = self.db.run_query(sql)
            if not mom_df.empty:
                top_increase = mom_df.iloc[0]
                answer = (
                    f"The highest category spending increase was **{top_increase['category']}**, which grew "
                    f"by **{top_increase['pct_increase']:.1f}%** from ${top_increase['prev_spend']:,.2f} in {top_increase['previous_month']} "
                    f"to **${top_increase['curr_spend']:,.2f}** in {top_increase['current_month']}."
                )
            else:
                answer = "No category spending increases detected between recorded months."

            return {
                "query": query_text,
                "answer": PrivacyMasker.mask_text(answer),
                "data_table": mom_df,
                "sql_executed": sql.strip(),
                "disclaimer": self._disclaimer()
            }

        # Query 4: Safe to spend / Committed spend
        elif any(w in q for w in ["safe to spend", "committed spend", "how much can i spend", "available balance"]):
            res = CommittedSpendCalculator.calculate_committed_spend(df)
            answer = (
                f"Your estimated **Safe-to-Spend Balance** is **${res['safe_to_spend_balance']:,.2f}**.\n"
                f"- Monthly Income: ${res['total_income']:,.2f}\n"
                f"- Committed Obligations (Housing/Utilities/Subs): ${res['committed_obligations']:,.2f} ({res['committed_spend_ratio_pct']}% of income)"
            )
            return {
                "query": query_text,
                "answer": PrivacyMasker.mask_text(answer),
                "data_table": pd.DataFrame([res]),
                "sql_executed": "CommittedSpendCalculator.calculate_committed_spend",
                "disclaimer": self._disclaimer()
            }

        # Query 5: Goals / Emergency Fund / Savings timeline
        elif any(w in q for w in ["goal", "target", "emergency fund", "how long", "reach"]):
            if goals:
                # Calculate monthly net cash flow
                inc = df[df['amount'] > 0]['amount'].sum()
                exp = abs(df[df['amount'] < 0]['amount'].sum())
                months = max(1, pd.to_datetime(df['date']).dt.to_period('M').nunique())
                net_cf = (inc - exp) / months

                sim_list = []
                answer_lines = []
                for g in goals:
                    sim = BudgetAndGoalManager.simulate_goal_timeline(g, net_cf)
                    sim_list.append(sim)
                    answer_lines.append(
                        f"• **{g.goal_name}**: Target ${g.target_amount:,.2f} (Saved ${g.current_amount:,.2f}). "
                        f"Est. completion: **{sim['months_to_target']} months** ({sim['projected_completion_date']}) based on net cash flow ${net_cf:,.2f}/mo."
                    )
                answer = "\n".join(answer_lines)
                goal_df = pd.DataFrame(sim_list)
            else:
                answer = "No active savings goals configured. Add a goal in the Budget & Goals section."
                goal_df = None

            return {
                "query": query_text,
                "answer": PrivacyMasker.mask_text(answer),
                "data_table": goal_df,
                "sql_executed": "GoalSimulator: Months = (Target - Current) / Net Cash Flow",
                "disclaimer": self._disclaimer()
            }

        # Generic SQL Search Fallback
        else:
            sql = """
                SELECT date, raw_vendor, normalized_vendor, category, ROUND(amount, 2) as amount
                FROM transactions
                ORDER BY date DESC
                LIMIT 15
            """
            result_df = self.db.run_query(sql)
            answer = f"Displaying recent financial transactions for query '{query_text}'."
            return {
                "query": query_text,
                "answer": PrivacyMasker.mask_text(answer),
                "data_table": result_df,
                "sql_executed": sql.strip(),
                "disclaimer": self._disclaimer()
            }

    @staticmethod
    def _disclaimer() -> str:
        return "FinPilot provides objective personal finance decision support based strictly on uploaded data. FinPilot does not provide certified financial, investment, or legal tax advice."
