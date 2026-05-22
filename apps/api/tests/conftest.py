import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("DEBUG_RUNTIME", "false")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-0123456789abcdef")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "")

    get_settings.cache_clear()
    get_engine.cache_clear()
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

    with TestClient(app) as test_client:
        yield test_client

    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def session() -> Session:
    with Session(get_engine()) as db_session:
        yield db_session
