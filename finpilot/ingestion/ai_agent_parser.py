import re
from typing import List, Dict, Any, Union, BinaryIO, Optional
from datetime import datetime
from finpilot.models import Transaction, TransactionCategory
from finpilot.ingestion.normalizer import SchemaNormalizer
from finpilot.ingestion.categorizer import HybridCategorizer


class AIAgentParser:
    """
    Intelligent AI Statement Ingestion Agent.
    When standard parsers fail or encounter unusual file formats, the AI Agent reads raw file content
    carefully, extracts transaction entities (Date, Merchant/Description, Amount, Category),
    and converts them into standard FinPilot Transaction objects.
    """

    def __init__(self, categorizer: Optional[HybridCategorizer] = None):
        self.categorizer = categorizer or HybridCategorizer()

    def parse_raw_text(self, text: str, filename: str = "statement") -> List[Transaction]:
        if not text or not text.strip():
            return []

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            return []

        transactions: List[Transaction] = []

        # Comprehensive date patterns across global bank formats:
        # 1. ISO / Standard: 2026-08-01, 2026/08/01, 08/01/2026, 1/8/2026, 08-01-2026, 15-Mar-2026, Aug 01, 2026
        # 2. Short date: Aug 01, 08/01, 1-Aug
        date_pattern = r'(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{2,4})?|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{2,4})?)'
        
        # Money amount pattern: $1,250.00, +$2500, -$142.35, - $142.35, (142.35), 142.35, -50.00
        amt_pattern = r'([+-]?\s*\$?\s*[\d,]+\.\d{2}\b|\(\$?[\d,]+\.\d{2}\)|[+-]?\s*\$?\s*[\d,]+\b)'

        date_regex = re.compile(date_pattern, re.IGNORECASE)
        amt_regex = re.compile(amt_pattern)

        # Pre-pass: stitch lines if date is wrapped across consecutive lines
        stitched_lines = []
        i = 0
        date_only_re = re.compile(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?$', re.IGNORECASE)
        year_start_re = re.compile(r'^(\d{2,4})\s+(.*)$')

        while i < len(lines):
            l = lines[i]
            if i + 1 < len(lines) and date_only_re.match(l):
                ym = year_start_re.match(lines[i+1])
                if ym:
                    stitched_lines.append(f"{l} {lines[i+1]}")
                    i += 2
                    continue
            stitched_lines.append(l)
            i += 1

        for line_str in stitched_lines:
            # Skip summary lines
            lower_line = line_str.lower()
            if any(k in lower_line for k in ["starting balance", "beginning balance", "ending balance", "total credits", "total debits", "account number", "statement period", "customer id", "page 1 of"]):
                continue

            date_match = date_regex.search(line_str)
            if not date_match:
                continue

            raw_date_str = date_match.group(1)
            # Remove date string from line to find description and amount
            start, end = date_match.span(1)
            remaining_line = (line_str[:start] + " " + line_str[end:]).strip()

            amt_matches = list(amt_regex.finditer(remaining_line))
            if not amt_matches:
                continue

            # Check 2-column withdrawal/deposit or single amount
            tokens = [m.group(1).strip() for m in amt_matches]
            first_amt_idx = amt_matches[0].start()
            vendor_part = remaining_line[:first_amt_idx].strip()

            # Clean out non-vendor metadata prefix/suffix symbols
            vendor_part = re.sub(r'^(POS|ACH|PAYPAL\*|SQ\*|TST\*|POS PURCHASE|DIRECT DEBIT|AUTO-PAY)\s+', '', vendor_part, flags=re.IGNORECASE).strip()
            vendor_part = vendor_part.rstrip("- :;,").strip()
            if not vendor_part:
                vendor_part = "Bank Transaction"

            amount = 0.0
            if len(tokens) >= 3 and (tokens[-1].startswith("$") or re.match(r'^\d+\.\d{2}$', tokens[-1])):
                # Format: Vendor [Withdrawal] [Deposit] [Balance]
                wd_str = tokens[-3]
                dp_str = tokens[-2]

                if wd_str != "-" and wd_str != "$0.00" and wd_str != "0.00":
                    amount = -abs(SchemaNormalizer.normalize_amount(wd_str))
                elif dp_str != "-" and dp_str != "$0.00" and dp_str != "0.00":
                    amount = abs(SchemaNormalizer.normalize_amount(dp_str))
            else:
                raw_amt = tokens[0]
                if raw_amt != "-":
                    amount = SchemaNormalizer.normalize_amount(raw_amt)

            if amount == 0.0:
                continue

            iso_date = SchemaNormalizer.normalize_date(raw_date_str)
            raw_vendor, norm_vendor = SchemaNormalizer.clean_vendor(vendor_part)
            category, suggested_norm = self.categorizer.categorize(raw_vendor, amount)

            tx = Transaction(
                date=iso_date,
                raw_vendor=raw_vendor,
                normalized_vendor=suggested_norm or norm_vendor,
                amount=amount,
                category=category,
                is_recurring=False,
                source_file=filename
            )
            transactions.append(tx)

        return transactions
