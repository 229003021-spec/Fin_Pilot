import re
from typing import List, Union, BinaryIO
from pypdf import PdfReader
from finpilot.models import Transaction, TransactionCategory
from finpilot.ingestion.normalizer import SchemaNormalizer
from finpilot.ingestion.categorizer import HybridCategorizer


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
        if not text.strip():
            raise ValueError("No extractable text found in PDF. Scanned or image-only PDFs are not supported.")

        raw_lines = [l.strip() for l in text.split("\n") if l.strip()]

        # 1. Multi-line date stitcher (e.g., handles wrapped date lines like "Aug 01," + "2026 ...")
        lines = []
        i = 0
        date_partial_re = re.compile(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?$', re.IGNORECASE)
        year_start_re = re.compile(r'^(\d{4})\s+(.*)$')

        while i < len(raw_lines):
            line = raw_lines[i]
            if i + 1 < len(raw_lines) and date_partial_re.match(line):
                year_match = year_start_re.match(raw_lines[i+1])
                if year_match:
                    lines.append(f"{line} {raw_lines[i+1]}")
                    i += 2
                    continue
            lines.append(line)
            i += 1

        # 2. Regex patterns
        date_pattern = r'(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{0,4})'
        curr_pattern = r'([+-]?\$[\d,]+\.\d{2}\b|[+-]?[\d,]+\.\d{2}\b|\(\$?[\d,]+\.\d{2}\))'
        amt_token_pattern = r'([+-]?\$[\d,]+\.\d{2}\b|[+-]?[\d,]+\.\d{2}\b|\(\$?[\d,]+\.\d{2}\)|(?<=\s)-(?=\s|$))'

        line_regex = re.compile(f'^{date_pattern}\\s+(.*)', re.IGNORECASE)
        curr_regex = re.compile(curr_pattern)
        token_regex = re.compile(amt_token_pattern)

        transactions = []
        for line_str in lines:
            match = line_regex.match(line_str)
            if not match:
                continue

            raw_date_str = match.group(1)
            rest = match.group(2).strip()

            if "beginning balance" in rest.lower() or "ending balance" in rest.lower():
                continue

            curr_matches = list(curr_regex.finditer(rest))
            if not curr_matches:
                continue

            first_curr_idx = curr_matches[0].start()
            prefix_before_curr = rest[:first_curr_idx]
            dash_match = re.search(r'\s-\s*$', prefix_before_curr)
            if dash_match:
                amt_start_idx = dash_match.start()
            else:
                amt_start_idx = first_curr_idx

            vendor_part = rest[:amt_start_idx].strip()
            amount_block = rest[amt_start_idx:].strip()

            tokens = [m.group(1).strip() for m in token_regex.finditer(amount_block)]
            if not tokens:
                continue

            amount = 0.0
            # Check 2-column withdrawal/deposit format (e.g., Description [Withdrawal] [Deposit] [Balance])
            if len(tokens) >= 3 and (tokens[-1].startswith("$") or re.search(r'\d+\.\d{2}$', tokens[-1])):
                wd_str = tokens[-3]
                dp_str = tokens[-2]

                if wd_str != "-" and wd_str != "$0.00" and wd_str != "0.00":
                    amount = -abs(SchemaNormalizer.normalize_amount(wd_str))
                elif dp_str != "-" and dp_str != "$0.00" and dp_str != "0.00":
                    amount = abs(SchemaNormalizer.normalize_amount(dp_str))
            elif len(tokens) == 2 and (tokens[-1].startswith("$") or re.search(r'\d+\.\d{2}$', tokens[-1])):
                amt_str = tokens[0]
                if amt_str != "-":
                    amount = SchemaNormalizer.normalize_amount(amt_str)
            else:
                raw_amt_str = tokens[0]
                if raw_amt_str != "-":
                    amount = SchemaNormalizer.normalize_amount(raw_amt_str)

            if amount == 0.0:
                continue

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

        return transactions
