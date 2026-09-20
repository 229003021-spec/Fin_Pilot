import re
from typing import List, Union, BinaryIO
from pypdf import PdfReader
from finpilot.models import Transaction, TransactionCategory
from finpilot.ingestion.normalizer import SchemaNormalizer
from finpilot.ingestion.categorizer import HybridCategorizer


# Standard categories map for pdf text extraction
KNOWN_CATEGORIES_MAP = {
    "income": TransactionCategory.INCOME.value,
    "housing": TransactionCategory.HOUSING.value,
    "groceries": TransactionCategory.GROCERIES.value,
    "utilities": TransactionCategory.UTILITIES.value,
    "dining": TransactionCategory.DINING_OUT.value,
    "dining out": TransactionCategory.DINING_OUT.value,
    "transportation": TransactionCategory.TRANSPORTATION.value,
    "fuel": TransactionCategory.TRANSPORTATION.value,
    "subscriptions": TransactionCategory.SUBSCRIPTIONS.value,
    "entertainment": TransactionCategory.SUBSCRIPTIONS.value,
    "shopping": TransactionCategory.SHOPPING.value,
    "insurance": TransactionCategory.GENERAL.value,
    "transfer": TransactionCategory.GENERAL.value,
    "bank fees": TransactionCategory.GENERAL.value,
    "fees": TransactionCategory.GENERAL.value,
}


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
            raise ValueError("No extractable text found in PDF. Scanned or image-only PDFs are not supported.")

        return self._extract_transactions_from_text(full_text, filename)

    def _extract_transactions_from_text(self, text: str, filename: str) -> List[Transaction]:
        lines = text.split("\n")
        transactions = []

        # Flexible date regex matching: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, or Mon DD YYYY
        date_pattern = r'(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{0,4})'
        # Amount pattern matching signed amounts +$2,500.00, -$1,450.00, (100.00), or 100.00
        amount_pattern = r'([+-]?\$?\s*[\d,]+\.\d{2}\b|\(\$?[\d,]+\.\d{2}\))'

        line_regex = re.compile(f'^{date_pattern}\\s+(.*)', re.IGNORECASE)
        amt_regex = re.compile(amount_pattern)

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            match = line_regex.match(line_str)
            if match:
                raw_date_str = match.group(1)
                rest = match.group(2).strip()

                amts = list(amt_regex.finditer(rest))
                if amts:
                    # The first amount is the transaction amount (second amount, if present, is running balance)
                    raw_amt_str = amts[0].group(1)
                    vendor_part = rest[:amts[0].start()].strip()

                    # Extract inline category if present at the end of vendor_part
                    explicit_category = None
                    words = vendor_part.split()
                    if len(words) > 1:
                        last_two = " ".join(words[-2:]).lower()
                        last_one = words[-1].lower()

                        if last_two in KNOWN_CATEGORIES_MAP:
                            explicit_category = KNOWN_CATEGORIES_MAP[last_two]
                            vendor_part = " ".join(words[:-2])
                        elif last_one in KNOWN_CATEGORIES_MAP:
                            explicit_category = KNOWN_CATEGORIES_MAP[last_one]
                            vendor_part = " ".join(words[:-1])

                    iso_date = SchemaNormalizer.normalize_date(raw_date_str)
                    raw_vendor, norm_vendor = SchemaNormalizer.clean_vendor(vendor_part)
                    amount = SchemaNormalizer.normalize_amount(raw_amt_str)

                    # Deduce or set category
                    if explicit_category:
                        category = explicit_category
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
                    continue

            # Check utility bill single total pattern (e.g. "Total Amount Due: $145.50")
            if ("total" in line_str.lower() or "amount due" in line_str.lower()) and ("balance" not in line_str.lower()):
                amt_match = amt_regex.search(line_str)
                if amt_match:
                    amt_str = amt_match.group(1)
                    amount = SchemaNormalizer.normalize_amount(amt_str)
                    if amount > 0:
                        amount = -amount  # expenses

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
