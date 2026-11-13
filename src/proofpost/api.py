"""HTTP API: n8n, Zapier, Make or any backend posts reviews here and gets posts back.

    uvicorn proofpost.api:app --port 8000

Set PROOFPOST_API_KEYS (comma separated) to require an X-API-Key header.
Nothing is stored: reviews are processed in memory and returned.
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import __version__
from .brand import Brand
from .ingest import from_rows
from .models import Platform
from .pipeline import run

MAX_REVIEWS = 5000
app = FastAPI(
    title="ProofPost",
    version=__version__,
    description="Turn real customer reviews into compliant, on-brand social posts.",
)


class Request(BaseModel):
    reviews: list[dict] = Field(
        min_length=1, max_length=MAX_REVIEWS, description="Rows with review text and rating"
    )
    brand: Brand = Field(default_factory=Brand)
    platforms: list[Platform] = Field(default_factory=lambda: list(Platform))


def auth(x_api_key: str = Header(default="")) -> None:
    keys = {k.strip() for k in os.getenv("PROOFPOST_API_KEYS", "").split(",") if k.strip()}
    if keys and x_api_key not in keys:
        raise HTTPException(401, "missing or invalid X-API-Key")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/v1/posts", dependencies=[Depends(auth)])
def posts(req: Request) -> dict:
    try:
        reviews, skipped = from_rows(req.reviews, source="api")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    res = run(reviews, req.brand, tuple(req.platforms))
    return {
        "posts": [p.model_dump(mode="json") for p in res.posts],
        "rejected": [r.model_dump() for r in res.rejected],
        "summary": {**res.summary(), "rows_skipped": skipped},
    }
