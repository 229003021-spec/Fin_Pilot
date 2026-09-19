import re


class PrivacyMasker:
    """Masks sensitive account numbers, SSNs, and credit cards from agent outputs."""

    @staticmethod
    def mask_text(text: str) -> str:
        if not text:
            return ""

        # Mask 16-digit credit card numbers: 1234-5678-9012-3456 -> ****-****-****-3456
        text = re.sub(r'\b(?:\d[ -]*?){13,16}\b', lambda m: '****-****-****-' + m.group(0).replace('-', '').replace(' ', '')[-4:], text)

        # Mask Account numbers like ACCT#123456789 -> ACCT#****6789
        text = re.sub(r'\b(ACCT|ACCOUNT|CARD|NUM|NO)[\s#:]*(\d{6,12})\b', r'\1#****\2', text, flags=re.IGNORECASE)

        # Mask SSN: 123-45-6789 -> ***-**-6789
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '***-**-****', text)

        return text
