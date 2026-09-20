from typing import List
import pandas as pd
import numpy as np
from datetime import datetime
from finpilot.models import RecurringSubscription


class SubscriptionTracker:
    """
    Detects recurring subscription transactions by analyzing date intervals (~30-day or annual cycles)
    and low price variance (<= 5%).
    """

    @staticmethod
    def detect_subscriptions(df: pd.DataFrame) -> List[RecurringSubscription]:
        if df.empty or len(df) < 2:
            return []

        # Filter out positive income transactions
        expenses_df = df[df['amount'] < 0].copy()
        if expenses_df.empty:
            return []

        expenses_df['abs_amount'] = expenses_df['amount'].abs()
        expenses_df['dt'] = pd.to_datetime(expenses_df['date'])

        # Group by normalized_vendor or raw_vendor
        grouped = expenses_df.groupby('normalized_vendor')

        recurring_list = []

        for vendor, group in grouped:
            if len(group) < 2:
                # Need at least 2 occurrences to analyze interval frequency
                continue

            group_sorted = group.sort_values('dt')
            dates = group_sorted['dt'].tolist()
            amounts = group_sorted['abs_amount'].tolist()

            # Calculate date intervals (days between consecutive transactions)
            raw_intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
            positive_intervals = [d for d in raw_intervals if d > 0]
            if not positive_intervals:
                continue
            avg_interval = float(np.mean(positive_intervals))

            # Calculate price variance
            mean_amt = float(np.mean(amounts))
            if mean_amt == 0:
                continue

            price_variance_pct = (float(np.std(amounts)) / mean_amt) * 100.0

            # Frequency check:
            # Monthly cycle: avg_interval between 25 and 35 days
            # Annual cycle: avg_interval between 350 and 380 days
            is_monthly = 25 <= avg_interval <= 35
            is_annual = 350 <= avg_interval <= 380

            # Rule requirement: low price variance (<= 5%)
            if (is_monthly or is_annual) and price_variance_pct <= 5.0:
                freq_str = "monthly" if is_monthly else "annual"
                category = group_sorted['category'].iloc[-1]
                last_payment = group_sorted['date'].iloc[-1]

                sub = RecurringSubscription(
                    vendor=str(vendor),
                    category=str(category),
                    average_amount=round(mean_amt, 2),
                    frequency=freq_str,
                    interval_days=round(avg_interval, 1),
                    price_variance_pct=round(price_variance_pct, 2),
                    transaction_count=len(group),
                    last_payment_date=str(last_payment)
                )
                recurring_list.append(sub)

        return recurring_list
