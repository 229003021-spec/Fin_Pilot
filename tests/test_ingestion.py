import io
import pytest
from finpilot.ingestion.normalizer import SchemaNormalizer
from finpilot.ingestion.categorizer import HybridCategorizer
from finpilot.ingestion.csv_parser import CSVStatementParser
from finpilot.ingestion.json_parser import JSONStatementParser
from finpilot.models import TransactionCategory


def test_schema_normalizer_date():
    assert SchemaNormalizer.normalize_date("2026-03-15") == "2026-03-15"
    assert SchemaNormalizer.normalize_date("03/15/2026") == "2026-03-15"
    assert SchemaNormalizer.normalize_date("15-Mar-2026") == "2026-03-15"


def test_schema_normalizer_vendor():
    raw, norm = SchemaNormalizer.clean_vendor("SQUARE * CAFE #1042 SEATTLE WA")
    assert raw == "SQUARE * CAFE #1042 SEATTLE WA"
    assert "Cafe" in norm or "Square" in norm


def test_schema_normalizer_amount():
    assert SchemaNormalizer.normalize_amount("$100.50") == 100.50
    assert SchemaNormalizer.normalize_amount("(50.25)") == -50.25
    assert SchemaNormalizer.normalize_amount("100.00", is_debit=True) == -100.00
    assert SchemaNormalizer.normalize_amount("-100.00", is_credit=True) == 100.00


def test_hybrid_categorizer():
    cat = HybridCategorizer()
    c1, _ = cat.categorize("SQUARE * CAFE BAKERY", amount=-15.00)
    assert c1 == TransactionCategory.DINING_OUT.value

    c2, _ = cat.categorize("NETFLIX DIGITAL SUB", amount=-19.99)
    assert c2 == TransactionCategory.SUBSCRIPTIONS.value

    c3, _ = cat.categorize("CONED ELECTRIC BILL NY", amount=-120.00)
    assert c3 == TransactionCategory.UTILITIES.value


def test_csv_parser():
    csv_content = """Date,Description,Amount,Category
2026-03-01,Tech Corp Salary,4500.00,Income
2026-03-02,Avalon Apartments,-1800.00,Housing
2026-03-10,Netflix,-19.99,Subscriptions
"""
    parser = CSVStatementParser()
    txs = parser.parse(io.StringIO(csv_content), filename="test.csv")
    assert len(txs) == 3
    assert txs[0].amount == 4500.00
    assert txs[1].category == "Housing"
    assert txs[2].amount == -19.99


def test_json_parser():
    json_str = """{
        "Transaction": [
            {"date": "2026-03-01", "raw_vendor": "Tech Corp Salary", "amount": 4500.00, "category": "Income"},
            {"date": "2026-03-10", "raw_vendor": "Netflix", "amount": -19.99, "category": "Subscriptions"}
        ]
    }"""
    parser = JSONStatementParser()
    txs = parser.parse(json_str, filename="test.json")
    assert len(txs) == 2
    assert txs[0].amount == 4500.00
    assert txs[1].category == "Subscriptions"


def test_pdf_parser_demo_statement():
    import os
    from finpilot.ingestion.pdf_parser import PDFStatementParser
    pdf_path = "demo_bank_statement.pdf"
    if os.path.exists(pdf_path):
        parser = PDFStatementParser()
        txs = parser.parse(pdf_path, filename=pdf_path)
        assert len(txs) == 15
        assert txs[0].amount == 2500.00
        assert txs[1].amount == -1450.00


def test_background_document_processor():
    import os
    from finpilot.ingestion.processor import BackgroundDocumentProcessor
    pdf_path = "demo_bank_statement.pdf"
    if os.path.exists(pdf_path):
        proc = BackgroundDocumentProcessor()
        res = proc.process_document(pdf_path, filename=pdf_path)
        stats = res["stats"]
        assert stats.status == "SUCCESS"
        assert stats.total_transactions == 15
        assert stats.gross_income == 5320.00
        assert stats.parsing_confidence_pct > 90.0


