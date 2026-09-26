import asyncio
import os
import subprocess
import sys

import pytest

from app import security


class DummyApp:
    def __init__(self, status=200):
        self.status = status
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        await send({"type": "http.response.start", "status": self.status, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def request(app, *, path="/api/briefing", headers=None, body=b""):
    async def run():
        sent = []
        scope = {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
            "client": ("127.0.0.1", 12345),
            "state": {},
        }
        received = False

        async def receive():
            nonlocal received
            if received:
                return {"type": "http.request", "body": b"", "more_body": False}
            received = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)
        return scope, sent

    return asyncio.run(run())


def response_status(sent):
    return next(item["status"] for item in sent if item["type"] == "http.response.start")


def test_memory_quota_enforces_weighted_hourly_and_daily_caps():
    limiter = security.MemoryQuota(hourly=8, daily=10)
    limiter.consume("user-a", 2, now=100_000)
    limiter.consume("user-a", 6, now=100_001)
    with pytest.raises(security.QuotaExceeded):
        limiter.consume("user-a", 1, now=100_002)
    with pytest.raises(security.QuotaExceeded):
        limiter.consume("user-a", 3, now=103_600)
    limiter.consume("user-a", 2, now=103_602)
    with pytest.raises(security.QuotaExceeded):
        limiter.consume("user-a", 1, now=103_603)


def test_hourly_window_does_not_reset_at_clock_boundary():
    limiter = security.MemoryQuota(hourly=4, daily=20)
    limiter.consume("user-a", 4, now=3599)
    with pytest.raises(security.QuotaExceeded):
        limiter.consume("user-a", 1, now=3600)
    limiter.consume("user-a", 1, now=7199)


def test_large_content_length_is_rejected_before_downstream_parser(monkeypatch):
    monkeypatch.setattr(security, "AUTH_MODE", "development")
    monkeypatch.setattr(security, "MAX_REQUEST_BYTES", 10)
    downstream = DummyApp()
    _, sent = request(
        security.RequestSecurityMiddleware(downstream),
        headers={
            "content-type": "multipart/form-data; boundary=x",
            "content-length": "11",
        },
    )
    assert response_status(sent) == 413
    assert not downstream.called


def test_firebase_mode_rejects_missing_authorization_before_body_read(monkeypatch):
    monkeypatch.setattr(security, "AUTH_MODE", "firebase")
    monkeypatch.setattr(security, "APP_CHECK_REQUIRED", False)
    monkeypatch.setattr(security, "MAX_REQUEST_BYTES", 1024)
    downstream = DummyApp()
    _, sent = request(
        security.RequestSecurityMiddleware(downstream),
        headers={
            "content-type": "multipart/form-data; boundary=x",
            "content-length": "8",
        },
    )
    assert response_status(sent) == 401
    assert not downstream.called


def test_firebase_mode_charges_weighted_units_before_calling_ai(monkeypatch):
    monkeypatch.setattr(security, "AUTH_MODE", "firebase")
    monkeypatch.setattr(security, "APP_CHECK_REQUIRED", False)
    monkeypatch.setattr(security, "MAX_REQUEST_BYTES", 1024)
    monkeypatch.setattr(security, "verify_firebase_token", lambda token: {"uid": "user-a", "email": "a@example.test"})
    calls = []
    monkeypatch.setattr(security, "consume_quota", lambda uid, units: calls.append((uid, units)))
    downstream = DummyApp()
    scope, sent = request(
        security.RequestSecurityMiddleware(downstream),
        path="/api/compare",
        headers={
            "authorization": "Bearer " + "x" * 30,
            "content-type": "multipart/form-data; boundary=x",
            "content-length": "8",
        },
    )
    assert response_status(sent) == 200
    assert calls == [("user-a", 2)]
    assert scope["state"]["clearclause_user"]["uid"] == "user-a"
    start = next(item for item in sent if item["type"] == "http.response.start")
    assert (b"x-content-type-options", b"nosniff") in start["headers"]


def test_quota_backend_failure_fails_closed(monkeypatch):
    monkeypatch.setattr(security, "AUTH_MODE", "firebase")
    monkeypatch.setattr(security, "APP_CHECK_REQUIRED", False)
    monkeypatch.setattr(security, "MAX_REQUEST_BYTES", 1024)
    monkeypatch.setattr(security, "verify_firebase_token", lambda token: {"uid": "user-a", "email": "a@example.test"})

    def unavailable(uid, units):
        raise security.QuotaUnavailable

    monkeypatch.setattr(security, "consume_quota", unavailable)
    downstream = DummyApp()
    _, sent = request(
        security.RequestSecurityMiddleware(downstream),
        headers={
            "authorization": "Bearer " + "x" * 30,
            "content-type": "multipart/form-data; boundary=x",
            "content-length": "8",
        },
    )
    assert response_status(sent) == 503
    assert not downstream.called


def test_memory_quota_is_user_scoped():
    limiter = security.MemoryQuota(hourly=1, daily=1)
    limiter.consume("user-a", 1, now=1000)
    limiter.consume("user-b", 1, now=1000)


def test_cloud_run_cannot_start_with_development_auth_bypass():
    environment = os.environ.copy()
    environment.update({"K_SERVICE": "security-test", "AUTH_MODE": "development", "RATE_LIMIT_BACKEND": "memory"})
    environment.pop("APP_ENV", None)
    result = subprocess.run(
        [sys.executable, "-c", "import app.security"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode != 0
    assert "Production requires AUTH_MODE=firebase" in result.stderr


def test_app_check_is_bound_to_the_configured_firebase_app(monkeypatch):
    from firebase_admin import app_check

    monkeypatch.setattr(security, "FIREBASE_APP_ID", "1:123:web:clearclause")
    monkeypatch.setattr(security, "_firebase_admin", lambda: object())
    monkeypatch.setattr(app_check, "verify_token", lambda token, app: {"sub": "1:123:web:clearclause"})
    security.verify_app_check_token("valid-token")
    monkeypatch.setattr(app_check, "verify_token", lambda token, app: {"sub": "1:123:ios:other-app"})
    with pytest.raises(security.AuthenticationError):
        security.verify_app_check_token("other-app-token")
