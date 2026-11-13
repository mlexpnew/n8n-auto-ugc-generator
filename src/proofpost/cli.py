"""Reviews export in, approval queue out.

    proofpost reviews.csv --brand config/brand.example.yaml --out queue.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import brand as brand_mod
from .export import queue_csv, workbook
from .ingest import from_csv
from .models import Platform
from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="proofpost", description=__doc__.splitlines()[0])
    p.add_argument("reviews", help="CSV export (Google, Shopify review apps, Amazon, any sheet)")
    p.add_argument("--brand", help="brand YAML (voice, hashtags, banned words)")
    p.add_argument("--out", default="approval_queue.xlsx", help=".xlsx or .csv")
    p.add_argument("--platforms", default="instagram,linkedin,x")
    p.add_argument("--llm", default="", help="hook writer: groq, gemini, openrouter, ollama")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    reviews, skipped = from_csv(Path(a.reviews).read_bytes())
    b = brand_mod.load(a.brand)
    hook = None
    if a.llm:
        from .llm import hook_fn

        hook = hook_fn(a.llm, b)
    platforms = tuple(Platform(x.strip()) for x in a.platforms.split(",") if x.strip())
    res = run(reviews, b, platforms, hook)
    out = Path(a.out)
    out.write_bytes(workbook(res)) if out.suffix == ".xlsx" else out.write_text(queue_csv(res))
    summary = {**res.summary(), "rows_skipped": skipped, "output": str(out)}
    if a.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{summary['reviews_in']} reviews -> {summary['posts_ready_for_approval']} posts "
              f"ready for approval, {summary['reviews_rejected']} reviews not used -> {out}")
    if not reviews:
        print("no usable reviews found", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
