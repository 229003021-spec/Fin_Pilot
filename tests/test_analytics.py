import pytest
import pandas as pd
from finpilot.models import Goal, Budget, TransactionCategory
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector
from finpilot.analytics.committed_spend import CommittedSpendCalculator
from finpilot.analytics.goals_budget import BudgetAndGoalManager
from finpilot.demo_data import generate_sample_transactions, generate_sample_budgets, generate_sample_goals, seed_demo_database
from finpilot.db import FinPilotDB


def test_subscription_tracker():
    txs = generate_sample_transactions()
    df = pd.DataFrame([t.model_dump() for t in txs])
    subs = SubscriptionTracker.detect_subscriptions(df)
    vendors = [s.vendor for s in subs]
    assert "Netflix" in vendors
    assert "Spotify" in vendors


def test_anomaly_detector_cases():
    # 1. Empty data
    empty_df = pd.DataFrame()
    assert AnomalyDetector.detect_anomalies(empty_df) == []

    # 2. Tiny data / single month
    tiny_data = [
        {"id": "1", "date": "2026-03-01", "raw_vendor": "Cafe", "normalized_vendor": "Cafe", "amount": -10.0, "category": "Dining Out"},
        {"id": "2", "date": "2026-03-02", "raw_vendor": "Store", "normalized_vendor": "Store", "amount": -20.0, "category": "Shopping"}
    ]
    tiny_df = pd.DataFrame(tiny_data)
    assert AnomalyDetector.detect_anomalies(tiny_df) == []

    # 3. Normal data with spikes
    txs = generate_sample_transactions()
    df = pd.DataFrame([t.model_dump() for t in txs])
    anomalies = AnomalyDetector.detect_anomalies(df)
    assert len(anomalies) > 0
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
    
    # 1. Normal case
    sim = BudgetAndGoalManager.simulate_goal_timeline(goal, monthly_net_cash_flow=1000.0)
    assert sim['months_to_target'] == 6.0
    assert sim['is_feasible'] is True

    # 2. Zero net cash flow
    sim_zero = BudgetAndGoalManager.simulate_goal_timeline(goal, monthly_net_cash_flow=0.0)
    assert sim_zero['is_feasible'] is False

    # 3. Negative net cash flow
    sim_neg = BudgetAndGoalManager.simulate_goal_timeline(goal, monthly_net_cash_flow=-500.0)
    assert sim_neg['is_feasible'] is False


def test_seed_demo_database_idempotent():
    db = FinPilotDB(":memory:")
    seed_demo_database(db)
    count1 = len(db.get_transactions_df())
    # Calling it a second time should not duplicate rows
    seed_demo_database(db)
    count2 = len(db.get_transactions_df())
    assert count1 == count2
    assert count1 > 0


def test_vendor_search_special_characters():
    txs = generate_sample_transactions()
    df = pd.DataFrame([t.model_dump() for t in txs])
    # Search with special characters (", "*", "SQUARE *") using regex=False
    query1 = "("
    filtered1 = df[df['raw_vendor'].astype(str).str.contains(query1, case=False, regex=False, na=False)]
    assert len(filtered1) >= 0

    query2 = "SQUARE *"
    filtered2 = df[df['raw_vendor'].astype(str).str.contains(query2, case=False, regex=False, na=False)]
    assert len(filtered2) > 0
