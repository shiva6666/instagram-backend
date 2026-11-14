from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_returns_ready_when_dependencies_are_available(
    monkeypatch,
) -> None:
    async def database_ready() -> bool:
        return True

    async def redis_ready() -> bool:
        return True

    monkeypatch.setattr("app.api.routes.health.check_database", database_ready)
    monkeypatch.setattr("app.api.routes.health.check_redis", redis_ready)

    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"postgres": "ok", "redis": "ok"},
    }


def test_readiness_check_returns_unavailable_when_a_dependency_is_down(
    monkeypatch,
) -> None:
    async def database_unavailable() -> bool:
        return False

    async def redis_ready() -> bool:
        return True

    monkeypatch.setattr("app.api.routes.health.check_database", database_unavailable)
    monkeypatch.setattr("app.api.routes.health.check_redis", redis_ready)

    response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"postgres": "unavailable", "redis": "ok"},
    }
