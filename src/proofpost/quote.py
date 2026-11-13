"""Pick the most quotable part of a review: verbatim, specific, and safe.

A quote is always an exact substring of the (redacted) review. Nothing is paraphrased,
shortened mid-sentence or "improved": a reworded customer quote is a fabricated one.
Sentences with health or absolute claims are never quoted, even inside a good review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .brand import DEFAULT_ASPECTS
from .screen import CLAIMS, NEGATIVE, PROFANITY

SENT = re.compile(r"[^.!?\n]+[.!?]*")
POSITIVE = re.compile(
    r"\b(?:love|loved|amazing|excellent|great|perfect|best|happy|impressed|recommend|"
    r"fantastic|wonderful|beautiful|brilliant|superb|awesome|favourite|favorite|smooth|"
    r"soft|fresh|quick|fast|easy|comfortable|worth)\b",
    re.I,
)
SPECIFIC = re.compile(
    r"\b(?:\d+\s?(?:days?|weeks?|months?|years?|hours?|washes|cups|uses|times)|"
    r"after (?:a|one|two|three|\d+)|every (?:day|morning|week)|since)\b",
    re.I,
)


@dataclass
class Quote:
    text: str
    score: float
    aspects: list[str]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT.findall(text) if s.strip()]


def aspects_in(text: str, aspects: dict[str, list[str]]) -> list[str]:
    low = text.lower()
    return [a for a, words in aspects.items()
            if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words)]  # fmt: skip


def candidates(text: str, max_chars: int) -> list[str]:
    """1 or 2 consecutive sentences, taken verbatim from the text."""
    sents = sentences(text)
    out = []
    for i in range(len(sents)):
        for j in (i + 1, i + 2):
            if j > len(sents):
                continue
            start = text.find(sents[i])
            end_sent = sents[j - 1]
            end = text.find(end_sent, start) + len(end_sent)
            span = text[start:end].strip()
            if 25 <= len(span) <= max_chars:
                out.append(span)
    return out


def best_quote(text: str, max_chars: int = 220, aspects: dict | None = None) -> Quote | None:
    aspects = aspects or DEFAULT_ASPECTS
    best = None
    for span in candidates(text, max_chars):
        if CLAIMS.search(span) or NEGATIVE.search(span) or PROFANITY.search(span):
            continue
        if "removed]" in span or span.count('"') % 2:
            continue
        found = aspects_in(span, aspects)
        score = (2.0 * len(found) + 1.0 * len(POSITIVE.findall(span))
                 + 1.5 * bool(SPECIFIC.search(span)) - abs(len(span) - 110) / 80)  # fmt: skip
        if best is None or score > best.score:
            best = Quote(span, round(score, 3), found)
    return best
