from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document: str = Field(min_length=1, max_length=80)
    page: int = Field(ge=1)
    quote: str = Field(min_length=8, max_length=700)


class Finding(BaseModel):
    topic: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=1200)
    citations: list[Citation] = Field(default_factory=list, max_length=5)
    uncertainty: str = Field(default="", max_length=500)


class BriefResponse(BaseModel):
    status: Literal["supported", "partial", "insufficient_evidence"]
    overview: str = Field(max_length=3000)
    overview_citations: list[Citation] = Field(default_factory=list, max_length=5)
    key_points: list[Finding] = Field(default_factory=list, max_length=6)
    verify_with_professional: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class AnswerResponse(BaseModel):
    status: Literal["supported", "partial", "insufficient_evidence", "conflicting"]
    answer: str = Field(max_length=3000)
    citations: list[Citation] = Field(default_factory=list, max_length=8)
    uncertainties: list[str] = Field(default_factory=list, max_length=8)
    questions_for_professional: list[str] = Field(default_factory=list, max_length=5)


class Change(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    change_type: Literal["added", "removed", "changed", "needs_review"]
    before: str = Field(max_length=900)
    after: str = Field(max_length=900)
    explanation: str = Field(max_length=1200)
    citations: list[Citation] = Field(default_factory=list, max_length=4)


class CompareResponse(BaseModel):
    status: Literal["supported", "partial", "insufficient_evidence"]
    changes: list[Change] = Field(default_factory=list, max_length=15)
    overall_note: str = Field(max_length=1200)
    verify_with_professional: list[str] = Field(default_factory=list, max_length=8)
