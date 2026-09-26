import pymupdf
import pytest

from app.documents import DocumentInputError, LegalDocument, PageText, citation_is_grounded, extract_pdf
from app.schemas import Citation


def make_pdf(text: str) -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    data = pdf.tobytes()
    pdf.close()
    return data


def test_pdf_extraction_preserves_page_numbers_and_normalizes_label():
    document = extract_pdf(
        "Contract #1.pdf", make_pdf("Either party may terminate this agreement with 30 days written notice."), 5, 1000
    )
    assert document.label == "Contract _1.pdf"
    assert document.pages[0].page == 1
    assert "terminate this agreement" in document.extracted_text


def test_rejects_non_pdf_input():
    with pytest.raises(DocumentInputError, match="does not look like a PDF"):
        extract_pdf("fake.pdf", b"not a pdf", 5, 1000)


def test_citation_must_match_the_correct_source_page():
    document = LegalDocument("agreement.pdf", (PageText(1, "Either party may terminate this agreement with notice."),))
    exact = Citation(document="agreement.pdf", page=1, quote="terminate this agreement")
    wrong_page = Citation(document="agreement.pdf", page=2, quote="terminate this agreement")
    invented = Citation(document="agreement.pdf", page=1, quote="the landlord may cancel")
    assert citation_is_grounded(exact, {"agreement.pdf": document})
    assert not citation_is_grounded(wrong_page, {"agreement.pdf": document})
    assert not citation_is_grounded(invented, {"agreement.pdf": document})
