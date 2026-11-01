"""The follow-up link opens the web app when FRONTEND_URL is set, and the API endpoint otherwise."""
from api.tokens import format_follow_up_url


def test_link_points_at_the_api_by_default(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000/")
    assert format_follow_up_url("tok123") == "http://localhost:8000/api/follow-up/tok123"


def test_link_points_at_the_web_app_when_configured(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173/")
    assert format_follow_up_url("tok123") == "http://localhost:5173/follow-up/tok123"


def test_blank_frontend_url_is_ignored(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "  ")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")
    assert format_follow_up_url("t").startswith("http://localhost:8000/api/follow-up/")
