import anyio
import httpx

from app.main import app


async def _request(method: str, path: str, request_kwargs: dict) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **request_kwargs)


def request(method: str, path: str, **kwargs) -> httpx.Response:
    return anyio.run(_request, method, path, kwargs)


def test_health_and_public_configuration_do_not_expose_vertex_credentials():
    health = request("GET", "/api/health")
    config = request("GET", "/api/config")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert config.status_code == 200
    assert config.json()["auth_mode"] == "development"
    assert "vertex" not in config.text.lower()
    assert health.headers["cache-control"] == "no-store"


def test_home_page_has_security_headers_and_auth_control():
    response = request("GET", "/")
    assert response.status_code == 200
    assert "SECURE ACCESS" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_analysis_requires_multipart_upload():
    response = request("POST", "/api/briefing", data={"value": "x"})
    assert response.status_code == 415


def test_file_limit_rejects_oversized_upload_before_pdf_parse():
    from app.main import MAX_PDF_BYTES

    response = request(
        "POST",
        "/api/briefing",
        files={"file": ("oversized.pdf", b"%PDF-" + b"x" * MAX_PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 413
