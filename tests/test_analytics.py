import pytest
import pandas as pd
from finpilot.models import Goal, Budget, TransactionCategory
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector
from finpilot.analytics.committed_spend import CommittedSpendCalculator
from finpilot.analytics.goals_budget import BudgetAndGoalManager
from finpilot.demo_data import generate_sample_transactions, generate_sample_budgets, generate_sample_goals


def test_subscription_tracker():
    txs = generate_sample_transactions()
    df = pd.DataFrame([t.model_dump() for t in txs])
    subs = SubscriptionTracker.detect_subscriptions(df)
    vendors = [s.vendor for s in subs]
    assert "Netflix" in vendors
    assert "Spotify" in vendors


def test_anomaly_detector():
    txs = generate_sample_transactions()
    df = pd.DataFrame([t.model_dump() for t in txs])
    anomalies = AnomalyDetector.detect_anomalies(df)
    assert len(anomalies) > 0
    # Should flag Le Bernardin dining outlier (>2.5 std dev)
    anom_vendors = [a.vendor for a in anomalies]
    assert any("Bernard" in v or "Dining" in v or "Spike" in v for v in anom_vendors)


def test_committed_spend_calculator():
    txs = generate_sample_transactions()
    df = pd.DataFrame([t.model_dump() for t in txs])
    res = CommittedSpendCalculator.calculate_committed_spend(df, current_balance=5000.0, monthly_income=4500.0)
    assert res['committed_obligations'] > 0
    assert res['committed_spend_ratio_pct'] > 0
    assert res['safe_to_spend_balance'] >= 0


def test_budget_variance():
    txs = generate_sample_transactions()
    budgets = generate_sample_budgets()
    df = pd.DataFrame([t.model_dump() for t in txs])
    variance = BudgetAndGoalManager.calculate_budget_variance(df, budgets)
    assert len(variance) == len(budgets)
    cats = [v['category'] for v in variance]
    assert TransactionCategory.HOUSING.value in cats


def test_goal_simulation():
    goal = Goal(goal_name="Emergency Fund", target_amount=10000.0, current_amount=4000.0, target_date="2026-12-31")
    # Remaining = 6000. Net cash flow = 1000. Months = 6.0
    sim = BudgetAndGoalManager.simulate_goal_timeline(goal, monthly_net_cash_flow=1000.0)
    assert sim['months_to_target'] == 6.0
    assert sim['is_feasible'] is True
