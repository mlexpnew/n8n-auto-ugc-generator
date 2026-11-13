"""Brand configuration: voice, hashtags, words to avoid, claims the brand may not make."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Brand(BaseModel):
    name: str = "Your Brand"
    tone: str = "warm"  # warm | crisp | playful
    emoji: bool = True
    hashtags: list[str] = Field(default_factory=lambda: ["#CustomerLove"])
    cta: str = "Shop the bestsellers, link in bio."
    linkedin_cta: str = "Thank you to every customer who takes the time to share feedback."
    banned_words: list[str] = Field(default_factory=list)
    # Product aspects worth highlighting; keys are labels, values are trigger words
    aspects: dict[str, list[str]] = Field(default_factory=dict)
    min_rating: float = 4.0
    max_posts: int = 10


def load(path: str | Path | None) -> Brand:
    if not path:
        return Brand()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Brand(**data)


DEFAULT_ASPECTS: dict[str, list[str]] = {
    "quality": ["quality", "well made", "sturdy", "premium", "durable", "finish", "stitching"],
    "delivery": ["delivery", "delivered", "shipping", "arrived", "dispatch", "on time"],
    "packaging": ["packaging", "packed", "box", "unboxing", "gift wrap"],
    "value": ["value", "worth", "price", "affordable", "money"],
    "fit": ["fit", "fits", "size", "sizing", "comfortable", "comfort"],
    "taste": ["taste", "flavour", "flavor", "aroma", "fresh", "smooth"],
    "support": ["support", "customer service", "replacement", "refund", "helpful", "responded"],
    "results": ["texture", "absorbs", "lightweight", "glow", "soft", "hydrated", "non-greasy"],
}
