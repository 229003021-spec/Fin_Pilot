from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4, UUID
from datetime import date
from pydantic import BaseModel, Field, field_validator


class TransactionCategory(str, Enum):
    HOUSING = "Housing"
    UTILITIES = "Utilities"
    GROCERIES = "Groceries"
    DINING_OUT = "Dining Out"
    TRANSPORTATION = "Transportation"
    SUBSCRIPTIONS = "Subscriptions"
    SHOPPING = "Shopping"
    INCOME = "Income"
    GENERAL = "General"


class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    date: str  # YYYY-MM-DD format
    raw_vendor: str
    normalized_vendor: str
    amount: float  # Negative for expenses, positive for income
    category: str = TransactionCategory.GENERAL.value
    is_recurring: bool = False
    notes: Optional[str] = None
    source_file: Optional[str] = None

    @field_validator("category", mode="before")
    def validate_category(cls, v):
        if not v:
            return TransactionCategory.GENERAL.value
        # If passed string matches enum value or case insensitive, match it
        v_str = str(v).strip()
        for cat in TransactionCategory:
            if cat.value.lower() == v_str.lower():
                return cat.value
        return v_str


class Budget(BaseModel):
    category: str
    allocated_limit: float
    period: str = "monthly"


class Goal(BaseModel):
    goal_name: str
    target_amount: float
    current_amount: float
    target_date: str  # YYYY-MM-DD

    @property
    def remaining_amount(self) -> float:
        return max(0.0, self.target_amount - self.current_amount)


class CategorizationRule(BaseModel):
    pattern: str  # Regex or substring
    category: str
    normalized_vendor: Optional[str] = None
    priority: int = 10


class AnomalyFlag(BaseModel):
    transaction_id: str
    date: str
    vendor: str
    amount: float
    category: str
    anomaly_type: str  # "vendor_std_dev", "category_mom_spike"
    reason: str
    severity: str = "HIGH"  # HIGH, MEDIUM, LOW


class RecurringSubscription(BaseModel):
    vendor: str
    category: str
    average_amount: float
    frequency: str  # "monthly", "annual"
    interval_days: float
    price_variance_pct: float
    transaction_count: int
    last_payment_date: str


class MonthlySummary(BaseModel):
    month_year: str  # YYYY-MM
    total_income: float
    total_expenses: float
    net_cash_flow: float
    savings_rate_pct: float
    committed_spend_ratio: float
    safe_to_spend: float
    top_spending_categories: Dict[str, float]
    anomalies: List[AnomalyFlag]
    active_subscriptions_count: int
    monthly_subscriptions_cost: float
