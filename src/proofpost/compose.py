"""Turn a verified quote into a platform-ready post.

The quote is inserted as a locked block; templates (or an optional LLM) write only the
hook line around it. Each platform gets its own length, hashtag and tone limits.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

from .brand import Brand
from .models import Platform

LIMITS = {Platform.INSTAGRAM: 2200, Platform.LINKEDIN: 3000, Platform.X: 280}
HASHTAGS = {Platform.INSTAGRAM: 5, Platform.LINKEDIN: 3, Platform.X: 2}
QUOTE_MAX = {Platform.INSTAGRAM: 220, Platform.LINKEDIN: 300, Platform.X: 170}

HOOKS = {
    "warm": {
        "quality": ["Made to last, and our customers notice.", "Quality you can feel."],
        "delivery": ["Fast, careful delivery matters.", "From our hands to yours, on time."],
        "packaging": ["Unboxing should feel special.", "Packed with care."],
        "value": ["Worth every rupee, in their words.", "Real value, real feedback."],
        "fit": ["The fit says it all.", "Comfort, confirmed."],
        "taste": ["One sip and they were in.", "Flavour worth talking about."],
        "support": ["We're here when it matters.", "Support that shows up."],
        "results": ["Texture people come back for.", "How it feels, in their words."],
        "_": ["Words like these make our day.", "Straight from our community."],
    },
    "crisp": {
        "_": ["Customer feedback:", "What customers are saying:", "In their words:"],
    },
    "playful": {
        "_": ["Okay, this made us blush.", "Screenshotting this forever.",
              "Our customers said it better than we could."],
    },
}  # fmt: skip
EMOJI = {"quality": "✨", "delivery": "📦", "packaging": "🎁", "value": "💛", "fit": "👌",
         "taste": "☕", "support": "🤝", "results": "🌿", "_": "💬"}  # fmt: skip


def _pick(options: list[str], seed: str) -> str:
    return options[int(hashlib.sha1(seed.encode()).hexdigest(), 16) % len(options)]


def template_hook(brand: Brand, aspect: str, seed: str) -> str:
    tone = HOOKS.get(brand.tone, HOOKS["warm"])
    options = tone.get(aspect) or tone["_"]
    return _pick(options, seed)


def stars(rating: float) -> str:
    n = max(0, min(5, round(rating)))
    return "★" * n


def _tags(brand: Brand, aspect: str, limit: int) -> list[str]:
    tags = list(dict.fromkeys(brand.hashtags + ([f"#{aspect.title()}"] if aspect != "_" else [])))
    return [t if t.startswith("#") else f"#{t}" for t in tags][:limit]


def compose(platform: Platform, quote: str, attribution: str, rating: float, aspects: list[str],
            brand: Brand, seed: str, hook_fn: Callable[[str, str], str | None] | None = None
            ) -> str:  # fmt: skip
    aspect = aspects[0] if aspects else "_"
    hook = hook_fn(aspect, platform.value) if hook_fn else None
    hook = hook or template_hook(brand, aspect, seed)
    block = f"“{quote}”"
    who = f"— {attribution} {stars(rating)}".rstrip()
    if platform is Platform.INSTAGRAM:
        head = f"{EMOJI.get(aspect, '💬')} {hook}" if brand.emoji else hook
        tags = " ".join(_tags(brand, aspect, HASHTAGS[platform]))
        return "\n\n".join(x for x in (head, block, who, brand.cta, tags) if x)
    if platform is Platform.LINKEDIN:
        tags = " ".join(_tags(brand, aspect, HASHTAGS[platform]))
        return "\n\n".join(x for x in (hook, block, who, brand.linkedin_cta, tags) if x)
    # X: one compact line, trimmed by dropping optional parts, never the quote
    tag = " ".join(_tags(brand, aspect, 1))
    for parts in ((block, who, tag), (block, who), (block,)):
        text = " ".join(p for p in parts if p)
        if len(text) <= LIMITS[platform]:
            return text
    return block


def hashtag_count(text: str) -> int:
    return len(re.findall(r"(?<!\w)#\w+", text))
