"""Remove personal data before anything leaves the review store.

Phone numbers, emails, links, order IDs and UPI handles are replaced with neutral tokens.
Customers are named only as "First L." and only with consent; otherwise "Verified buyer".
"""

from __future__ import annotations

import re

PATTERNS = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("upi", re.compile(r"\b[\w.-]{2,}@(?:ok\w+|ybl|paytm|upi|ibl|axl|apl)\b", re.I)),
    ("link", re.compile(r"(?:https?://|www\.)\S+", re.I)),
    ("phone", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("order", re.compile(
        r"\b(?:order|ord|awb|tracking)\s*(?:id|no\.?|number|#)?\s*[:#-]?\s*"
        r"(?=[A-Z0-9-]*\d)[A-Z0-9-]{6,}\b",  # real IDs contain a digit
        re.I,
    )),
    ("pincode_addr", re.compile(r"\b(?:flat|house|h\.?no|plot)\s*(?:no\.?)?\s*\d+[^.,\n]*", re.I)),
]
TOKENS = {"email": "[email removed]", "upi": "[payment id removed]", "link": "[link removed]",
          "phone": "[phone removed]", "order": "[order id removed]",
          "pincode_addr": "[address removed]"}  # fmt: skip


def redact(text: str) -> tuple[str, list[str]]:
    """Return redacted text and the kinds of personal data found."""
    found = []
    out = text
    for kind, pat in PATTERNS:
        if pat.search(out):
            found.append(kind)
            out = pat.sub(TOKENS[kind], out)
    return out, found


def has_pii(text: str) -> bool:
    return any(pat.search(text) for _, pat in PATTERNS)


def attribution(author: str, consent: bool, verified: bool) -> str:
    name = re.sub(r"[^A-Za-z .'-]", "", author or "").strip()
    if consent and name:
        parts = name.split()
        if len(parts) == 1:
            return parts[0].title()
        return f"{parts[0].title()} {parts[-1][0].upper()}."
    return "Verified buyer" if verified else "A customer"
