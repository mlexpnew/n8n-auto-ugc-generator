"""Reviews in, an approval queue of compliant posts out."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from .brand import DEFAULT_ASPECTS, Brand
from .compose import QUOTE_MAX, compose
from .guard import check
from .models import Platform, Post, Rejection, Review
from .quote import best_quote
from .redact import attribution, redact
from .screen import CLAIMS, screen


@dataclass
class Result:
    posts: list[Post] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    blocked_posts: list[dict] = field(default_factory=list)  # failed a final check
    reviews_in: int = 0
    pii_redacted: int = 0

    def summary(self) -> dict:
        return {
            "reviews_in": self.reviews_in,
            "reviews_rejected": len(self.rejected),
            "posts_ready_for_approval": len(self.posts),
            "posts_blocked_by_checks": len(self.blocked_posts),
            "reviews_with_personal_data_redacted": self.pii_redacted,
        }


def _recency(d: date | None, today: date) -> float:
    if d is None:
        return 0.0
    days = (today - d).days
    return 1.0 if days <= 30 else 0.5 if days <= 90 else 0.0


def run(reviews: list[Review], brand: Brand | None = None,
        platforms: tuple[Platform, ...] = (Platform.INSTAGRAM, Platform.LINKEDIN, Platform.X),
        hook_fn: Callable[[str, str], str | None] | None = None,
        today: date | None = None) -> Result:  # fmt: skip
    brand = brand or Brand()
    today = today or date.today()
    aspects = brand.aspects or DEFAULT_ASPECTS
    res = Result(reviews_in=len(reviews))
    eligible, res.rejected = screen(reviews, brand.min_rating)

    scored = []
    for r in eligible:
        clean, found = redact(r.text)
        res.pii_redacted += bool(found)
        q = best_quote(clean, QUOTE_MAX[Platform.LINKEDIN], aspects)
        if q is None:
            why = ("only health or absolute claims to quote: brand cannot substantiate them"
                   if CLAIMS.search(clean) else "no safe, specific sentence to quote")
            res.rejected.append(Rejection(review_id=r.id, reasons=[why]))
            continue
        score = q.score + r.rating + 0.5 * r.verified + _recency(r.review_date, today)
        scored.append((score, r, clean, q))

    # Best first; one post per customer; spread across aspects before repeating one
    # Variety is a preference: pass 1 caps each aspect, pass 2 fills any remaining slots
    scored.sort(key=lambda t: (-t[0], t[1].id))
    chosen, authors, used_aspects = [], set(), []
    cap = max(1, brand.max_posts // 3)
    for capped in (True, False):
        for item in scored:
            if len(chosen) >= brand.max_posts:
                break
            _, r, _, q = item
            who = r.author.strip().lower() or r.id
            lead = q.aspects[0] if q.aspects else "_"
            if who in authors or (capped and used_aspects.count(lead) >= cap):
                continue
            chosen.append(item)
            authors.add(who)
            used_aspects.append(lead)

    for score, r, clean, q in chosen:
        who = attribution(r.author, r.consent_to_name, r.verified)
        for p in platforms:
            quote = q.text
            if len(quote) > QUOTE_MAX[p]:  # shorter verbatim quote for tight platforms
                short = best_quote(clean, QUOTE_MAX[p], aspects)
                if short is None:
                    continue
                quote = short.text
            text = compose(p, quote, who, r.rating, q.aspects, brand, f"{r.id}:{p}", hook_fn)
            checks = check(text, quote, p, r, clean, brand)
            post = Post(
                platform=p, text=text, quote=quote, review_id=r.id, rating=r.rating,
                attribution=who, aspects=q.aspects, score=round(score, 2), checks=checks,
            )  # fmt: skip
            if all(checks.values()):
                res.posts.append(post)
            else:
                failed = [k for k, v in checks.items() if not v]
                res.blocked_posts.append({"review_id": r.id, "platform": p.value, "failed": failed})
    return res
