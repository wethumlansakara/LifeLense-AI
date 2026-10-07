import pytest
from app.config import settings

@pytest.fixture(autouse=True)
def test_rate_budget(monkeypatch):
    # Functional tests share one synthetic client IP; dedicated limiter tests set their own budgets.
    monkeypatch.setattr(settings,'auth_rate_limit',1000)
    monkeypatch.setattr(settings,'api_rate_limit',10000)
    monkeypatch.setattr(settings,'analysis_rate_limit',1000)
