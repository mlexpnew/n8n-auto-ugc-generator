"""Read reviews from the exports brands actually have.

Google Business Profile, Shopify review apps (Judge.me, Loox), Amazon seller exports and
plain spreadsheets all name their columns differently; this maps them to one schema.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime

from .models import Review

COLUMNS = {
    "text": ["text", "review", "review_text", "body", "review_body", "comment", "content",
             "review content", "review body", "comments"],
    "rating": ["rating", "stars", "star_rating", "starrating", "score", "review_rating",
               "star rating", "review score"],
    "author": ["author", "name", "reviewer", "reviewer_name", "customer", "customer_name",
               "reviewer name", "display_name"],
    "date": ["date", "review_date", "created_at", "createtime", "created", "submitted_at",
             "review date"],
    "id": ["id", "review_id", "reviewid", "name_id"],
    "product": ["product", "product_title", "product_name", "item", "sku", "asin"],
    "verified": ["verified", "verified_purchase", "verified buyer", "verified_buyer"],
    "consent": ["consent", "marketing_consent", "can_feature", "consent_to_name",
                "permission_to_feature"],
}  # fmt: skip
WORD_RATING = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
TRUE = {"1", "true", "yes", "y", "verified", "t"}


def _key(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower().replace("-", "_"))


def _map(headers: list[str]) -> dict[str, str]:
    found = {}
    norm = {_key(h): h for h in headers}
    for field, names in COLUMNS.items():
        for n in names:
            if n in norm or n.replace(" ", "_") in norm:
                found[field] = norm.get(n) or norm[n.replace(" ", "_")]
                break
    return found


def _rating(v: str) -> float | None:
    v = (v or "").strip()
    if v.upper() in WORD_RATING:
        return float(WORD_RATING[v.upper()])
    m = re.search(r"\d+(?:\.\d+)?", v)
    return float(m.group()) if m else None


def _date(v: str) -> date | None:
    v = (v or "").strip()[:19]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%d %b %Y", "%B %d, %Y"):  # fmt: skip
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def from_rows(rows: list[dict], source: str = "csv") -> tuple[list[Review], int]:
    """Reviews plus how many rows were skipped (no text or no rating)."""
    if not rows:
        return [], 0
    cols = _map(list(rows[0].keys()))
    if "text" not in cols or "rating" not in cols:
        raise ValueError(f"need review text and rating columns; found {list(rows[0].keys())}")
    out, skipped = [], 0
    for i, row in enumerate(rows):
        text = (row.get(cols["text"]) or "").strip()
        rating = _rating(str(row.get(cols["rating"]) or ""))
        if not text or rating is None:
            skipped += 1
            continue
        rid = str(row.get(cols.get("id", ""), "") or "").strip() or hashlib.sha1(
            f"{i}:{text}".encode()
        ).hexdigest()[:10]
        out.append(Review(
            id=rid, text=text, rating=rating,
            author=str(row.get(cols.get("author", ""), "") or "").strip(),
            source=source,
            product=str(row.get(cols.get("product", ""), "") or "").strip(),
            review_date=_date(str(row.get(cols.get("date", ""), "") or "")),
            verified=str(row.get(cols.get("verified", ""), "")).strip().lower() in TRUE,
            consent_to_name=str(row.get(cols.get("consent", ""), "")).strip().lower() in TRUE,
        ))  # fmt: skip
    return out, skipped


def from_csv(data: bytes | str, source: str = "csv") -> tuple[list[Review], int]:
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    return from_rows(list(csv.DictReader(io.StringIO(text))), source)
