import os
import io
import pandas as pd
from typing import List, Dict, Any, Union, BinaryIO, Optional
from pydantic import BaseModel
from pypdf import PdfReader
from finpilot.models import Transaction
from finpilot.ingestion.csv_parser import CSVStatementParser
from finpilot.ingestion.json_parser import JSONStatementParser
from finpilot.ingestion.pdf_parser import PDFStatementParser
from finpilot.ingestion.ai_agent_parser import AIAgentParser
from finpilot.analytics.subscriptions import SubscriptionTracker
from finpilot.analytics.anomalies import AnomalyDetector


class DocumentStats(BaseModel):
    filename: str
    file_format: str
    total_transactions: int
    date_range_start: str
    date_range_end: str
    gross_income: float
    gross_expenses: float
    net_cash_flow: float
    top_category: str
    top_category_amount: float
    top_vendor: str
    top_vendor_amount: float
    subscriptions_detected: int
    anomalies_detected: int
    parsing_confidence_pct: float
    status: str
    message: str


class BackgroundDocumentProcessor:
    """
    Background Document Processing Engine.
    Invisibly ingests uploaded documents (CSV, JSON, PDF), normalizes schemas,
    and computes document statistics without clogging the main UI view.
    """

    def __init__(self):
        self.csv_parser = CSVStatementParser()
        self.json_parser = JSONStatementParser()
        self.pdf_parser = PDFStatementParser()
        self.ai_agent = AIAgentParser()

    def process_document(self, file_source: Union[str, BinaryIO, bytes], filename: str) -> Dict[str, Any]:
        """
        Parses document in the background and computes summary statistics.
        Returns:
            {
                "transactions": List[Transaction],
                "stats": DocumentStats
            }
        """
        ext = os.path.splitext(filename)[1].lower()
        file_format = ext.replace(".", "").upper() if ext else "UNKNOWN"

        transactions: List[Transaction] = []

        try:
            if ext == ".csv":
                transactions = self.csv_parser.parse(file_source, filename=filename)
            elif ext == ".json":
                transactions = self.json_parser.parse(file_source, filename=filename)
            elif ext == ".pdf":
                transactions = self.pdf_parser.parse(file_source, filename=filename)
            else:
                # Fallback format auto-detection
                content = file_source.read() if hasattr(file_source, 'read') else file_source
                if hasattr(file_source, 'seek'):
                    file_source.seek(0)
                
                try:
                    transactions = self.csv_parser.parse(io.BytesIO(content) if isinstance(content, bytes) else content, filename=filename)
                    file_format = "CSV"
                except Exception:
                    try:
                        transactions = self.pdf_parser.parse(io.BytesIO(content) if isinstance(content, bytes) else content, filename=filename)
                        file_format = "PDF"
                    except Exception:
                        transactions = []
        except Exception:
            transactions = []

        # If primary parsing produced 0 transactions, trigger AI Agent fallback ingestion
        if not transactions:
            try:
                raw_text = ""
                if hasattr(file_source, 'seek'):
                    file_source.seek(0)

                if ext == ".pdf":
                    pdf_stream = io.BytesIO(file_source) if isinstance(file_source, bytes) else file_source
                    reader = PdfReader(pdf_stream)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            raw_text += t + "\n"
                else:
                    if hasattr(file_source, 'read'):
                        content = file_source.read()
                        if isinstance(content, bytes):
                            raw_text = content.decode('utf-8', errors='ignore')
                        else:
                            raw_text = str(content)
                    elif isinstance(file_source, bytes):
                        raw_text = file_source.decode('utf-8', errors='ignore')
                    elif isinstance(file_source, str):
                        if os.path.exists(file_source):
                            with open(file_source, 'r', encoding='utf-8', errors='ignore') as f:
                                raw_text = f.read()
                        else:
                            raw_text = file_source

                if raw_text:
                    transactions = self.ai_agent.parse_raw_text(raw_text, filename=filename)
            except Exception:
                transactions = []

        if not transactions:
            return {
                "transactions": [],
                "stats": DocumentStats(
                    filename=filename,
                    file_format=file_format,
                    total_transactions=0,
                    date_range_start="N/A",
                    date_range_end="N/A",
                    gross_income=0.0,
                    gross_expenses=0.0,
                    net_cash_flow=0.0,
                    top_category="N/A",
                    top_category_amount=0.0,
                    top_vendor="N/A",
                    top_vendor_amount=0.0,
                    subscriptions_detected=0,
                    anomalies_detected=0,
                    parsing_confidence_pct=0.0,
                    status="WARNING",
                    message="No valid transaction rows identified."
                )
            }

        # Calculate statistics deterministically
        df = pd.DataFrame([t.model_dump() for t in transactions])
        df['abs_amount'] = df['amount'].abs()
        df['dt'] = pd.to_datetime(df['date'])

        date_start = df['date'].min()
        date_end = df['date'].max()

        gross_income = float(df[df['amount'] > 0]['amount'].sum()) if not df[df['amount'] > 0].empty else 0.0
        gross_expenses = float(df[df['amount'] < 0]['abs_amount'].sum()) if not df[df['amount'] < 0].empty else 0.0
        net_cash_flow = gross_income - gross_expenses

        # Top spending category
        expenses_df = df[df['amount'] < 0]
        if not expenses_df.empty:
            cat_sums = expenses_df.groupby('category')['abs_amount'].sum()
            top_category = str(cat_sums.idxmax())
            top_category_amt = float(cat_sums.max())

            vendor_sums = expenses_df.groupby('normalized_vendor')['abs_amount'].sum()
            top_vendor = str(vendor_sums.idxmax())
            top_vendor_amt = float(vendor_sums.max())
        else:
            top_category = "None"
            top_category_amt = 0.0
            top_vendor = "None"
            top_vendor_amt = 0.0

        # Pattern analytics
        subs = SubscriptionTracker.detect_subscriptions(df)
        anomalies = AnomalyDetector.detect_anomalies(df)

        # Confidence Score calculation
        valid_dates = df['date'].str.match(r'^\d{4}-\d{2}-\d{2}$').sum()
        valid_amounts = (df['amount'] != 0).sum()
        confidence = min(100.0, round(((valid_dates + valid_amounts) / (2 * len(df))) * 100.0, 1))

        stats = DocumentStats(
            filename=filename,
            file_format=file_format,
            total_transactions=len(transactions),
            date_range_start=str(date_start),
            date_range_end=str(date_end),
            gross_income=round(gross_income, 2),
            gross_expenses=round(gross_expenses, 2),
            net_cash_flow=round(net_cash_flow, 2),
            top_category=top_category,
            top_category_amount=round(top_category_amt, 2),
            top_vendor=top_vendor,
            top_vendor_amount=round(top_vendor_amt, 2),
            subscriptions_detected=len(subs),
            anomalies_detected=len(anomalies),
            parsing_confidence_pct=confidence,
            status="SUCCESS",
            message=f"Successfully processed {len(transactions)} transaction records."
        )

        return {
            "transactions": transactions,
            "stats": stats
        }
