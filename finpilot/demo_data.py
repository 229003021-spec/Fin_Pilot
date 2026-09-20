import os
import json
import pandas as pd
from typing import List, Dict, Any
from finpilot.models import Transaction, Budget, Goal, TransactionCategory
from finpilot.db import FinPilotDB


def generate_sample_transactions() -> List[Transaction]:
    """Generates realistic multi-month financial sample data for FinPilot."""
    records = [
        # Income - Monthly
        {"date": "2026-01-01", "raw_vendor": "TECH CORP PAYROLL ACH_DIRECT", "normalized_vendor": "Tech Corp Salary", "amount": 4500.00, "category": TransactionCategory.INCOME.value, "is_recurring": True},
        {"date": "2026-02-01", "raw_vendor": "TECH CORP PAYROLL ACH_DIRECT", "normalized_vendor": "Tech Corp Salary", "amount": 4500.00, "category": TransactionCategory.INCOME.value, "is_recurring": True},
        {"date": "2026-03-01", "raw_vendor": "TECH CORP PAYROLL ACH_DIRECT", "normalized_vendor": "Tech Corp Salary", "amount": 4500.00, "category": TransactionCategory.INCOME.value, "is_recurring": True},

        # Housing - Rent
        {"date": "2026-01-02", "raw_vendor": "AVALON APARTMENTS LEASE PAYMENT", "normalized_vendor": "Avalon Apartments", "amount": -1800.00, "category": TransactionCategory.HOUSING.value, "is_recurring": True},
        {"date": "2026-02-02", "raw_vendor": "AVALON APARTMENTS LEASE PAYMENT", "normalized_vendor": "Avalon Apartments", "amount": -1800.00, "category": TransactionCategory.HOUSING.value, "is_recurring": True},
        {"date": "2026-03-02", "raw_vendor": "AVALON APARTMENTS LEASE PAYMENT", "normalized_vendor": "Avalon Apartments", "amount": -1800.00, "category": TransactionCategory.HOUSING.value, "is_recurring": True},

        # Utilities
        {"date": "2026-01-05", "raw_vendor": "CONED ELECTRIC BILL NY", "normalized_vendor": "ConEd Electric", "amount": -115.00, "category": TransactionCategory.UTILITIES.value, "is_recurring": True},
        {"date": "2026-02-05", "raw_vendor": "CONED ELECTRIC BILL NY", "normalized_vendor": "ConEd Electric", "amount": -118.00, "category": TransactionCategory.UTILITIES.value, "is_recurring": True},
        {"date": "2026-03-05", "raw_vendor": "CONED ELECTRIC BILL NY", "normalized_vendor": "ConEd Electric", "amount": -120.00, "category": TransactionCategory.UTILITIES.value, "is_recurring": True},

        # Subscriptions (~30 day frequency, <= 5% variance)
        {"date": "2026-01-10", "raw_vendor": "NETFLIX.COM DIGITAL SUB", "normalized_vendor": "Netflix", "amount": -19.99, "category": TransactionCategory.SUBSCRIPTIONS.value, "is_recurring": True},
        {"date": "2026-02-10", "raw_vendor": "NETFLIX.COM DIGITAL SUB", "normalized_vendor": "Netflix", "amount": -19.99, "category": TransactionCategory.SUBSCRIPTIONS.value, "is_recurring": True},
        {"date": "2026-03-10", "raw_vendor": "NETFLIX.COM DIGITAL SUB", "normalized_vendor": "Netflix", "amount": -19.99, "category": TransactionCategory.SUBSCRIPTIONS.value, "is_recurring": True},

        {"date": "2026-01-15", "raw_vendor": "SPOTIFY PREMIUM USA", "normalized_vendor": "Spotify", "amount": -10.99, "category": TransactionCategory.SUBSCRIPTIONS.value, "is_recurring": True},
        {"date": "2026-02-15", "raw_vendor": "SPOTIFY PREMIUM USA", "normalized_vendor": "Spotify", "amount": -10.99, "category": TransactionCategory.SUBSCRIPTIONS.value, "is_recurring": True},
        {"date": "2026-03-15", "raw_vendor": "SPOTIFY PREMIUM USA", "normalized_vendor": "Spotify", "amount": -10.99, "category": TransactionCategory.SUBSCRIPTIONS.value, "is_recurring": True},

        # Groceries
        {"date": "2026-01-08", "raw_vendor": "TRADER JOE'S #542 SEATTLE", "normalized_vendor": "Trader Joe's", "amount": -145.20, "category": TransactionCategory.GROCERIES.value, "is_recurring": False},
        {"date": "2026-01-22", "raw_vendor": "WHOLE FOODS MKT 104", "normalized_vendor": "Whole Foods", "amount": -182.50, "category": TransactionCategory.GROCERIES.value, "is_recurring": False},
        {"date": "2026-02-09", "raw_vendor": "TRADER JOE'S #542 SEATTLE", "normalized_vendor": "Trader Joe's", "amount": -150.00, "category": TransactionCategory.GROCERIES.value, "is_recurring": False},
        {"date": "2026-02-23", "raw_vendor": "WHOLE FOODS MKT 104", "normalized_vendor": "Whole Foods", "amount": -175.40, "category": TransactionCategory.GROCERIES.value, "is_recurring": False},
        {"date": "2026-03-07", "raw_vendor": "TRADER JOE'S #542 SEATTLE", "normalized_vendor": "Trader Joe's", "amount": -162.10, "category": TransactionCategory.GROCERIES.value, "is_recurring": False},

        # Dining Out & Anomaly Spikes
        {"date": "2026-01-12", "raw_vendor": "SQUARE * CAFE BAKERY", "normalized_vendor": "Square Cafe", "amount": -14.50, "category": TransactionCategory.DINING_OUT.value, "is_recurring": False},
        {"date": "2026-01-18", "raw_vendor": "CHIPOTLE ONLINE #88", "normalized_vendor": "Chipotle", "amount": -18.75, "category": TransactionCategory.DINING_OUT.value, "is_recurring": False},
        {"date": "2026-02-14", "raw_vendor": "SQUARE * CAFE BAKERY", "normalized_vendor": "Square Cafe", "amount": -15.20, "category": TransactionCategory.DINING_OUT.value, "is_recurring": False},
        {"date": "2026-02-20", "raw_vendor": "CHIPOTLE ONLINE #88", "normalized_vendor": "Chipotle", "amount": -22.10, "category": TransactionCategory.DINING_OUT.value, "is_recurring": False},
        
        # March Dining Out Spike (>20% MoM and >2.5x Std Dev anomaly event!)
        {"date": "2026-03-12", "raw_vendor": "SQUARE * CAFE BAKERY", "normalized_vendor": "Square Cafe", "amount": -16.00, "category": TransactionCategory.DINING_OUT.value, "is_recurring": False},
        {"date": "2026-03-18", "raw_vendor": "LE BERNARDIN FINE DINING NY", "normalized_vendor": "Le Bernardin", "amount": -580.00, "category": TransactionCategory.DINING_OUT.value, "is_recurring": False},

        # Transportation
        {"date": "2026-01-14", "raw_vendor": "UBER TRIP RIDE PASS", "normalized_vendor": "Uber", "amount": -28.50, "category": TransactionCategory.TRANSPORTATION.value, "is_recurring": False},
        {"date": "2026-02-16", "raw_vendor": "UBER TRIP RIDE PASS", "normalized_vendor": "Uber", "amount": -32.00, "category": TransactionCategory.TRANSPORTATION.value, "is_recurring": False},
        {"date": "2026-03-14", "raw_vendor": "UBER TRIP RIDE PASS", "normalized_vendor": "Uber", "amount": -35.50, "category": TransactionCategory.TRANSPORTATION.value, "is_recurring": False},

        # Shopping
        {"date": "2026-01-25", "raw_vendor": "AMAZON.COM*ORDER 940", "normalized_vendor": "Amazon", "amount": -65.40, "category": TransactionCategory.SHOPPING.value, "is_recurring": False},
        {"date": "2026-02-28", "raw_vendor": "AMAZON.COM*ORDER 112", "normalized_vendor": "Amazon", "amount": -89.90, "category": TransactionCategory.SHOPPING.value, "is_recurring": False},
        {"date": "2026-03-22", "raw_vendor": "AMAZON.COM*ORDER 551", "normalized_vendor": "Amazon", "amount": -142.00, "category": TransactionCategory.SHOPPING.value, "is_recurring": False},
    ]

    return [Transaction(**r) for r in records]


