from fastapi.testclient import TestClient


def test_root_get_returns_ok(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "comic-os-api"}


def test_root_head_returns_ok(client: TestClient) -> None:
    response = client.head("/")

    assert response.status_code == 200


def test_healthz_get_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_healthz_head_returns_ok(client: TestClient) -> None:
    response = client.head("/healthz")

    assert response.status_code == 200


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_db_returns_connection_status(client: TestClient) -> None:
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "database": "connected"}


def test_health_redis_returns_connection_status(client: TestClient, monkeypatch) -> None:
    class DummyRedis:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr("app.tasks.queue.get_redis_connection", lambda: DummyRedis())

    response = client.get("/health/redis")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "redis": "connected"}


def test_health_worker_returns_visibility(client: TestClient, monkeypatch) -> None:
    class DummyWorker:
        def __init__(self, name: str) -> None:
            self.name = name

    monkeypatch.setattr("app.tasks.queue.get_redis_connection", lambda: object())
    monkeypatch.setattr(
        "rq.Worker.all",
        lambda connection: [DummyWorker("worker-1"), DummyWorker("worker-2")],
    )

    response = client.get("/health/worker")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "worker_count": 2,
        "workers": ["worker-1", "worker-2"],
        "queues": ["ai_parse", "gmail_sync"],
    }
