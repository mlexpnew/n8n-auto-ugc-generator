"""Typed records shared across the pipeline."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    X = "x"


class Review(BaseModel):
    id: str
    text: str
    rating: float
    author: str = ""
    source: str = ""  # google, shopify, amazon, csv
    product: str = ""
    review_date: date | None = None
    verified: bool = False
    consent_to_name: bool = False  # customer agreed to be named in marketing


class Rejection(BaseModel):
    review_id: str
    reasons: list[str]


class Post(BaseModel):
    platform: Platform
    text: str
    quote: str  # verbatim substring of the review (after redaction)
    review_id: str
    rating: float
    attribution: str
    aspects: list[str] = Field(default_factory=list)
    score: float = 0.0
    status: str = "pending_approval"  # a human approves before anything is published
    checks: dict[str, bool] = Field(default_factory=dict)
