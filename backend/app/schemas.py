"""Request / response shapes for the API (validated automatically by FastAPI)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Channel = Literal["web", "telegram", "extension", "api"]


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    channel: Channel = "web"


class UrlIn(BaseModel):
    url: str = Field(min_length=3, max_length=2048)
    channel: Channel = "web"


class UrlResult(BaseModel):
    url: str
    score: float
    signals: list[str]


class AnalysisOut(BaseModel):
    analysis_id: str
    verdict: Literal["scam", "suspicious", "safe"]
    risk_score: float
    text_score: float | None
    url_score: float | None
    reasons: list[str]
    explanation: str
    advice: list[str]
    urls: list[UrlResult]
    language: str
    model_version: str
    extracted_text: str | None = None  # filled for screenshots (OCR)


class FeedbackIn(BaseModel):
    analysis_id: str
    is_correct: bool
    correct_label: Literal["scam", "safe"] | None = None
    comment: str | None = Field(default=None, max_length=1000)


class StatsOut(BaseModel):
    total_checks: int
    scams_detected: int
    suspicious: int
    safe: int
    feedback_count: int
    accuracy_from_feedback: float | None
    top_reasons: list[tuple[str, int]]
    models: dict
