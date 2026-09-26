"""Authentication, early request guards, and abuse quotas for ClearClause.

Production requests must carry a verified Firebase Authentication ID token and
pass the shared Firestore quota. Local development deliberately uses a process
local limiter and no login; this mode is rejected on Cloud Run.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from starlette.types import ASGIApp, Message, Receive, Scope, Send

load_dotenv()

IS_CLOUD_RUN = bool(os.getenv("K_SERVICE"))
APP_ENV = "production" if IS_CLOUD_RUN else os.getenv("APP_ENV", "development").lower()
AUTH_MODE = os.getenv("AUTH_MODE", "firebase" if APP_ENV == "production" else "development").lower()
RATE_LIMIT_BACKEND = os.getenv("RATE_LIMIT_BACKEND", "firestore" if APP_ENV == "production" else "memory").lower()
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN") or (
    f"{FIREBASE_PROJECT_ID}.firebaseapp.com" if FIREBASE_PROJECT_ID else ""
)
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID", "")
APP_CHECK_REQUIRED = os.getenv("APP_CHECK_REQUIRED", "true" if APP_ENV == "production" else "false").lower() == "true"
APP_CHECK_SITE_KEY = os.getenv("FIREBASE_APP_CHECK_SITE_KEY", "")
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", "12582912"))
MAX_REQUEST_BYTES = 2 * MAX_PDF_BYTES + 262_144
HOURLY_UNITS = int(os.getenv("USER_HOURLY_UNITS", "8"))
DAILY_UNITS = int(os.getenv("USER_DAILY_UNITS", "30"))
PROTECTED_PATHS = {"/api/briefing": 1, "/api/answer": 1, "/api/compare": 2}
logger = logging.getLogger(__name__)

if APP_ENV == "production":
    if AUTH_MODE != "firebase":
        raise RuntimeError("Production requires AUTH_MODE=firebase.")
    if RATE_LIMIT_BACKEND != "firestore":
        raise RuntimeError("Production requires RATE_LIMIT_BACKEND=firestore.")
    if not FIREBASE_PROJECT_ID:
        raise RuntimeError("Production requires FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT.")
    if not FIREBASE_API_KEY or not FIREBASE_AUTH_DOMAIN:
        raise RuntimeError("Production requires Firebase web configuration for authenticated access.")
    if not APP_CHECK_REQUIRED:
        raise RuntimeError("Production requires APP_CHECK_REQUIRED=true.")
    if not FIREBASE_APP_ID or not APP_CHECK_SITE_KEY:
        raise RuntimeError("Production App Check requires FIREBASE_APP_ID and FIREBASE_APP_CHECK_SITE_KEY.")
    if HOURLY_UNITS < 1 or DAILY_UNITS < HOURLY_UNITS:
        raise RuntimeError("Production user quota settings are invalid.")


class AuthenticationError(Exception):
    pass


class QuotaExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)


class QuotaUnavailable(Exception):
    pass


class RequestBodyTooLarge(Exception):
    pass


class MemoryQuota:
    """Small local-only limiter. Never suitable for multi-instance deployment."""

    def __init__(self, hourly: int = HOURLY_UNITS, daily: int = DAILY_UNITS):
        self.hourly = hourly
        self.daily = daily
        self.lock = threading.Lock()
        self.counts: dict[str, list[tuple[int, int]]] = defaultdict(list)

    def consume(self, user_id: str, units: int, now: int | None = None) -> None:
        now = int(time.time()) if now is None else now
        with self.lock:
            recent = [(stamp, cost) for stamp, cost in self.counts[user_id] if stamp > now - 86400]
            hour_events = [(stamp, cost) for stamp, cost in recent if stamp > now - 3600]
            hour_used = sum(cost for _, cost in hour_events)
            day_used = sum(cost for _, cost in recent)
            retries = []
            if hour_used + units > self.hourly:
                retries.append(_retry_after(hour_events, self.hourly, units, now, 3600))
            if day_used + units > self.daily:
                retries.append(_retry_after(recent, self.daily, units, now, 86400))
            if retries:
                raise QuotaExceeded(max(retries))
            recent.append((now, units))
            self.counts[user_id] = recent


def _retry_after(events: list[tuple[int, int]], limit: int, units: int, now: int, window: int) -> int:
    remaining = sum(cost for _, cost in events)
    for stamp, cost in sorted(events):
        remaining -= cost
        if remaining + units <= limit:
            return max(1, stamp + window - now)
    return window


_memory_quota = MemoryQuota()
_firebase_app = None
_firestore_client = None
_firebase_lock = threading.Lock()


def _firebase_admin():
    global _firebase_app
    with _firebase_lock:
        if _firebase_app is None:
            try:
                import firebase_admin
                from firebase_admin import credentials

                _firebase_app = firebase_admin.initialize_app(
                    credentials.ApplicationDefault(), {"projectId": FIREBASE_PROJECT_ID}
                )
            except Exception as exc:
                raise QuotaUnavailable("Identity provider unavailable") from exc
        return _firebase_app


def verify_firebase_token(token: str) -> dict[str, Any]:
    try:
        from firebase_admin import auth

        claims = auth.verify_id_token(token, app=_firebase_admin(), check_revoked=False)
        if (
            claims.get("aud") != FIREBASE_PROJECT_ID
            or claims.get("iss") != f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"
        ):
            raise AuthenticationError
        if claims.get("email_verified") is not True:
            raise AuthenticationError
        uid = claims.get("uid")
        if not isinstance(uid, str) or not uid:
            raise AuthenticationError
        return {"uid": uid, "email": claims.get("email", "")}
    except (AuthenticationError, QuotaUnavailable):
        raise
    except Exception as exc:
        raise AuthenticationError from exc


def verify_app_check_token(token: str) -> None:
    try:
        from firebase_admin import app_check

        claims = app_check.verify_token(token, app=_firebase_admin())
        # Firebase's decoded App Check token carries its app ID in `sub`.
        if claims.get("sub") != FIREBASE_APP_ID:
            raise AuthenticationError
    except (AuthenticationError, QuotaUnavailable):
        raise
    except Exception as exc:
        raise AuthenticationError from exc


def _consume_firestore(user_id: str, units: int) -> None:
    global _firestore_client
    try:
        from google.cloud import firestore
        from google.cloud.firestore_v1 import transactional

        if _firestore_client is None:
            with _firebase_lock:
                if _firestore_client is None:
                    _firestore_client = firestore.Client(project=FIREBASE_PROJECT_ID)
        now = int(time.time())
        # UIDs are not stored in Firestore paths. The digest prevents casual
        # disclosure through project console listings while preserving stable keys.
        digest = hashlib.sha256((FIREBASE_PROJECT_ID + ":" + user_id).encode()).hexdigest()
        ref = _firestore_client.collection("clearClauseRateLimits").document(digest)
        transaction = _firestore_client.transaction()

        @transactional
        def update(tx):
            snapshot = ref.get(transaction=tx)
            record = snapshot.to_dict() or {}
            # Firestore forbids arrays directly nested in arrays. Store maps
            # so the first quota reservation can actually commit in production.
            events = [
                (int(item["timestamp"]), int(item["units"]))
                for item in record.get("events", [])
                if int(item["timestamp"]) > now - 86400
            ]
            if any(cost < 1 for _, cost in events):
                raise ValueError("Invalid quota event")
            hour_events = [(stamp, cost) for stamp, cost in events if stamp > now - 3600]
            hour_used = sum(cost for _, cost in hour_events)
            day_used = sum(cost for _, cost in events)
            retries = []
            if hour_used + units > HOURLY_UNITS:
                retries.append(_retry_after(hour_events, HOURLY_UNITS, units, now, 3600))
            if day_used + units > DAILY_UNITS:
                retries.append(_retry_after(events, DAILY_UNITS, units, now, 86400))
            if retries:
                raise QuotaExceeded(max(retries))
            events.append((now, units))
            tx.set(
                ref,
                {
                    "events": [{"timestamp": stamp, "units": cost} for stamp, cost in events],
                    "expiresAt": datetime.fromtimestamp(now + 2 * 86400, tz=timezone.utc),
                },
            )

        update(transaction)
    except QuotaExceeded:
        raise
    except Exception as exc:
        logger.error("Quota reservation failed; exception_type=%s", type(exc).__name__)
        raise QuotaUnavailable("Quota service unavailable") from exc


def consume_quota(user_id: str, units: int) -> None:
    if RATE_LIMIT_BACKEND == "memory":
        _memory_quota.consume(user_id, units)
        return
    if RATE_LIMIT_BACKEND == "firestore":
        _consume_firestore(user_id, units)
        return
    raise QuotaUnavailable("Quota backend is not configured")


def _response(start_response: Send, status: int, detail: str, headers: list[tuple[bytes, bytes]] | None = None):
    payload = json.dumps({"detail": detail}).encode()
    response_headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(payload)).encode()),
        (b"cache-control", b"no-store"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"x-permitted-cross-domain-policies", b"none"),
        (b"cross-origin-resource-policy", b"same-origin"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
        (
            b"content-security-policy",
            b"default-src 'self'; script-src 'self' https://www.gstatic.com https://www.google.com/recaptcha/ https://www.recaptcha.net/recaptcha/; style-src 'self'; img-src 'self' data:; connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://firebaseappcheck.googleapis.com https://recaptchaenterprise.googleapis.com https://www.google.com/recaptcha/ https://www.recaptcha.net/recaptcha/; frame-src https://www.google.com/recaptcha/ https://www.recaptcha.net/recaptcha/; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        ),
    ]
    if APP_ENV == "production":
        response_headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
    response_headers.extend(headers or [])

    async def send_response():
        await start_response({"type": "http.response.start", "status": status, "headers": response_headers})
        await start_response({"type": "http.response.body", "body": payload})

    return send_response


class RequestSecurityMiddleware:
    """Authenticate/quota protected requests before multipart parsing begins."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        is_protected = method == "POST" and path in PROTECTED_PATHS

        if is_protected:
            if os.getenv("GENAI_ENABLED", "true").lower() != "true":
                await _response(send, 503, "Document analysis is temporarily disabled by the service operator.")()
                return
            length_header = headers.get(b"content-length")
            if length_header:
                try:
                    content_length = int(length_header)
                except ValueError:
                    await _response(send, 400, "Invalid request size header.")()
                    return
                if content_length < 0 or content_length > MAX_REQUEST_BYTES:
                    await _response(send, 413, f"Request exceeds the {MAX_REQUEST_BYTES // (1024 * 1024)} MiB limit.")()
                    return
            content_type = headers.get(b"content-type", b"").lower()
            if not content_type.startswith(b"multipart/form-data;"):
                await _response(send, 415, "Document analysis requires a multipart PDF upload.")()
                return
            user = None
            if AUTH_MODE == "firebase":
                authorization = headers.get(b"authorization", b"").decode("latin-1")
                match = re.fullmatch(r"Bearer ([A-Za-z0-9._~-]{20,8192})", authorization)
                if not match:
                    await _response(
                        send,
                        401,
                        "Sign in with a verified account to use document analysis.",
                        [(b"www-authenticate", b"Bearer")],
                    )()
                    return
                try:
                    user = await asyncio.to_thread(verify_firebase_token, match.group(1))
                except AuthenticationError:
                    await _response(
                        send,
                        401,
                        "Your session is invalid or expired. Sign in again.",
                        [(b"www-authenticate", b"Bearer")],
                    )()
                    return
                except QuotaUnavailable:
                    await _response(send, 503, "Authentication is temporarily unavailable. Please try again shortly.")()
                    return
                if APP_CHECK_REQUIRED:
                    app_check = headers.get(b"x-firebase-appcheck", b"").decode("latin-1")
                    if not app_check or len(app_check) > 8192:
                        await _response(send, 401, "This app could not verify the request. Reload and try again.")()
                        return
                    try:
                        await asyncio.to_thread(verify_app_check_token, app_check)
                    except AuthenticationError:
                        await _response(send, 401, "This app could not verify the request. Reload and try again.")()
                        return
                    except QuotaUnavailable:
                        await _response(
                            send, 503, "Request verification is temporarily unavailable. Please try again shortly."
                        )()
                        return
                try:
                    await asyncio.to_thread(consume_quota, user["uid"], PROTECTED_PATHS[path])
                except QuotaExceeded as exc:
                    await _response(
                        send,
                        429,
                        "Your document-analysis usage limit was reached. Please try again later.",
                        [(b"retry-after", str(exc.retry_after).encode())],
                    )()
                    return
                except QuotaUnavailable:
                    # Fail closed: no Vertex calls when the shared limiter is down.
                    await _response(
                        send, 503, "Usage protection is temporarily unavailable. Please try again shortly."
                    )()
                    return
            else:
                user = {"uid": "local-development", "email": ""}
            scope.setdefault("state", {})["clearclause_user"] = user

        async def secured_send(message: Message):
            if message["type"] == "http.response.start":
                current = list(message.get("headers", []))
                current.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"x-permitted-cross-domain-policies", b"none"),
                        (b"cross-origin-resource-policy", b"same-origin"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (
                            b"content-security-policy",
                            b"default-src 'self'; script-src 'self' https://www.gstatic.com https://www.google.com/recaptcha/ https://www.recaptcha.net/recaptcha/; style-src 'self'; img-src 'self' data:; connect-src 'self' https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://firebaseappcheck.googleapis.com https://recaptchaenterprise.googleapis.com https://www.google.com/recaptcha/ https://www.recaptcha.net/recaptcha/; frame-src https://www.google.com/recaptcha/ https://www.recaptcha.net/recaptcha/; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
                        ),
                        (b"cross-origin-opener-policy", b"same-origin"),
                    ]
                )
                if path.startswith("/api/"):
                    current.append((b"cache-control", b"no-store"))
                if APP_ENV == "production":
                    current.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message["headers"] = current
            await send(message)

        guarded_receive = receive
        if is_protected:
            received_bytes = 0

            async def size_limited_receive():
                nonlocal received_bytes
                message = await receive()
                if message["type"] == "http.request":
                    received_bytes += len(message.get("body", b""))
                    if received_bytes > MAX_REQUEST_BYTES:
                        raise RequestBodyTooLarge
                return message

            guarded_receive = size_limited_receive
        try:
            await self.app(scope, guarded_receive, secured_send)
        except RequestBodyTooLarge:
            await _response(send, 413, f"Request exceeds the {MAX_REQUEST_BYTES // (1024 * 1024)} MiB limit.")()
