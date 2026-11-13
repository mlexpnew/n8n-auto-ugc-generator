"""Final checks on every post. A post that fails any check is dropped, never "fixed"."""

from __future__ import annotations

import re

from .brand import Brand
from .compose import HASHTAGS, LIMITS, hashtag_count
from .models import Platform, Review
from .redact import has_pii
from .screen import CLAIMS, NEGATIVE


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def check(text: str, quote: str, platform: Platform, review: Review, review_text: str,
          brand: Brand) -> dict[str, bool]:  # fmt: skip
    """review_text is the redacted review the quote was taken from."""
    name_parts = [p for p in re.findall(r"[A-Za-z]{3,}", review.author)]
    surname = name_parts[-1] if len(name_parts) > 1 else ""
    named = [p for p in name_parts if re.search(rf"\b{re.escape(p)}\b", text, re.I)]
    return {
        "quote_is_verbatim": _norm(quote) in _norm(review_text),
        "quote_in_post": f"“{quote}”" in text,
        "no_personal_data": not has_pii(text),
        "no_health_or_absolute_claims": not CLAIMS.search(text),
        "no_negative_content": not NEGATIVE.search(text),
        "no_banned_words": not any(re.search(rf"\b{re.escape(w)}\b", text, re.I)
                                   for w in brand.banned_words),  # fmt: skip
        "within_length": len(text) <= LIMITS[platform],
        "hashtags_ok": hashtag_count(text) <= HASHTAGS[platform],
        "name_only_with_consent": (not named) if not review.consent_to_name
        else not (surname and re.search(rf"\b{re.escape(surname)}\b", text, re.I)),
    }
