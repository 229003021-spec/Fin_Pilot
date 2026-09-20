from typing import List
import pandas as pd
import numpy as np
from finpilot.models import AnomalyFlag


class AnomalyDetector:
    """
    Identifies vendor/category transactions exceeding 2.5x standard deviation,
    and category-level month-over-month (MoM) spending spikes (>20%).
    """

    @staticmethod
    def detect_anomalies(df: pd.DataFrame) -> List[AnomalyFlag]:
        if df.empty:
            return []

        expenses_df = df[df['amount'] < 0].copy()
        if expenses_df.empty:
            return []

        expenses_df['abs_amount'] = expenses_df['amount'].abs()
        expenses_df['dt'] = pd.to_datetime(expenses_df['date'])
        expenses_df['month_year'] = expenses_df['dt'].dt.strftime('%Y-%m')

        anomalies: List[AnomalyFlag] = []

        # 1. Vendor & Category Standard Deviation Check (> 2.5x historical std dev)
        # Group by category
        for category, cat_group in expenses_df.groupby('category'):
            if len(cat_group) >= 3:
                mean_amt = cat_group['abs_amount'].mean()
                std_amt = cat_group['abs_amount'].std()

                if std_amt > 0:
                    threshold = mean_amt + (2.5 * std_amt)
                    outliers = cat_group[cat_group['abs_amount'] > threshold]

                    for _, row in outliers.iterrows():
                        reason = (
                            f"Transaction amount (${row['abs_amount']:.2f}) exceeds historical "
                            f"category mean (${mean_amt:.2f}) by >2.5x standard deviation "
                            f"(Threshold: ${threshold:.2f}, Std Dev: ${std_amt:.2f})."
                        )
                        anomalies.append(AnomalyFlag(
                            transaction_id=str(row['id']),
                            date=str(row['date']),
                            vendor=str(row['normalized_vendor']),
                            amount=float(row['amount']),
                            category=str(category),
                            anomaly_type="vendor_std_dev",
                            reason=reason,
                            severity="HIGH"
                        ))

        # Group by vendor for vendor-level std dev
        for vendor, ven_group in expenses_df.groupby('normalized_vendor'):
            if len(ven_group) >= 3:
                mean_amt = ven_group['abs_amount'].mean()
                std_amt = ven_group['abs_amount'].std()

                if std_amt > 0:
                    threshold = mean_amt + (2.5 * std_amt)
                    outliers = ven_group[ven_group['abs_amount'] > threshold]

                    for _, row in outliers.iterrows():
                        # Avoid adding exact duplicate if already flagged by category
                        if not any(a.transaction_id == str(row['id']) for a in anomalies):
                            reason = (
                                f"Vendor transaction amount (${row['abs_amount']:.2f}) exceeds historical "
                                f"vendor mean (${mean_amt:.2f}) by >2.5x standard deviation."
                            )
                            anomalies.append(AnomalyFlag(
                                transaction_id=str(row['id']),
                                date=str(row['date']),
                                vendor=str(vendor),
                                amount=float(row['amount']),
                                category=str(row['category']),
                                anomaly_type="vendor_std_dev",
                                reason=reason,
                                severity="HIGH"
                            ))

        # 2. Category-level Month-over-Month Spending Spikes (>20% MoM increase)
        # Aggregate spending by category and month_year
        monthly_cat = expenses_df.groupby(['category', 'month_year'])['abs_amount'].sum().reset_index()
        months_sorted = sorted(monthly_cat['month_year'].unique())

        if len(months_sorted) >= 2:
            latest_month = months_sorted[-1]
            prev_month = months_sorted[-2]

            latest_cat_df = monthly_cat[monthly_cat['month_year'] == latest_month]
            prev_cat_df = monthly_cat[monthly_cat['month_year'] == prev_month].set_index('category')['abs_amount'].to_dict()

            for _, row in latest_cat_df.iterrows():
                cat = row['category']
                curr_spend = row['abs_amount']
                prev_spend = prev_cat_df.get(cat, 0.0)

                if prev_spend > 0:
                    dollar_diff = curr_spend - prev_spend
                    pct_increase = (dollar_diff / prev_spend) * 100.0
                    # Must be >20% MoM increase AND at least $25.00 dollar increase to prevent false positives on small transactions
                    if pct_increase > 20.0 and dollar_diff >= 25.0:
                        reason = (
                            f"Category spending for '{cat}' in {latest_month} (${curr_spend:.2f}) "
                            f"increased by {pct_increase:.1f}% (+${dollar_diff:.2f}) compared to {prev_month} (${prev_spend:.2f})."
                        )
                        anomalies.append(AnomalyFlag(
                            transaction_id=f"mom_spike_{cat}_{latest_month}",
                            date=f"{latest_month}-01",
                            vendor=f"Category Spike: {cat}",
                            amount=-curr_spend,
                            category=cat,
                            anomaly_type="category_mom_spike",
                            reason=reason,
                            severity="MEDIUM" if pct_increase < 50 else "HIGH"
                        ))

        return anomalies
