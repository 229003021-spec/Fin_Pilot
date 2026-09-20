import re
from datetime import datetime
from typing import Optional, Tuple, Any


class SchemaNormalizer:
    """Standardizes disparate transaction records into unified FinPilot schema."""

    @staticmethod
    def normalize_date(date_str: str) -> str:
        """Standardizes raw date strings into ISO format YYYY-MM-DD."""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")
        
        date_str = str(date_str).strip()
        
        # Standard formats to attempt
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d-%b-%Y",
            "%m-%d-%Y",
            "%d/%m/%y",
            "%m/%d/%y"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
                
        # Regex extraction fallback if date string contains extra text
        match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
        if match:
            y, m, d = match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            
        match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', date_str)
        if match:
            m, d, y = match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def clean_vendor(raw_vendor: str) -> Tuple[str, str]:
        """
        Cleans raw vendor string and produces a normalized vendor name.
        Example: 'SQUARE * CAFE #1042 SEATTLE WA' -> ('SQUARE * CAFE #1042 SEATTLE WA', 'Square Cafe')
        """
        if not raw_vendor:
            return "UNKNOWN VENDOR", "Unknown Vendor"
            
        raw = str(raw_vendor).strip()
        
        # Strip trailing transaction reference numbers, store codes, location IDs
        clean = raw
        
        # Remove common payment processor prefixes
        clean = re.sub(r'^(SQUARE\s*\*|TST\*\s*|SQ\s*\*|PAYPAL\s*\*|POS\s+|ACH\s+DEBIT\s+|WITHDRAWAL\s+)', '', clean, flags=re.IGNORECASE)
        
        # Remove store/ref numbers like #1234, *123, 04921
        clean = re.sub(r'#\d+|\*\d+|\b\d{4,}\b', '', clean)
        
        # Remove trailing city/state codes (e.g. SEATTLE WA, NY, CA)
        clean = re.sub(r'\b[A-Z]{2}\b$', '', clean)
        
        # Clean extra symbols and whitespace
        clean = re.sub(r'[\*\-_]+', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        if not clean:
            clean = raw
            
        # Capitalize nicely
        normalized = clean.title()
        return raw, normalized

    @staticmethod
    def normalize_amount(val: Any, is_debit: Optional[bool] = None, is_credit: Optional[bool] = None) -> float:
        """
        Ensures negative amount for expenses, positive for income.
        """
        if val is None or val == '':
            return 0.0
            
        if isinstance(val, (int, float)):
            num = float(val)
        else:
            # Clean string
            s = str(val).replace('$', '').replace(',', '').replace(' ', '').strip()
            # Handle parenthesized negative amounts: (100.00) -> -100.00
            if s.startswith('(') and s.endswith(')'):
                s = '-' + s[1:-1]
            try:
                num = float(s)
            except ValueError:
                num = 0.0

        if is_debit is True and num > 0:
            num = -num
        elif is_credit is True and num < 0:
            num = abs(num)
            
        return num
