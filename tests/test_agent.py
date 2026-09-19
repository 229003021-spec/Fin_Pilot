import pytest
from finpilot.db import FinPilotDB
from finpilot.agent.query_router import NLQueryRouter
from finpilot.agent.brief_generator import MonthlyBriefGenerator
from finpilot.agent.privacy import PrivacyMasker
from finpilot.demo_data import seed_demo_database


@pytest.fixture
def populated_db():
    db = FinPilotDB(":memory:")
    seed_demo_database(db)
    return db


def test_privacy_masker():
    masked = PrivacyMasker.mask_text("My credit card is 1234-5678-9012-3456 and SSN is 123-45-6789")
    assert "1234-5678" not in masked
    assert "123-45" not in masked
    assert "3456" in masked


def test_nl_query_router_spending(populated_db):
    router = NLQueryRouter(populated_db)
    res = router.process_query("Where did I spend the most this month?")
    assert "spent the most" in res['answer'].lower()
    assert res['data_table'] is not None


def test_nl_query_router_subscriptions(populated_db):
    router = NLQueryRouter(populated_db)
    res = router.process_query("Which subscriptions am I paying for?")
    assert "recurring subscription" in res['answer'].lower() or "subscriptions" in res['answer'].lower()


def test_nl_query_router_increases(populated_db):
    router = NLQueryRouter(populated_db)
    res = router.process_query("What expenses increased compared to last month?")
    assert "increase" in res['answer'].lower() or "dining out" in res['answer'].lower()


def test_monthly_brief_generator(populated_db):
    gen = MonthlyBriefGenerator(populated_db)
    brief = gen.generate_brief()
    assert brief['status'] == "SUCCESS"
    assert brief['total_income'] > 0
    assert brief['total_expenses'] > 0
    assert len(brief['next_steps']) > 0