def generate_sample_budgets() -> List[Budget]:
    return [
        Budget(category=TransactionCategory.HOUSING.value, allocated_limit=1850.00),
        Budget(category=TransactionCategory.GROCERIES.value, allocated_limit=450.00),
        Budget(category=TransactionCategory.DINING_OUT.value, allocated_limit=250.00),
        Budget(category=TransactionCategory.SUBSCRIPTIONS.value, allocated_limit=50.00),
        Budget(category=TransactionCategory.UTILITIES.value, allocated_limit=150.00),
        Budget(category=TransactionCategory.TRANSPORTATION.value, allocated_limit=100.00),
        Budget(category=TransactionCategory.SHOPPING.value, allocated_limit=200.00),
    ]


def generate_sample_goals() -> List[Goal]:
    return [
        Goal(goal_name="Emergency Fund (6 Months)", target_amount=15000.00, current_amount=8500.00, target_date="2026-12-31"),
        Goal(goal_name="Japan Summer Vacation", target_amount=4000.00, current_amount=1800.00, target_date="2026-08-01"),
    ]


def seed_demo_database(db: FinPilotDB):
    """Seeds DuckDB database with demo dataset."""
    db.clear_all()
    db.insert_transactions(generate_sample_transactions())
    db.insert_budgets(generate_sample_budgets())
    db.insert_goals(generate_sample_goals())


def export_sample_files(output_dir: str = "."):
    """Exports sample CSV and JSON files if missing from disk."""
    csv_path = os.path.join(output_dir, "sample_bank_statement.csv")
    json_path = os.path.join(output_dir, "sample_credit_statement.json")

    if os.path.exists(csv_path) and os.path.exists(json_path):
        return

    os.makedirs(output_dir, exist_ok=True)
    txs = generate_sample_transactions()
    
    if not os.path.exists(csv_path):
        csv_data = [
            {
                "Date": t.date,
                "Description": t.raw_vendor,
                "Amount": t.amount,
                "Category": t.category
            }
            for t in txs
        ]
        pd.DataFrame(csv_data).to_csv(csv_path, index=False)
    
    if not os.path.exists(json_path):
        json_data = [t.model_dump() for t in txs]
        with open(json_path, "w") as f:
            json.dump({"Transaction": json_data}, f, indent=2)
