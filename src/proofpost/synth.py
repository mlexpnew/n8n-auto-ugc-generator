"""Synthetic review benchmark with labelled traps.

Real customer reviews cannot be published, so reviews are assembled from praise sentences
plus the traps that cause real incidents when brands repost reviews by hand:

    pii            phone, email, UPI id or order number in the text
    claim          a health or absolute claim the brand could not substantiate
    claim_only     the only quotable content is a claim: must not be used at all
    incentivised   free product / review-for-discount, undisclosed
    negative       5 stars, but a bad experience inside
    duplicate      the same text posted by several "customers"
    low_rating     3 stars or fewer
    short          too short to quote ("Nice.")
    spam           shouting, repeated characters

Two phrasing sets: "dev" (used while building the rules) and "held_out" (written
separately, never used for tuning) so the benchmark also measures generalisation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from .models import Review

TODAY = date(2026, 11, 13)

FIRST = ["Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Arjun", "Kavya", "Rahul", "Divya",
         "Karthik", "Meera", "Imran", "Fatima", "Joseph", "Sara", "Harpreet", "Neha", "Aditya"]
LAST = ["Sharma", "Iyer", "Reddy", "Khan", "Das", "Nair", "Singh", "Patel", "Menon", "Gupta",
        "Fernandes", "Bose", "Kulkarni", "Hussain"]  # fmt: skip

PHRASES = {
    "dev": {
        "praise": [
            "The quality is excellent and it feels premium in hand.",
            "Delivery was quick, it arrived in 2 days.",
            "Packaging was beautiful, perfect for gifting.",
            "Great value for the price, I would buy again.",
            "It fits perfectly and is very comfortable all day.",
            "The aroma is fresh and the taste is smooth every morning.",
            "Customer support was helpful and replied within an hour.",
            "Lovely lightweight texture that absorbs quickly.",
            "I have used it every day for 3 months and still love it.",
            "Stitching is neat and the finish looks amazing.",
        ],
        "claim": [
            "It cured my acne in a week.",
            "Lost 5 kg in a month using this.",
            "No side effects at all, 100% safe.",
            "Best in India, guaranteed.",
            "My eczema healed completely.",
        ],
        "pii": [
            "Call me on 9876543210 for details.",
            "Mail me at priya.s@gmail.com if you have questions.",
            "Order ID: OD45127789 was packed well.",
            "Paid via rahul@okaxis without any issue.",
        ],
        "incentivised": [
            "I received this for free in exchange for an honest review.",
            "Got a discount for writing this review.",
        ],
        "negative": [
            "But delivery was delayed by a week, disappointed.",
            "Sadly it broke after two weeks.",
            "The second one I ordered arrived damaged.",
        ],
        "short": ["Nice.", "Good product", "Loved it!"],
        "spam": ["BEST PRODUCT EVER BUY NOW!!!!!!!", "wowwwwwwww amazinggggggg"],
    },
    "held_out": {
        "praise": [
            "Honestly the build feels solid and well made.",
            "Shipping was super fast, reached Pune overnight.",
            "Came in a gorgeous box, my sister loved the unboxing.",
            "Totally worth the money compared to other brands.",
            "Sizing chart was accurate and it is so comfortable.",
            "Rich flavour, my whole family drinks it after dinner now.",
            "Their team sorted my exchange in a day, very helpful.",
            "Non-greasy and leaves my skin soft.",
            "Been using it since January and it still looks new.",
            "The colour is exactly like the photos, superb finish.",
        ],
        "claim": [
            "My thyroid levels improved after using it.",
            "Doctors recommend it, mine did too.",
            "It permanently removed my dark spots.",
            "Results are instant and permanent.",
            "My PCOS symptoms are better now.",
        ],
        "pii": [
            "WhatsApp me at +91 98765 43210.",
            "My email is neha.k@yahoo.in.",
            "Tracking number AWB99812345 updated quickly.",
            "UPI neha.k@ybl worked fine.",
        ],
        "incentivised": [
            "They sent this as a free sample in exchange for a review.",
            "Got cashback after posting a review, but genuinely like it.",
        ],
        "negative": [
            "Only issue: the lid leaked in transit.",
            "Customer care was rude when I called.",
            "Gave me a rash on day two though.",
        ],
        "short": ["Superb", "ok ok", "Fab!"],
        "spam": ["DM ME FOR CHEAP DEALS!!!!!!", "goooooood product buy fast"],
    },
}

KINDS = ["clean", "clean", "clean", "pii", "claim", "claim_only", "incentivised", "negative",
         "duplicate", "low_rating", "short", "spam"]  # fmt: skip


@dataclass
class Labelled:
    review: Review
    kind: str
    eligible: bool
    pii_values: list[str] = field(default_factory=list)  # strings that must never be posted
    claim_sentences: list[str] = field(default_factory=list)


def generate(n: int = 240, seed: int = 7, phrasing: str = "dev") -> list[Labelled]:
    P = PHRASES[phrasing]
    rng = random.Random(seed)
    out: list[Labelled] = []
    dup_text = None
    # Unique customers and texts, so only the designed duplicates look duplicated
    names = [(f, la) for f in FIRST for la in LAST]
    rng.shuffle(names)
    used_texts: set[str] = set()
    for i in range(n):
        kind = KINDS[i % len(KINDS)]
        first, last = names[i % len(names)]
        praise = rng.sample(P["praise"], rng.randint(2, 3))
        for _ in range(20):
            if " ".join(praise) not in used_texts:
                break
            praise = rng.sample(P["praise"], rng.randint(2, 4))
        rating, eligible, pii, claims = 5.0, True, [], []
        if kind == "pii":
            p = rng.choice(P["pii"])
            praise.insert(rng.randint(0, len(praise)), p)
            pii = [tok for tok in p.replace(",", " ").split()
                   if any(c.isdigit() for c in tok) and len(tok) >= 5 or "@" in tok]  # fmt: skip
            pii = [t.strip(".") for t in pii]
        elif kind == "claim":
            c = rng.choice(P["claim"])
            praise.insert(rng.randint(0, len(praise)), c)
            claims = [c]
        elif kind == "claim_only":
            c = rng.choice(P["claim"])
            praise, claims, eligible = [c], [c], False
        elif kind == "incentivised":
            praise.insert(0, rng.choice(P["incentivised"]))
            eligible = False
        elif kind == "negative":
            praise.append(rng.choice(P["negative"]))
            eligible = False
        elif kind == "duplicate":
            if dup_text is None:
                dup_text = " ".join(praise)
                kind = "clean"  # first copy is legitimate
            else:
                eligible = False
        elif kind == "low_rating":
            rating, eligible = float(rng.choice([1, 2, 3])), False
        elif kind == "short":
            praise, eligible = [rng.choice(P["short"])], False
        elif kind == "spam":
            praise, eligible = [rng.choice(P["spam"])], False
        text = dup_text if kind == "duplicate" else " ".join(praise)
        used_texts.add(text)
        out.append(Labelled(
            review=Review(
                id=f"r{i:04d}", text=text, rating=rating, author=f"{first} {last}",
                source="synthetic", product="", verified=rng.random() < 0.7,
                consent_to_name=rng.random() < 0.3,
                review_date=TODAY - timedelta(days=rng.randint(1, 180)),
            ),
            kind=kind, eligible=eligible, pii_values=pii, claim_sentences=claims,
        ))  # fmt: skip
    return out
