import asyncio
import os
import subprocess
import sys
from types import SimpleNamespace

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


def test_chunked_body_limit_stops_reading_when_content_length_is_missing(monkeypatch):
    monkeypatch.setattr(security, "AUTH_MODE", "development")
    monkeypatch.setattr(security, "MAX_REQUEST_BYTES", 10)

    class ReaderApp:
        async def __call__(self, scope, receive, send):
            await receive()

    _, sent = request(
        security.RequestSecurityMiddleware(ReaderApp()),
        headers={"content-type": "multipart/form-data; boundary=x"},
        body=b"x" * 11,
    )

    assert response_status(sent) == 413


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


def test_firestore_quota_round_trip_uses_supported_types_and_enforces_weights(monkeypatch):
    from google.cloud import firestore_v1

    stored = {}

    class Reference:
        def get(self, transaction):
            return SimpleNamespace(to_dict=lambda: stored.copy())

    class Transaction:
        def set(self, ref, record):
            # Mirror the real Firestore restriction, not just a mocked success.
            assert all(isinstance(item, dict) for item in record["events"])
            stored.update(record)

    reference = Reference()
    client = SimpleNamespace(
        collection=lambda name: SimpleNamespace(document=lambda digest: reference),
        transaction=Transaction,
    )
    monkeypatch.setattr(security, "_firestore_client", client)
    monkeypatch.setattr(firestore_v1, "transactional", lambda fn: fn)
    monkeypatch.setattr(security, "HOURLY_UNITS", 3)
    monkeypatch.setattr(security, "DAILY_UNITS", 4)
    monkeypatch.setattr(security.time, "time", lambda: 100_000)

    security._consume_firestore("synthetic-user", 2)
    security._consume_firestore("synthetic-user", 1)
    with pytest.raises(security.QuotaExceeded) as limit:
        security._consume_firestore("synthetic-user", 1)
    assert limit.value.retry_after == 3600
    assert len(stored["events"]) == 2
    assert stored["expiresAt"].timestamp() == 272800

    monkeypatch.setattr(security.time, "time", lambda: 103_601)
    with pytest.raises(security.QuotaExceeded):
        security._consume_firestore("synthetic-user", 2)
    security._consume_firestore("synthetic-user", 1)
    monkeypatch.setattr(security.time, "time", lambda: 200_000)
    security._consume_firestore("synthetic-user", 2)
    assert len(stored["events"]) == 1


def test_missing_app_check_blocks_request_before_quota(monkeypatch):
    monkeypatch.setattr(security, "AUTH_MODE", "firebase")
    monkeypatch.setattr(security, "APP_CHECK_REQUIRED", True)
    monkeypatch.setattr(security, "verify_firebase_token", lambda token: {"uid": "synthetic-user"})
    calls = []
    monkeypatch.setattr(security, "consume_quota", lambda *args: calls.append(args))
    downstream = DummyApp()
    _, sent = request(
        security.RequestSecurityMiddleware(downstream),
        headers={
            "content-type": "multipart/form-data; boundary=x",
            "authorization": "Bearer " + "x" * 30,
        },
    )
    assert response_status(sent) == 401
    assert not calls
    assert not downstream.called


@pytest.mark.parametrize(
    "override",
    [
        {"aud": "another-project"},
        {"iss": "https://example.invalid"},
        {"email_verified": False},
        {"uid": ""},
    ],
)
def test_identity_rejects_wrong_project_unverified_or_missing_uid(monkeypatch, override):
    from firebase_admin import auth

    claims = {
        "aud": "test-project",
        "iss": "https://securetoken.google.com/test-project",
        "uid": "synthetic-user",
        "email_verified": True,
    }
    claims.update(override)
    monkeypatch.setattr(security, "FIREBASE_PROJECT_ID", "test-project")
    monkeypatch.setattr(security, "_firebase_admin", lambda: object())
    monkeypatch.setattr(auth, "verify_id_token", lambda *args, **kwargs: claims)
    with pytest.raises(security.AuthenticationError):
        security.verify_firebase_token("synthetic-token")
