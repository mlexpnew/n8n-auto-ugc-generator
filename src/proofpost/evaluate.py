"""Benchmark ProofPost against the way brands usually repost reviews.

    python -m proofpost.evaluate --gate

Naive baseline (what a social media intern or a simple "reviews to posts" automation does):
take every 4-5 star review, post the full text, credit the customer by full name.
Both are scored on the same labelled reviews for what actually causes incidents.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .brand import Brand
from .compose import LIMITS
from .models import Platform
from .pipeline import run
from .synth import TODAY, Labelled, generate


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def score_posts(posts: list[dict], labelled: list[Labelled]) -> dict:
    """posts: dicts with review_id, text, quote, platform."""
    by_id = {x.review.id: x for x in labelled}
    used = {p["review_id"] for p in posts}
    leaks = {"personal_data": 0, "health_or_absolute_claims": 0, "incentivised_reused": 0,
             "negative_reused": 0, "fake_duplicates_reused": 0, "low_rating_reused": 0,
             "named_without_consent": 0, "misquoted": 0, "over_platform_limit": 0}  # fmt: skip
    for p in posts:
        x = by_id[p["review_id"]]
        r = x.review
        text = p["text"]
        if any(v and v in text for v in x.pii_values):
            leaks["personal_data"] += 1
        if any(c in text for c in x.claim_sentences):
            leaks["health_or_absolute_claims"] += 1
        if x.kind == "incentivised":
            leaks["incentivised_reused"] += 1
        if x.kind == "negative":
            leaks["negative_reused"] += 1
        if x.kind == "duplicate":
            leaks["fake_duplicates_reused"] += 1
        if x.kind == "low_rating":
            leaks["low_rating_reused"] += 1
        surname = r.author.split()[-1]
        if not r.consent_to_name and (surname in text or r.author.split()[0] in text):
            leaks["named_without_consent"] += 1
        if _norm(p["quote"]) not in _norm(r.text):
            leaks["misquoted"] += 1
        if len(text) > LIMITS[Platform(p["platform"])]:
            leaks["over_platform_limit"] += 1
    eligible = {x.review.id for x in labelled if x.eligible}
    return {
        "posts": len(posts),
        "reviews_used": len(used),
        "eligible_reviews": len(eligible),
        "eligible_used": len(used & eligible),
        "selection_precision": round(len(used & eligible) / len(used), 4) if used else None,
        "eligible_coverage": round(len(used & eligible) / len(eligible), 4) if eligible else None,
        "posts_with_any_problem": sum(1 for p in posts if _problem(p, by_id)),
        "problems": leaks,
    }


def _problem(p: dict, by_id: dict) -> bool:
    x = by_id[p["review_id"]]
    r = x.review
    bad_kind = x.kind in ("incentivised", "negative", "duplicate", "low_rating", "claim_only",
                          "short", "spam")  # fmt: skip
    return (bad_kind or any(v and v in p["text"] for v in x.pii_values)
            or any(c in p["text"] for c in x.claim_sentences)
            or (not r.consent_to_name and r.author.split()[-1] in p["text"])
            or _norm(p["quote"]) not in _norm(r.text))  # fmt: skip


def naive(labelled: list[Labelled]) -> list[dict]:
    posts = []
    for x in labelled:
        r = x.review
        if r.rating < 4:
            continue
        for plat in Platform:
            text = f"“{r.text}” — {r.author} ★★★★★ #CustomerLove"
            posts.append({"review_id": r.id, "text": text, "quote": r.text, "platform": plat.value})
    return posts


def proofpost(labelled: list[Labelled]) -> tuple[list[dict], dict]:
    brand = Brand(name="Brewly", hashtags=["#Brewly", "#CustomerLove"], max_posts=10_000)
    res = run([x.review for x in labelled], brand, today=TODAY)
    posts = [{"review_id": p.review_id, "text": p.text, "quote": p.quote,
              "platform": p.platform.value} for p in res.posts]  # fmt: skip
    return posts, res.summary()


def evaluate(n: int, seed: int, phrasing: str) -> dict:
    labelled = generate(n, seed, phrasing)
    pp_posts, summary = proofpost(labelled)
    kinds: dict[str, int] = {}
    for x in labelled:
        kinds[x.kind] = kinds.get(x.kind, 0) + 1
    return {
        "phrasing": phrasing, "reviews": n, "mix": kinds,
        "proofpost": score_posts(pp_posts, labelled),
        "naive": score_posts(naive(labelled), labelled), "pipeline": summary,
    }  # fmt: skip


def report(dev: dict, held: dict) -> str:
    def pct(v):
        return "n/a" if v is None else f"{v * 100:.0f}%"

    rows = []
    for k in dev["proofpost"]["problems"]:
        rows.append(
            f"| {k.replace('_', ' ')} | {dev['naive']['problems'][k]} | "
            f"{dev['proofpost']['problems'][k]} | {held['proofpost']['problems'][k]} |"
        )
    nv, pp, ho = dev["naive"], dev["proofpost"], held["proofpost"]
    return "\n".join([
        f"### ProofPost benchmark ({dev['reviews']} reviews per set, 3 platforms)",
        "",
        "| | Naive repost | ProofPost (dev phrasing) | ProofPost (held-out phrasing) |",
        "|---|---|---|---|",
        f"| Posts produced | {nv['posts']} | {pp['posts']} | {ho['posts']} |",
        f"| Posts with any problem | **{nv['posts_with_any_problem']}** | "
        f"**{pp['posts_with_any_problem']}** | **{ho['posts_with_any_problem']}** |",
        f"| Reviews used that were safe to use | {pct(nv['selection_precision'])} | "
        f"{pct(pp['selection_precision'])} | {pct(ho['selection_precision'])} |",
        f"| Safe reviews turned into posts | {pct(nv['eligible_coverage'])} | "
        f"{pct(pp['eligible_coverage'])} | {pct(ho['eligible_coverage'])} |",
        "",
        "| Problem (count of posts) | Naive | ProofPost dev | ProofPost held-out |",
        "|---|---|---|---|",
        *rows,
    ]) + "\n"  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Benchmark ProofPost vs naive reposting")
    p.add_argument("--n", type=int, default=240)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default="eval_results")
    p.add_argument("--gate", action="store_true", help="exit 1 if any dev post has a problem")
    a = p.parse_args(argv)
    dev = evaluate(a.n, a.seed, "dev")
    held = evaluate(a.n, a.seed + 1, "held_out")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps({"dev": dev, "held_out": held}, indent=2))
    md = report(dev, held)
    (out / "report.md").write_text(md)
    print(md)
    if a.gate:
        bad = dev["proofpost"]["posts_with_any_problem"] > 0 or (
            dev["proofpost"]["eligible_coverage"] or 0) < 0.9
        if bad:
            print("gate failed: problems in posts or coverage below 90%", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
