import anyio
import httpx
import pymupdf
import pytest

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
    assert response.headers["cache-control"] == "no-store"
    assert "SECURE ACCESS" in response.text
    assert "verify the email link" in response.text
    assert 'aria-live="polite"' in response.text
    assert 'aria-busy="false"' in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_brand_favicon_is_available():
    response = request("GET", "/static/favicon.svg")
    assert response.status_code == 200
    assert "<svg" in response.text


def test_analysis_requires_multipart_upload():
    response = request("POST", "/api/briefing", data={"value": "x"})
    assert response.status_code == 415
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_file_limit_rejects_oversized_upload_before_pdf_parse():
    from app.main import MAX_PDF_BYTES

    response = request(
        "POST",
        "/api/briefing",
        files={"file": ("oversized.pdf", b"%PDF-" + b"x" * MAX_PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 413


def synthetic_pdf():
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "The client must pay the agreed fee within thirty days of the invoice date.")
        return pdf.tobytes()


@pytest.mark.parametrize(
    "route,method,fields,payload",
    [
        ("briefing", "briefing", {}, {"status": "supported", "overview": "Payment is due within thirty days."}),
        (
            "answer",
            "answer_question",
            {"question": "When is payment due?"},
            {"status": "supported", "answer": "Within thirty days."},
        ),
        ("compare", "compare_documents", {"lens": "payment"}, {"status": "supported", "overall_note": "No change."}),
    ],
)
def test_document_workflows_return_structured_response(monkeypatch, route, method, fields, payload):
    from app import main

    received = []

    def model(*args):
        received.extend(args)
        return payload

    monkeypatch.setattr(main, method, model)
    names = ("before_file", "after_file") if route == "compare" else ("file",)
    files = {name: ("x" * 76 + ".pdf", synthetic_pdf(), "application/pdf") for name in names}
    response = request("POST", "/api/" + route, files=files, data=fields)
    assert response.status_code == 200
    assert response.json()["status"] == "supported"
    if route == "compare":
        assert received[0].label != received[1].label
        assert len(received[0].label) <= 80


def test_provider_error_does_not_leak_document_text(monkeypatch):
    from app import main

    def unavailable(document):
        raise RuntimeError("sensitive provider details must not be shown")

    monkeypatch.setattr(main, "briefing", unavailable)
    response = request("POST", "/api/briefing", files={"file": ("synthetic.pdf", synthetic_pdf(), "application/pdf")})
    assert response.status_code == 503
    assert "sensitive provider details" not in response.text


def test_invalid_generation_returns_abstention(monkeypatch):
    from app import main
    from app.ai import InvalidModelOutput

    def invalid(document):
        raise InvalidModelOutput("invalid_json")

    monkeypatch.setattr(main, "briefing", invalid)
    response = request("POST", "/api/briefing", files={"file": ("synthetic.pdf", synthetic_pdf(), "application/pdf")})
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_evidence"


def test_empty_question_rejected_before_model(monkeypatch):
    from app import main

    def unexpected(*args):
        pytest.fail("Empty question should not reach the model")

    monkeypatch.setattr(main, "answer_question", unexpected)
    response = request(
        "POST",
        "/api/answer",
        data={"question": " "},
        files={"file": ("synthetic.pdf", synthetic_pdf(), "application/pdf")},
    )
    assert response.status_code == 422
