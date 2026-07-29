"""HTTP auth: login, me."""

from backend.app.config import get_settings


def test_login_ok(client):
    settings = get_settings()
    r = client.post(
        "/api/auth/login",
        json={"login": "pm", "password": settings.demo_pm_password},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["login"] == "pm"
    assert settings.cookie_name in client.cookies


def test_login_bad_password(client):
    r = client.post(
        "/api/auth/login",
        json={"login": "pm", "password": "wrong-password"},
    )
    assert r.status_code == 401


def test_me_with_cookie(login_pm):
    r = login_pm.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["login"] == "pm"


def test_me_without_cookie(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
