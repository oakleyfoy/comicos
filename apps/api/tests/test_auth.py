from fastapi.testclient import TestClient


def test_register_success(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret123"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_duplicate_register_fails(client: TestClient) -> None:
    payload = {"email": "user@example.com", "password": "supersecret123"}

    first_response = client.post("/auth/register", json=payload)
    second_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert second_response.json() == {"detail": "Email already registered"}


def test_login_success(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret123"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "supersecret123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data


def test_login_bad_password_fails(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret123"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_auth_me_with_token_works(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "supersecret123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "supersecret123"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_auth_me_without_token_fails(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
