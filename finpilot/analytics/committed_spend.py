from typing import Dict, Any, List
import pandas as pd


class CommittedSpendCalculator:
    """
    Calculates fixed obligations due prior to the next income cycle to determine safe-to-spend balances.
    """

    @staticmethod
    def calculate_committed_spend(
        df: pd.DataFrame,
        current_balance: float = 0.0,
        monthly_income: float = 0.0
    ) -> Dict[str, Any]:
        """
        Returns:
        {
            'total_income': float,
            'committed_obligations': float,
            'committed_spend_ratio_pct': float,
            'safe_to_spend_balance': float,
            'fixed_vendors': List[str]
        }
        """
        if df.empty:
            return {
                'total_income': monthly_income,
                'committed_obligations': 0.0,
                'committed_spend_ratio_pct': 0.0,
                'safe_to_spend_balance': current_balance,
                'fixed_vendors': []
            }

        df['dt'] = pd.to_datetime(df['date'])

        # Calculate income if not explicitly passed
        if monthly_income <= 0:
            income_df = df[df['amount'] > 0]
            if not income_df.empty:
                # Average monthly income or sum of income in recent month
                months = income_df['dt'].dt.to_period('M').nunique()
                monthly_income = income_df['amount'].sum() / max(1, months)
            else:
                monthly_income = 0.0

        # Fixed categories: Housing, Utilities, Subscriptions, plus marked recurring items
        fixed_categories = ['Housing', 'Utilities', 'Subscriptions']
        expenses_df = df[df['amount'] < 0].copy()
        expenses_df['abs_amount'] = expenses_df['amount'].abs()

        fixed_df = expenses_df[
            (expenses_df['category'].isin(fixed_categories)) | (expenses_df['is_recurring'] == True)
        ]

        if not fixed_df.empty:
            months = expenses_df['dt'].dt.to_period('M').nunique()
            committed_obligations = fixed_df['abs_amount'].sum() / max(1, months)
            fixed_vendors = sorted(fixed_df['normalized_vendor'].unique().tolist())
        else:
            committed_obligations = 0.0
            fixed_vendors = []

        ratio_pct = (committed_obligations / monthly_income * 100.0) if monthly_income > 0 else 0.0
        
        # Safe to spend = current balance - upcoming committed obligations
        safe_to_spend = max(0.0, current_balance - committed_obligations) if current_balance > 0 else max(0.0, monthly_income - committed_obligations)

        return {
            'total_income': round(monthly_income, 2),
            'committed_obligations': round(committed_obligations, 2),
            'committed_spend_ratio_pct': round(ratio_pct, 1),
            'safe_to_spend_balance': round(safe_to_spend, 2),
            'fixed_vendors': fixed_vendors
        }
