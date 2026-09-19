import re
from typing import Optional, List, Tuple
from finpilot.models import TransactionCategory, CategorizationRule


# Default high-precision rule dictionary
DEFAULT_RULES: List[Tuple[str, str, Optional[str]]] = [
    # (pattern, category, optional normalized vendor)
    (r'\b(salary|payroll|direct dep|paycheck|stipend|employer|income)\b', TransactionCategory.INCOME.value, "Employer Direct Deposit"),
    (r'\b(rent|lease|mortgage|property mgmt|housing)\b', TransactionCategory.HOUSING.value, "Housing / Rent"),
    (r'\b(electric|water|gas bill|power|coned|utility|sewer|trash|national grid|pge)\b', TransactionCategory.UTILITIES.value, "Utility Service"),
    (r'\b(trader joe|whole foods|walmart|kroger|safeway|aldi|costco|grocer|supermarket|market)\b', TransactionCategory.GROCERIES.value, None),
    (r'\b(starbucks|cafe|coffee|mcdonald|subway|chipotle|uber eats|doordash|grubhub|restaurant|diner|bistro|taco|burger|dining)\b', TransactionCategory.DINING_OUT.value, None),
    (r'\b(netflix|spotify|hulu|disney\+|apple\.com/bill|amazon prime|hbo|youtube|patreon|nytimes|subscriptions)\b', TransactionCategory.SUBSCRIPTIONS.value, None),
    (r'\b(uber|lyft|shell|chevron|exxon|bp|gas station|transit|metro|parking|toll)\b', TransactionCategory.TRANSPORTATION.value, None),
    (r'\b(amazon|target|ebay|best buy|zara|nordstrom|nike|apparel|store|clothing|shopping)\b', TransactionCategory.SHOPPING.value, None),
]


class HybridCategorizer:
    """
    Combines deterministic rule matching with intelligent fallback context inference.
    """

    def __init__(self, custom_rules: Optional[List[CategorizationRule]] = None):
        self.rules = list(DEFAULT_RULES)
        if custom_rules:
            for rule in custom_rules:
                self.rules.insert(0, (rule.pattern, rule.category, rule.normalized_vendor))

    def categorize(self, raw_vendor: str, amount: float = 0.0) -> Tuple[str, Optional[str]]:
        """
        Categorizes vendor text into one of the standard TransactionCategory values.
        Returns: (category, suggested_normalized_vendor)
        """
        if amount > 0:
            # Positive amounts default to Income unless explicitly marked otherwise
            if any(re.search(pat, raw_vendor, re.IGNORECASE) for pat, cat, _ in self.rules if cat != TransactionCategory.INCOME.value):
                pass
            else:
                return TransactionCategory.INCOME.value, "Income / Deposit"

        vendor_lower = raw_vendor.lower()

        # Step 1: Rule-based regex lookup
        for pattern, category, norm_vendor in self.rules:
            if re.search(pattern, vendor_lower, re.IGNORECASE):
                return category, norm_vendor

        # Step 2: Key word fallback heuristics
        if any(w in vendor_lower for w in ['cafe', 'coffee', 'bakery', 'kitchen', 'grill', 'bar', 'food', 'eats', 'pizza', 'sushi']):
            return TransactionCategory.DINING_OUT.value, None
        if any(w in vendor_lower for w in ['mart', 'market', 'farm', 'food', 'grocery', 'fresh']):
            return TransactionCategory.GROCERIES.value, None
        if any(w in vendor_lower for w in ['sub', 'membership', 'cloud', 'digital', 'saas', 'monthly']):
            return TransactionCategory.SUBSCRIPTIONS.value, None
        if any(w in vendor_lower for w in ['oil', 'gas', 'auto', 'ride', 'taxi', 'cab', 'transit']):
            return TransactionCategory.TRANSPORTATION.value, None

        # Step 3: General fallback
        return TransactionCategory.GENERAL.value, None
