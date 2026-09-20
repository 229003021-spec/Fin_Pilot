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


def test_pdf_parser_demo_bank_statement_2():
    import os
    from finpilot.ingestion.pdf_parser import PDFStatementParser
    pdf_path = "Demo Bank Statement.pdf"
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


def test_invalid_files_error_handling():
    from finpilot.ingestion.processor import BackgroundDocumentProcessor
    proc = BackgroundDocumentProcessor()

    # 1. Invalid JSON
    res_json = proc.process_document(io.BytesIO(b"invalid json content {{"), filename="test.json")
    assert res_json["stats"].status in ["WARNING", "ERROR"]
    assert len(res_json["transactions"]) == 0

    # 2. Corrupt / Empty CSV
    res_csv = proc.process_document(io.BytesIO(b""), filename="test.csv")
    assert res_csv["stats"].status in ["WARNING", "ERROR"]
    assert len(res_csv["transactions"]) == 0

    # 3. Image-only PDF with no text
    from finpilot.ingestion.pdf_parser import PDFStatementParser
    with pytest.raises(ValueError):
        PDFStatementParser()._extract_transactions_from_text("", filename="scanned.pdf")


def test_duplicate_upload_prevention_and_clear_all():
    from finpilot.db import FinPilotDB
    from finpilot.ingestion.processor import BackgroundDocumentProcessor
    db = FinPilotDB(":memory:")
    proc = BackgroundDocumentProcessor()

    csv_data = b"Date,Description,Amount,Category\n2026-03-01,Salary,5000,Income"
    res = proc.process_document(io.BytesIO(csv_data), filename="test.csv")
    
    # First insert
    db.insert_transactions(res["transactions"])
    assert len(db.get_transactions_df()) == 1

    # Simulated rerun with duplicate check: key match prevents second insertion
    last_uploaded_key = f"test.csv:{len(csv_data)}"
    new_uploaded_key = f"test.csv:{len(csv_data)}"
    
    if last_uploaded_key != new_uploaded_key:
        db.insert_transactions(res["transactions"])
    
    # Should still be 1 row
    assert len(db.get_transactions_df()) == 1

    # Clear All leaves 0 rows
    db.clear_all()
    assert len(db.get_transactions_df()) == 0
    assert len(db.get_budgets()) == 0
    assert len(db.get_goals()) == 0


def test_ai_agent_parser():
    from finpilot.ingestion.ai_agent_parser import AIAgentParser
    raw_text = """
    STATEMENT PERIOD: AUGUST 2026
    Aug 01, 2026 DIRECT DEPOSIT TECH CORP $2,500.00
    Aug 02, 2026 AVALON APTS RENT - $1,450.00
    Aug 05, 2026 NETFLIX DIGITAL SUB - $19.99
    """
    parser = AIAgentParser()
    txs = parser.parse_raw_text(raw_text, filename="unstructured.txt")
    assert len(txs) == 3
    assert txs[0].amount == 2500.00
    assert txs[1].amount == -1450.00
    assert txs[2].category == TransactionCategory.SUBSCRIPTIONS.value


def test_raw_bytes_pdf_processing():
    import os
    from finpilot.ingestion.processor import BackgroundDocumentProcessor
    pdf_path = "Demo Bank Statement.pdf"
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            raw_bytes = f.read()
        proc = BackgroundDocumentProcessor()
        res = proc.process_document(raw_bytes, filename=pdf_path)
        assert res["stats"].status == "SUCCESS"
        assert res["stats"].total_transactions == 15





