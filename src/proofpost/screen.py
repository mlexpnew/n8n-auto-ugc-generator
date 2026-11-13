"""Decide which reviews may be used publicly, and why the rest may not.

Rules follow what Indian advertising and review norms expect from brands that reuse
reviews (ASCI code, IS 19000:2022 on online consumer reviews, DPDP Act for personal data):
no incentivised reviews without disclosure, no health or absolute claims the brand could
not substantiate, no mixed or negative reviews passed off as praise, no duplicates.
"""

from __future__ import annotations

import re
from collections import Counter

from .models import Rejection, Review

INCENTIVISED = re.compile(
    r"\b(?:received (?:this|it|the product) (?:for )?free|got (?:this|it) (?:for )?free|"
    r"free (?:sample|product) in exchange|in exchange for (?:an? )?(?:honest )?review|"
    r"gifted (?:by|to me)|sponsored|#ad\b|#gifted|paid partnership|"
    r"(?:discount|coupon|cashback) (?:for|after) (?:writing|leaving|posting) (?:a |this )?review)",
    re.I,
)
CLAIMS = re.compile(
    r"\b(?:cure[sd]?|curing|heal(?:s|ed)?|treat(?:s|ed)? my|eczema|psoriasis|diabetes|"
    r"blood pressure|thyroid|pcos|acne (?:is )?(?:gone|disappeared|cleared)|"
    r"lost \d+\s?(?:kg|kgs|kilos|pounds)|weight loss|doctor(?:s)? recommend|no side effects?|"
    r"100\s?%|guarantee[sd]?|permanent(?:ly)?|best in (?:india|the world)|clinically|"
    r"miracle|instant(?:ly)? (?:fair|white)|fairness|whiten(?:s|ing|ed)?)\b",
    re.I,
)
NEGATIVE = re.compile(
    r"\b(?:disappoint(?:ed|ing)?|worst|terrible|awful|broke|broken|stopped working|"
    r"waste of|not worth|never again|had to return|returned it|rash|allerg(?:y|ic)|"
    r"itch(?:y|ing)|smell(?:s|ed)? bad|fake product|duplicate product|damaged|leak(?:ed|ing)|"
    r"overpriced|poor quality|cheap quality|late delivery|delayed|rude)\b",
    re.I,
)
PROFANITY = re.compile(r"\b(?:damn|hell|crap|wtf|shit|bloody)\b", re.I)


def _spammy(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    caps = sum(c.isupper() for c in letters) / max(1, len(letters))
    return caps > 0.6 or bool(re.search(r"(.)\1{5,}", text)) or text.count("http") > 1


def screen(reviews: list[Review], min_rating: float = 4.0, min_chars: int = 40
           ) -> tuple[list[Review], list[Rejection]]:  # fmt: skip
    """Eligible reviews and rejections with every reason that applies."""
    norm = Counter(re.sub(r"\W+", " ", r.text.lower()).strip() for r in reviews)
    seen: set[str] = set()
    ok, rejected = [], []
    for r in reviews:
        reasons = []
        key = re.sub(r"\W+", " ", r.text.lower()).strip()
        if r.rating < min_rating:
            reasons.append(f"rating {r.rating:g} below {min_rating:g}")
        if len(r.text.strip()) < min_chars:
            reasons.append("too short to quote")
        if INCENTIVISED.search(r.text):
            reasons.append("incentivised review: cannot be reused without disclosure")
        if NEGATIVE.search(r.text):
            reasons.append("contains negative experience: mixed review")
        if PROFANITY.search(r.text):
            reasons.append("profanity")
        if _spammy(r.text):
            reasons.append("looks like spam")
        if norm[key] > 1 and key in seen:
            reasons.append("duplicate text: possible fake review")
        seen.add(key)
        if reasons:
            rejected.append(Rejection(review_id=r.id, reasons=reasons))
        else:
            ok.append(r)
    return ok, rejected
