import logging
import os
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.ai import InvalidModelOutput, answer_question, briefing, compare_documents
from app.documents import DocumentInputError, extract_pdf
from app.schemas import AnswerResponse, BriefResponse, CompareResponse
from app.security import (
    APP_CHECK_REQUIRED,
    APP_CHECK_SITE_KEY,
    AUTH_MODE,
    FIREBASE_APP_ID,
    FIREBASE_PROJECT_ID,
    RequestSecurityMiddleware,
)

load_dotenv()
BASE_DIR = Path(__file__).parent
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", "12582912"))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "40"))
MAX_EXTRACTED_CHARS = int(os.getenv("MAX_EXTRACTED_CHARS", "100000"))

app = FastAPI(
    title="ClearClause API",
    version="0.1.0",
    description="Document-grounded legal information prototype. Not legal advice.",
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(RequestSecurityMiddleware)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
logger = logging.getLogger(__name__)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    content = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-store"})


@app.get("/api/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/api/config", include_in_schema=False)
def public_config():
    """Firebase web config is public by design; API credentials stay server-side."""
    auth_domain = os.getenv("FIREBASE_AUTH_DOMAIN") or (
        f"{FIREBASE_PROJECT_ID}.firebaseapp.com" if FIREBASE_PROJECT_ID else ""
    )
    return {
        "auth_mode": AUTH_MODE,
        "firebase": {
            "apiKey": os.getenv("FIREBASE_API_KEY", ""),
            "authDomain": auth_domain,
            "projectId": FIREBASE_PROJECT_ID,
            "appId": FIREBASE_APP_ID,
        },
        "appCheckRequired": APP_CHECK_REQUIRED,
        "appCheckSiteKey": APP_CHECK_SITE_KEY,
        "maxPdfBytes": MAX_PDF_BYTES,
    }


def _read_pdf(upload: UploadFile):
    data = upload.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=f"PDF exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MiB limit.")
    try:
        return extract_pdf(upload.filename or "document.pdf", data, MAX_PDF_PAGES, MAX_EXTRACTED_CHARS)
    except DocumentInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _model_error(exc: Exception):
    # Do not return provider diagnostics, request contents, or credentials to the browser.
    code = getattr(exc, "code", None)
    logger.error("Vertex request failed; exception_type=%s; provider_code=%s", type(exc).__name__, code)
    if code in (401, 403):
        detail = (
            "Vertex AI authorization failed. Check that the active Google account can call Vertex AI in this project."
        )
    elif code == 404:
        detail = (
            "The selected Vertex AI model or location is unavailable. Check VERTEX_MODEL and GOOGLE_CLOUD_LOCATION."
        )
    elif code == 429:
        detail = "Vertex AI quota was reached. Check the model's quota and retry later."
    elif code == 400:
        detail = "Vertex AI rejected the request configuration. Check the model or structured-output schema."
    else:
        detail = "Vertex AI could not complete the request. Check project configuration and retry."
    raise HTTPException(status_code=503, detail=detail) from exc


def _invalid_output_note(exc: InvalidModelOutput, task: str) -> str:
    if exc.category == "invalid_json":
        return f"Gemini's response for this {task} was not valid JSON, so no claims are shown. Try a shorter, clearer PDF or a narrower request."
    return f"Gemini returned data that did not match ClearClause's required format for this {task}, so no claims are shown. Try a shorter, clearer PDF or a narrower request."


@app.post("/api/briefing", response_model=BriefResponse)
def create_briefing(file: UploadFile = File(...)):
    document = _read_pdf(file)
    try:
        return briefing(document)
    except InvalidModelOutput as exc:
        return BriefResponse(
            status="insufficient_evidence",
            overview=_invalid_output_note(exc, "briefing"),
            limitations=["No legal-document claims were displayed because the response could not be validated."],
        )
    except Exception as exc:  # noqa: BLE001 - sanitize unexpected Vertex client failures
        _model_error(exc)


@app.post("/api/answer", response_model=AnswerResponse)
def ask_document(question: str = Form(...), file: UploadFile = File(...)):
    question = question.strip()
    if not question or len(question) > 1000:
        raise HTTPException(status_code=422, detail="Enter a question of 1–1,000 characters.")
    document = _read_pdf(file)
    try:
        return answer_question(document, question)
    except InvalidModelOutput as exc:
        return AnswerResponse(
            status="insufficient_evidence",
            answer=_invalid_output_note(exc, "answer"),
        )
    except Exception as exc:  # noqa: BLE001 - sanitize unexpected Vertex client failures
        _model_error(exc)


@app.post("/api/compare", response_model=CompareResponse)
def compare(
    before_file: UploadFile = File(...),
    after_file: UploadFile = File(...),
    lens: str = Form(default="all material text changes"),
):
    if len(lens) > 160:
        raise HTTPException(status_code=422, detail="Comparison lens must be 160 characters or fewer.")
    before = _read_pdf(before_file)
    after = _read_pdf(after_file)
    if before.label == after.label:
        before = replace(before, label="Version 1 - " + before.label[:68])
        after = replace(after, label="Version 2 - " + after.label[:68])
    try:
        return compare_documents(before, after, lens.strip())
    except InvalidModelOutput as exc:
        return CompareResponse(
            status="insufficient_evidence",
            overall_note=_invalid_output_note(exc, "comparison"),
            verify_with_professional=["Review the changed passages in both original documents directly."],
        )
    except Exception as exc:  # noqa: BLE001 - sanitize unexpected Vertex client failures
        _model_error(exc)
