"""Optional LLM for hook lines only. The customer quote never passes through the model.

Any OpenAI-compatible endpoint works (Groq, Gemini's OpenAI endpoint, OpenRouter, local
Ollama). If the call fails or the hook breaks a rule, the template hook is used instead.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable

from .brand import Brand
from .screen import CLAIMS

PRESETS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
               "gemini-2.5-flash"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
                   "meta-llama/llama-3.3-70b-instruct"),
    "ollama": ("http://localhost:11434/v1", None, "qwen2.5:7b-instruct"),
}  # fmt: skip

PROMPT = """Write ONE short opening line (max 70 characters) for a {platform} post that
shares a real customer review about {aspect} for the brand {brand}. Tone: {tone}.
Rules: no quotation marks, no hashtags, no emojis, no prices, no medical, health,
"best", "guaranteed" or "100%" claims, do not describe what the customer said.
Return only the line."""


def _post(url: str, headers: dict, body: dict) -> dict:
    import requests

    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def hook_fn(provider: str, brand: Brand, post: Callable = _post
            ) -> Callable[[str, str], str | None]:  # fmt: skip
    base, key_env, model = PRESETS[provider]
    key = os.getenv(key_env) if key_env else None
    if key_env and not key:
        raise RuntimeError(f"{key_env} is not set")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    def make(aspect: str, platform: str) -> str | None:
        prompt = PROMPT.format(platform=platform, aspect=aspect, brand=brand.name, tone=brand.tone)
        body = {"model": model, "temperature": 0.7, "max_tokens": 40,
                "messages": [{"role": "user", "content": prompt}]}  # fmt: skip
        try:
            data = post(f"{base}/chat/completions", headers, body)
            line = data["choices"][0]["message"]["content"]
        except Exception:
            return None
        line = line.strip().splitlines()[0].strip() if line and line.strip() else ""
        bad = (not line or len(line) > 80 or re.search(r"[\"“”#]", line) or CLAIMS.search(line)
               or any(w.lower() in line.lower() for w in brand.banned_words))  # fmt: skip
        return None if bad else line

    return make
