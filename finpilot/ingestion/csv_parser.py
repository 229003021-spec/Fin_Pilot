import pandas as pd
from typing import List, Union, BinaryIO
from finpilot.models import Transaction
from finpilot.ingestion.normalizer import SchemaNormalizer
from finpilot.ingestion.categorizer import HybridCategorizer


class CSVStatementParser:
    """Parses bank/credit card CSV statements with flexible header auto-detection."""

    def __init__(self, categorizer: HybridCategorizer = None):
        self.categorizer = categorizer or HybridCategorizer()

    def parse(self, file_source: Union[str, BinaryIO], filename: str = "statement.csv") -> List[Transaction]:
        df = pd.read_csv(file_source)
        if df.empty:
            return []

        # Lowercase column names for robust matching
        cols = {str(c).strip().lower(): c for c in df.columns}

        # 1. Identify Date Column
        date_col = next((cols[c] for c in ['date', 'transaction_date', 'posted_date', 'tx_date', 'trans date'] if c in cols), None)
        if not date_col:
            # Fallback to first column
            date_col = df.columns[0]

        # 2. Identify Vendor / Description Column
        vendor_col = next((cols[c] for c in ['vendor', 'raw_vendor', 'description', 'payee', 'merchant', 'narrative', 'details', 'name'] if c in cols), None)
        if not vendor_col:
            vendor_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

        # 3. Identify Amount / Debit / Credit Columns
        amount_col = next((cols[c] for c in ['amount', 'tx_amount', 'transaction_amount', 'val', 'value'] if c in cols), None)
        debit_col = next((cols[c] for c in ['debit', 'withdrawal', 'outflow', 'expense'] if c in cols), None)
        credit_col = next((cols[c] for c in ['credit', 'deposit', 'inflow', 'income'] if c in cols), None)

        # 4. Identify Category Column (if present)
        cat_col = next((cols[c] for c in ['category', 'type', 'group'] if c in cols), None)

        transactions = []
        for idx, row in df.iterrows():
            raw_date = str(row[date_col]) if pd.notna(row[date_col]) else ""
            iso_date = SchemaNormalizer.normalize_date(raw_date)

            raw_vendor_val = str(row[vendor_col]) if pd.notna(row[vendor_col]) else "Unknown Vendor"
            raw_vendor, norm_vendor = SchemaNormalizer.clean_vendor(raw_vendor_val)

            # Compute amount
            if amount_col:
                amt_val = row[amount_col]
                amount = SchemaNormalizer.normalize_amount(amt_val)
            elif debit_col or credit_col:
                debit_val = row[debit_col] if debit_col and pd.notna(row[debit_col]) else 0.0
                credit_val = row[credit_col] if credit_col and pd.notna(row[credit_col]) else 0.0
                
                d_num = SchemaNormalizer.normalize_amount(debit_val)
                c_num = SchemaNormalizer.normalize_amount(credit_val)
                
                if abs(d_num) > 0:
                    amount = -abs(d_num)
                else:
                    amount = abs(c_num)
            else:
                amount = 0.0

            # Determine category
            if cat_col and pd.notna(row[cat_col]) and str(row[cat_col]).strip():
                category = str(row[cat_col]).strip()
            else:
                category, suggested_norm = self.categorizer.categorize(raw_vendor, amount)
                if suggested_norm and norm_vendor == raw_vendor.title():
                    norm_vendor = suggested_norm

            tx = Transaction(
                date=iso_date,
                raw_vendor=raw_vendor,
                normalized_vendor=norm_vendor,
                amount=amount,
                category=category,
                is_recurring=False,
                source_file=filename
            )
            transactions.append(tx)

        return transactions
