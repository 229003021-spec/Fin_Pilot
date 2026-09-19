import json
from typing import List, Union, Dict, Any, BinaryIO
from finpilot.models import Transaction
from finpilot.ingestion.normalizer import SchemaNormalizer
from finpilot.ingestion.categorizer import HybridCategorizer


class JSONStatementParser:
    """Parses JSON transaction exports or statement payloads."""

    def __init__(self, categorizer: HybridCategorizer = None):
        self.categorizer = categorizer or HybridCategorizer()

    def parse(self, data_source: Union[str, BinaryIO, List[Dict[str, Any]], Dict[str, Any]], filename: str = "statement.json") -> List[Transaction]:
        if isinstance(data_source, (str, bytes)):
            try:
                data = json.loads(data_source)
            except Exception:
                return []
        elif hasattr(data_source, 'read'):
            content = data_source.read()
            data = json.loads(content)
        else:
            data = data_source

        if isinstance(data, dict):
            # Check for keys like 'transactions', 'items', 'records', or 'Transaction'
            if "Transaction" in data and isinstance(data["Transaction"], list):
                items = data["Transaction"]
            elif "Transaction" in data and isinstance(data["Transaction"], dict):
                items = [data["Transaction"]]
            elif "transactions" in data:
                items = data["transactions"]
            elif "records" in data:
                items = data["records"]
            else:
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            return []

        transactions = []
        for item in items:
            if not isinstance(item, dict):
                continue

            raw_date = str(item.get("date", item.get("transaction_date", "")))
            iso_date = SchemaNormalizer.normalize_date(raw_date)

            raw_vendor_val = str(item.get("raw_vendor", item.get("vendor", item.get("description", "Unknown Vendor"))))
            raw_vendor, norm_vendor = SchemaNormalizer.clean_vendor(raw_vendor_val)
            if item.get("normalized_vendor"):
                norm_vendor = str(item["normalized_vendor"])

            amt_val = item.get("amount", item.get("val", 0.0))
            amount = SchemaNormalizer.normalize_amount(amt_val)

            category = item.get("category")
            if not category or str(category).lower() in ["general", "none", "null"]:
                category, suggested_norm = self.categorizer.categorize(raw_vendor, amount)
                if suggested_norm and norm_vendor == raw_vendor.title():
                    norm_vendor = suggested_norm

            is_recurring = bool(item.get("is_recurring", False))

            kwargs = {
                "date": iso_date,
                "raw_vendor": raw_vendor,
                "normalized_vendor": norm_vendor,
                "amount": amount,
                "category": str(category),
                "is_recurring": is_recurring,
                "notes": item.get("notes"),
                "source_file": filename
            }
            if item.get("id"):
                kwargs["id"] = str(item.get("id"))
            tx = Transaction(**kwargs)
            transactions.append(tx)

        return transactions
