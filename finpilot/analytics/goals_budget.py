from typing import List, Dict, Any, Optional
import pandas as pd
from finpilot.models import Budget, Goal


class BudgetAndGoalManager:
    """
    Budget variance tracking and deterministic Goal timeline simulation.
    """

    @staticmethod
    def calculate_budget_variance(df: pd.DataFrame, budgets: List[Budget]) -> List[Dict[str, Any]]:
        """
        Calculates category spending vs allocated budget limits.
        """
        if not budgets:
            return []

        expenses_df = df[df['amount'] < 0].copy() if not df.empty else pd.DataFrame()
        if not expenses_df.empty:
            expenses_df['abs_amount'] = expenses_df['amount'].abs()
            expenses_df['dt'] = pd.to_datetime(expenses_df['date'])
            # Filter for current month or average monthly
            months = max(1, expenses_df['dt'].dt.to_period('M').nunique())
            cat_spend = (expenses_df.groupby('category')['abs_amount'].sum() / months).to_dict()
        else:
            cat_spend = {}

        results = []
        for b in budgets:
            spent = cat_spend.get(b.category, 0.0)
            allocated = b.allocated_limit
            remaining = allocated - spent
            pct_used = (spent / allocated * 100.0) if allocated > 0 else 0.0
            status = "NORMAL"
            if pct_used > 100.0:
                status = "EXCEEDED"
            elif pct_used >= 85.0:
                status = "WARNING"

            results.append({
                'category': b.category,
                'allocated_limit': round(allocated, 2),
                'spent': round(spent, 2),
                'remaining': round(remaining, 2),
                'pct_used': round(pct_used, 1),
                'status': status
            })

        return results

    @staticmethod
    def simulate_goal_timeline(
        goal: Goal,
        monthly_net_cash_flow: float,
        monthly_expense_reduction: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculates target completion months based on net cash flow:
        Months to Target Goal = (Target Amount - Current Savings) / Monthly Net Cash Flow
        """
        effective_net_cash_flow = monthly_net_cash_flow + monthly_expense_reduction
        remaining_amount = goal.remaining_amount

        if remaining_amount <= 0:
            return {
                'goal_name': goal.goal_name,
                'target_amount': goal.target_amount,
                'current_amount': goal.current_amount,
                'remaining_amount': 0.0,
                'monthly_net_cash_flow': round(effective_net_cash_flow, 2),
                'months_to_target': 0.0,
                'projected_completion_date': "Achieved",
                'is_feasible': True,
                'notes': "Target goal is already fully funded!"
            }

        if effective_net_cash_flow <= 0:
            return {
                'goal_name': goal.goal_name,
                'target_amount': goal.target_amount,
                'current_amount': goal.current_amount,
                'remaining_amount': round(remaining_amount, 2),
                'monthly_net_cash_flow': round(effective_net_cash_flow, 2),
                'months_to_target': float('inf'),
                'projected_completion_date': "N/A (Net Cash Flow <= 0)",
                'is_feasible': False,
                'notes': "Net cash flow is negative or zero. Increase income or reduce expenses to reach target."
            }

        months_to_target = remaining_amount / effective_net_cash_flow
        
        # Calculate estimated completion date from today
        from datetime import datetime
        from dateutil.relativedelta import relativedelta # fallback or manual calculation
        
        months_int = int(months_to_target)
        days_int = int((months_to_target - months_int) * 30)
        
        today = datetime.now()
        # approximate addition
        year = today.year + (today.month + months_int - 1) // 12
        month = (today.month + months_int - 1) % 12 + 1
        est_date = f"{year:04d}-{month:02d}-{min(28, today.day):02d}"

        return {
            'goal_name': goal.goal_name,
            'target_amount': goal.target_amount,
            'current_amount': goal.current_amount,
            'remaining_amount': round(remaining_amount, 2),
            'monthly_net_cash_flow': round(effective_net_cash_flow, 2),
            'months_to_target': round(months_to_target, 1),
            'projected_completion_date': est_date,
            'is_feasible': True,
            'notes': f"On track! Will reach goal in ~{round(months_to_target, 1)} months."
        }
