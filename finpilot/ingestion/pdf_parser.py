import re
from typing import List, Union, BinaryIO
from pypdf import PdfReader
from finpilot.models import Transaction
from finpilot.ingestion.normalizer import SchemaNormalizer
from finpilot.ingestion.categorizer import HybridCategorizer


class PDFStatementParser:
    """Parses bank/credit card statements and utility bills from PDF files."""

    def __init__(self, categorizer: HybridCategorizer = None):
        self.categorizer = categorizer or HybridCategorizer()

    def parse(self, file_source: Union[str, BinaryIO], filename: str = "statement.pdf") -> List[Transaction]:
        try:
            reader = PdfReader(file_source)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        except Exception:
            return []

        if not full_text.strip():
            return []

        return self._extract_transactions_from_text(full_text, filename)

    def _extract_transactions_from_text(self, text: str, filename: str) -> List[Transaction]:
        lines = text.split("\n")
        transactions = []

        # Common line patterns:
        # Pattern 1: Date (MM/DD/YYYY or YYYY-MM-DD or Mon DD) Vendor Amount ($XX.XX or -XX.XX)
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s*\d{0,4})'
        amount_pattern = r'(-?\$?\s*[\d,]+\.\d{2}\b|\(\$?[\d,]+\.\d{2}\))'

        line_regex = re.compile(f'^{date_pattern}\\s+(.*?)\\s+{amount_pattern}', re.IGNORECASE)

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            match = line_regex.search(line_str)
            if match:
                raw_date_str, raw_vendor_str, raw_amt_str = match.groups()
                
                iso_date = SchemaNormalizer.normalize_date(raw_date_str)
                raw_vendor, norm_vendor = SchemaNormalizer.clean_vendor(raw_vendor_str)
                
                amount = SchemaNormalizer.normalize_amount(raw_amt_str)
                
                # Deduce category
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
                continue

            # Check utility bill single total pattern (e.g., "Total Amount Due: $145.50" or "ConEd Electric Bill ... Date: 2026-03-15 ... $120.00")
            if "total" in line_str.lower() or "amount due" in line_str.lower():
                amt_match = re.search(amount_pattern, line_str)
                if amt_match:
                    amt_str = amt_match.group(1)
                    amount = SchemaNormalizer.normalize_amount(amt_str)
                    if amount > 0:
                        amount = -amount # expenses
                        
                    raw_vendor = filename.replace(".pdf", "").replace("_", " ").title()
                    iso_date = SchemaNormalizer.normalize_date("")
                    category, suggested_norm = self.categorizer.categorize(line_str + " " + raw_vendor, amount)
                    
                    tx = Transaction(
                        date=iso_date,
                        raw_vendor=raw_vendor,
                        normalized_vendor=suggested_norm or raw_vendor,
                        amount=amount,
                        category=category,
                        is_recurring=True,
                        source_file=filename
                    )
                    transactions.append(tx)

        return transactions
