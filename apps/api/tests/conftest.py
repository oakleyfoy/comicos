import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.core.config import get_settings
from app.db.session import get_engine
from app.main import app
from app.tasks import queue as rq_queue_module


@pytest.fixture(autouse=True)
def fake_rq_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeStrictRedis:
    """Route all default Redis/RQ traffic to one in-memory broker per test."""

    fake = fakeredis.FakeStrictRedis()
    cached_get_redis_connection = rq_queue_module.get_redis_connection
    cache_clear = getattr(cached_get_redis_connection, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
    monkeypatch.setattr(rq_queue_module.Redis, "from_url", lambda *args, **kwargs: fake)
    yield fake
    cache_clear = getattr(cached_get_redis_connection, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


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
    monkeypatch.setenv("COVER_IMAGES_STORAGE_ROOT", str(tmp_path / "cover-images"))
    monkeypatch.setenv("SCAN_INGESTION_STORAGE_ROOT", str(tmp_path / "scan-ingestion"))
    monkeypatch.setenv("SCAN_NORMALIZATION_STORAGE_ROOT", str(tmp_path / "scan-normalization"))
    monkeypatch.setenv("SCAN_BOUNDARY_STORAGE_ROOT", str(tmp_path / "scan-boundary"))
    monkeypatch.setenv("SCAN_OCR_STORAGE_ROOT", str(tmp_path / "scan-ocr"))
    monkeypatch.setenv("SCAN_RECONCILIATION_STORAGE_ROOT", str(tmp_path / "scan-reconciliation"))
    monkeypatch.setenv("SCAN_DEFECTS_STORAGE_ROOT", str(tmp_path / "scan-defects"))
    monkeypatch.setenv("SCAN_SPINE_TICKS_STORAGE_ROOT", str(tmp_path / "scan-spine-ticks"))
    monkeypatch.setenv("SCAN_CORNER_EDGES_STORAGE_ROOT", str(tmp_path / "scan-corner-edges"))
    monkeypatch.setenv("SCAN_SURFACE_DEFECTS_STORAGE_ROOT", str(tmp_path / "scan-surface-defects"))
    monkeypatch.setenv("SCAN_STRUCTURAL_DAMAGE_STORAGE_ROOT", str(tmp_path / "scan-structural-damage"))
    monkeypatch.setenv("SCAN_DEFECT_AGGREGATION_STORAGE_ROOT", str(tmp_path / "scan-defect-aggregation"))
    monkeypatch.setenv("SCAN_GRADING_ASSISTANCE_STORAGE_ROOT", str(tmp_path / "scan-grading-assistance"))
    monkeypatch.setenv("SCAN_VISUAL_EVIDENCE_STORAGE_ROOT", str(tmp_path / "scan-visual-evidence"))
    monkeypatch.setenv("SCAN_REVIEW_STORAGE_ROOT", str(tmp_path / "scan-review"))
    monkeypatch.setenv("SCAN_HISTORICAL_COMPARISON_STORAGE_ROOT", str(tmp_path / "scan-historical-comparison"))
    monkeypatch.setenv("SCAN_AUTHENTICATION_STORAGE_ROOT", str(tmp_path / "scan-authentication"))
    monkeypatch.setenv("LISTING_EXPORTS_STORAGE_ROOT", str(tmp_path / "listing-exports"))
    monkeypatch.setenv("OPERATIONAL_REPORTS_STORAGE_ROOT", str(tmp_path / "operational-reports"))

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
