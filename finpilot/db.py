import duckdb
import pandas as pd
from typing import List, Dict, Any, Optional
from finpilot.models import Transaction, Budget, Goal


class FinPilotDB:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = duckdb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id VARCHAR PRIMARY KEY,
                date VARCHAR,
                raw_vendor VARCHAR,
                normalized_vendor VARCHAR,
                amount DOUBLE,
                category VARCHAR,
                is_recurring BOOLEAN,
                notes VARCHAR,
                source_file VARCHAR
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                category VARCHAR PRIMARY KEY,
                allocated_limit DOUBLE,
                period VARCHAR
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                goal_name VARCHAR PRIMARY KEY,
                target_amount DOUBLE,
                current_amount DOUBLE,
                target_date VARCHAR
            )
        """)

    def insert_transactions(self, tx_list: List[Transaction]):
        if not tx_list:
            return
        
        # Prepare records for insertion
        records = [
            (
                tx.id,
                tx.date,
                tx.raw_vendor,
                tx.normalized_vendor,
                tx.amount,
                tx.category,
                tx.is_recurring,
                tx.notes or "",
                tx.source_file or ""
            )
            for tx in tx_list
        ]
        
        # Insert using parameter binding or DataFrame
        df = pd.DataFrame(records, columns=[
            'id', 'date', 'raw_vendor', 'normalized_vendor', 'amount',
            'category', 'is_recurring', 'notes', 'source_file'
        ])
        
        self.conn.register('temp_tx_df', df)
        self.conn.execute("""
            INSERT OR REPLACE INTO transactions
            SELECT * FROM temp_tx_df
        """)
        self.conn.unregister('temp_tx_df')

    def insert_budgets(self, budget_list: List[Budget]):
        if not budget_list:
            return
        for b in budget_list:
            self.upsert_budget(b)

    def upsert_budget(self, budget: Budget):
        if not budget.category or not budget.category.strip():
            raise ValueError("Budget category cannot be empty.")
        if budget.allocated_limit < 0:
            raise ValueError("Budget allocated limit cannot be negative.")
        self.conn.execute("""
            INSERT OR REPLACE INTO budgets (category, allocated_limit, period)
            VALUES (?, ?, ?)
        """, [budget.category.strip(), float(budget.allocated_limit), budget.period])

    def delete_budget(self, category: str):
        self.conn.execute("DELETE FROM budgets WHERE category = ?", [category.strip()])

    def insert_goals(self, goal_list: List[Goal]):
        if not goal_list:
            return
        for g in goal_list:
            self.add_goal(g)

    def add_goal(self, goal: Goal):
        if not goal.goal_name or not goal.goal_name.strip():
            raise ValueError("Goal name cannot be empty.")
        if goal.target_amount <= 0:
            raise ValueError("Goal target amount must be greater than 0.")
        if goal.current_amount < 0:
            raise ValueError("Goal current amount cannot be negative.")
        self.conn.execute("""
            INSERT OR REPLACE INTO goals (goal_name, target_amount, current_amount, target_date)
            VALUES (?, ?, ?, ?)
        """, [goal.goal_name.strip(), float(goal.target_amount), float(goal.current_amount), goal.target_date])

    def delete_goal(self, goal_name: str):
        self.conn.execute("DELETE FROM goals WHERE goal_name = ?", [goal_name.strip()])

    def get_all_transactions_df(self) -> pd.DataFrame:
        return self.get_transactions_df()

    def get_transactions_df(self) -> pd.DataFrame:
        return self.conn.execute("SELECT * FROM transactions ORDER BY date DESC").df()

    def get_budgets(self) -> List[Budget]:
        df = self.conn.execute("SELECT * FROM budgets").df()
        return [Budget(**row) for row in df.to_dict(orient='records')]

    def get_goals(self) -> List[Goal]:
        df = self.conn.execute("SELECT * FROM goals").df()
        return [Goal(**row) for row in df.to_dict(orient='records')]

    def clear_all(self):
        self.conn.execute("DELETE FROM transactions")
        self.conn.execute("DELETE FROM budgets")
        self.conn.execute("DELETE FROM goals")

    def run_query(self, query: str) -> pd.DataFrame:
        """Executes arbitrary SQL query safely against DuckDB tables."""
        return self.conn.execute(query).df()
