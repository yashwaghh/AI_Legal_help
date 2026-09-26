import re
from dataclasses import dataclass

import pymupdf

from app.schemas import AnswerResponse, BriefResponse, CompareResponse


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


@dataclass(frozen=True)
class LegalDocument:
    label: str
    pages: tuple[PageText, ...]

    @property
    def extracted_text(self) -> str:
        return "\n\n".join(f"[Page {page.page}]\n{page.text}" for page in self.pages)


class DocumentInputError(ValueError):
    pass


def extract_pdf(label: str, data: bytes, max_pages: int, max_chars: int) -> LegalDocument:
    if not data.startswith(b"%PDF-"):
        raise DocumentInputError("This file does not look like a PDF.")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise DocumentInputError("Password-protected PDFs are not supported yet.")
            if pdf.page_count == 0:
                raise DocumentInputError("The PDF has no pages.")
            if pdf.page_count > max_pages:
                raise DocumentInputError(f"The PDF is over the {max_pages}-page limit.")
            pages = tuple(
                PageText(page=index + 1, text=pdf[index].get_text("text", sort=True).strip())
                for index in range(pdf.page_count)
            )
    except DocumentInputError:
        raise
    except Exception as exc:
        raise DocumentInputError("The PDF could not be read. Try an unencrypted, readable PDF.") from exc

    total = sum(len(page.text) for page in pages)
    if total > max_chars:
        raise DocumentInputError(f"Extracted text is over the {max_chars:,}-character limit.")
    if total < 40:
        raise DocumentInputError(
            "Very little selectable text was found. Scanned-PDF OCR is not in this first slice; use a text-based PDF for now."
        )
    safe_label = re.sub(r"[^A-Za-z0-9._ -]", "_", label)[:80] or "document.pdf"
    return LegalDocument(label=safe_label, pages=pages)


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def citation_is_grounded(citation, documents: dict[str, LegalDocument]) -> bool:
    document = documents.get(citation.document)
    if document is None or citation.page > len(document.pages):
        return False
    page_text = document.pages[citation.page - 1].text
    quote = normalized(citation.quote)
    return len(quote) >= 8 and quote in normalized(page_text)


def validate_citations(response, documents: dict[str, LegalDocument]) -> bool:
    if isinstance(response, BriefResponse):
        citations = list(response.overview_citations)
        if response.status in {"supported", "partial"} and not citations:
            return False
        for finding in response.key_points:
            if not finding.citations:
                return False
            citations.extend(finding.citations)
    elif isinstance(response, AnswerResponse):
        citations = response.citations
        if response.status in {"supported", "partial", "conflicting"} and not citations:
            return False
    elif isinstance(response, CompareResponse):
        citations = []
        for change in response.changes:
            if not change.citations:
                return False
            cited_documents = {citation.document for citation in change.citations}
            if change.change_type == "changed" and len(documents) == 2 and len(cited_documents & set(documents)) < 2:
                return False
            citations.extend(change.citations)
    else:
        return False
    return all(citation_is_grounded(citation, documents) for citation in citations)
