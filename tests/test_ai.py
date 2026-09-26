import json
from types import SimpleNamespace

import pytest

from app import ai
from app.documents import LegalDocument, PageText
from app.schemas import BriefResponse, Change, Citation, CompareResponse


def document(label: str, text: str) -> LegalDocument:
    return LegalDocument(label=label, pages=(PageText(page=1, text=text),))


def test_operator_kill_switch_prevents_vertex_call(monkeypatch):
    monkeypatch.setattr(ai, "GENAI_ENABLED", False)

    def unexpected_provider_call():
        raise AssertionError("Vertex should not be called while the kill switch is off")

    monkeypatch.setattr(ai, "vertex_client", unexpected_provider_call)
    with pytest.raises(RuntimeError, match="disabled by the service operator"):
        ai._generate("synthetic prompt", {}, max_tokens=10)


def test_invalid_model_output_logs_schema_errors_without_generated_text(monkeypatch, caplog):
    secret_text = "This generated text must not appear in application logs."
    monkeypatch.setattr(
        ai,
        "_generate",
        lambda prompt, schema, max_tokens: json.dumps({"status": "invalid", "answer": secret_text}),
    )

    with pytest.raises(ai.InvalidModelOutput, match="schema_mismatch"):
        ai._parse_structured(ai.AnswerResponse, "synthetic prompt")

    assert "status" in caplog.text
    assert secret_text not in caplog.text


def test_briefing_abstains_when_generated_citation_is_not_grounded(monkeypatch):
    source = document("agreement.pdf", "Either party may terminate this agreement with written notice.")
    response = BriefResponse(
        status="supported",
        overview="The agreement contains a termination clause.",
        overview_citations=[Citation(document="agreement.pdf", page=1, quote="payment is due in 10 days")],
    )
    monkeypatch.setattr(ai, "_parse_structured", lambda *args, **kwargs: response)

    result = ai.briefing(source)

    assert result.status == "insufficient_evidence"
    assert result.overview_citations == []
    assert "could not verify" in result.overview


def test_identical_documents_skip_vertex_comparison(monkeypatch):
    before = document("before.pdf", "Either party must provide thirty days written notice before termination.")
    after = document("after.pdf", "Either party must provide thirty days written notice before termination.")

    def unexpected_model_call(*args, **kwargs):
        raise AssertionError("Identical extracted text should not be sent to Vertex")

    monkeypatch.setattr(ai, "_parse_structured", unexpected_model_call)
    result = ai.compare_documents(before, after, "termination")

    assert result.status == "supported"
    assert result.changes == []
    assert "No text differences" in result.overall_note


def test_comparison_abstains_when_change_citation_is_not_grounded(monkeypatch):
    before = document("before.pdf", "The payment is due within thirty days after receipt of the invoice.")
    after = document("after.pdf", "The payment is due within sixty days after receipt of the invoice.")
    response = CompareResponse(
        status="supported",
        overall_note="The payment period changed.",
        changes=[
            Change(
                topic="Payment timing",
                change_type="changed",
                before="thirty days",
                after="sixty days",
                explanation="The later version allows more time to pay.",
                citations=[
                    Citation(document="before.pdf", page=1, quote="payment is due in ten days"),
                    Citation(document="after.pdf", page=1, quote="payment is due in ten days"),
                ],
            )
        ],
    )
    monkeypatch.setattr(ai, "_parse_structured", lambda *args, **kwargs: response)

    result = ai.compare_documents(before, after, "payment")

    assert result.status == "insufficient_evidence"
    assert result.changes == []
    assert "withholding" in result.overall_note


def test_short_amount_and_case_changes_are_detected():
    before = document("before.pdf", "Fees\nUSD 10\nParty: ACME")
    after = document("after.pdf", "Fees\nUSD 90\nParty: Acme")
    diff = ai._diff_excerpt(before, after)
    assert diff
    assert "USD 10" in diff[0]["before"]
    assert "USD 90" in diff[0]["after"]


def test_question_with_invented_quote_is_withheld(monkeypatch):
    source = document("terms.pdf", "Fees are payable within thirty days of the invoice date.")
    monkeypatch.setattr(
        ai,
        "_parse_structured",
        lambda *args: ai.AnswerResponse(
            status="supported",
            answer="An invented answer.",
            citations=[Citation(document="terms.pdf", page=1, quote="There is no payment obligation")],
        ),
    )
    assert ai.answer_question(source, "When are fees due?").status == "insufficient_evidence"


@pytest.mark.parametrize("generated,category", [("{unfinished", "invalid_json"), ("", "empty")])
def test_vertex_generation_rejects_invalid_json_and_empty_output(monkeypatch, generated, category, caplog):
    monkeypatch.setattr(ai, "GENAI_ENABLED", True)
    response = SimpleNamespace(text=generated, candidates=[])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: response))
    monkeypatch.setattr(ai, "vertex_client", lambda: client)
    with pytest.raises(RuntimeError if category == "empty" else ai.InvalidModelOutput):
        ai._generate("synthetic-source-private", {}, 100)
    assert "synthetic-source-private" not in caplog.text


def test_long_document_answer_discloses_partial_coverage(monkeypatch):
    source = document("long.pdf", "Fees are due within thirty days. " * 3000)
    response = ai.AnswerResponse(
        status="supported",
        answer="Thirty days.",
        citations=[Citation(document="long.pdf", page=1, quote="Fees are due within thirty days.")],
    )
    monkeypatch.setattr(ai, "_parse_structured", lambda *args: response)
    result = ai.answer_question(source, "When are fees due?")
    assert result.status == "partial"
    assert "Only the beginning" in result.uncertainties[0]
