from datetime import date

import pytest

from proofpost.brand import Brand
from proofpost.compose import LIMITS, compose, hashtag_count
from proofpost.ingest import from_csv
from proofpost.models import Platform, Review
from proofpost.pipeline import run
from proofpost.quote import best_quote
from proofpost.redact import attribution, has_pii, redact
from proofpost.screen import screen

TODAY = date(2026, 11, 13)


def rv(i, text, rating=5, author="Priya Sharma", consent=False, verified=True):
    return Review(id=str(i), text=text, rating=rating, author=author, consent_to_name=consent,
                  verified=verified)  # fmt: skip


@pytest.mark.parametrize("text,kind", [
    ("call 9876543210 anytime", "phone"),
    ("whatsapp +91 98765 43210", "phone"),
    ("mail me at a.b@gmail.com", "email"),
    ("paid with neha@okaxis", "email"),  # caught as email first; never posted either way
    ("Order ID: OD45127789", "order"),
    ("see www.example.com", "link"),
])
def test_redaction_catches_indian_personal_data(text, kind):
    out, found = redact(text)
    assert found and not has_pii(out)


def test_attribution_needs_consent():
    assert attribution("Priya Sharma", True, True) == "Priya S."
    assert attribution("Priya Sharma", False, True) == "Verified buyer"
    assert attribution("", False, False) == "A customer"


def test_screen_reasons():
    reviews = [
        rv(1, "I received this for free in exchange for an honest review. Lovely texture."),
        rv(2, "Lovely aroma but the second pack arrived damaged and I was disappointed."),
        rv(3, "Nice."),
        rv(4, "Lovely packaging and the taste is smooth, would order again soon.", rating=3),
        rv(5, "BEST PRODUCT EVER BUY NOW!!!!!!! AMAZING"),
        rv(6, "The quality is great and delivery was quick, arrived in two days."),
        rv(7, "The quality is great and delivery was quick, arrived in two days."),
    ]
    ok, rejected = screen(reviews)
    reasons = {r.review_id: " ".join(r.reasons) for r in rejected}
    assert [r.id for r in ok] == ["6"]
    assert "incentivised" in reasons["1"] and "negative" in reasons["2"]
    assert "short" in reasons["3"] and "rating" in reasons["4"]
    assert "spam" in reasons["5"] and "duplicate" in reasons["7"]


def test_quote_is_verbatim_and_skips_claim_sentences():
    text = "It cured my acne in a week. The texture is lightweight and absorbs quickly."
    q = best_quote(text)
    assert q and q.text in text and "cured" not in q.text and "results" in q.aspects


def test_quote_none_when_only_claims():
    assert best_quote("My eczema healed completely. 100% safe, guaranteed.") is None


def test_compose_respects_platform_limits():
    b = Brand(hashtags=["#A", "#B", "#C", "#D", "#E", "#F"])
    q = "Delivery was quick and the packaging was beautiful, perfect for gifting to my family."
    for p in Platform:
        t = compose(p, q, "Verified buyer", 5, ["delivery"], b, "seed")
        assert f"“{q}”" in t and len(t) <= LIMITS[p]
    assert hashtag_count(compose(Platform.INSTAGRAM, q, "x", 5, ["delivery"], b, "s")) <= 5
    assert hashtag_count(compose(Platform.LINKEDIN, q, "x", 5, ["delivery"], b, "s")) <= 3


def test_pipeline_end_to_end_never_leaks():
    reviews = [
        rv(1, "Ordered the kit for my office. The aroma is rich and delivery came in 2 days. "
              "Call me on 9876543210 for details."),
        rv(2, "Stitching is neat and the fit is perfect after 10 washes.", author="Meera Iyer",
           consent=True),
        rv(3, "My thyroid levels improved after using it."),
    ]
    res = run(reviews, Brand(name="Brewly"), today=TODAY)
    texts = " ".join(p.text for p in res.posts)
    assert "9876543210" not in texts and "Sharma" not in texts and "Priya" not in texts
    assert "Meera I." in texts and "Iyer" not in texts
    assert "thyroid" not in texts
    assert {r.review_id for r in res.rejected} == {"3"}
    assert "claims" in res.rejected[0].reasons[0]
    assert all(all(p.checks.values()) for p in res.posts)
    assert all(p.status == "pending_approval" for p in res.posts)


def test_one_post_per_customer_and_max_posts():
    reviews = [rv(i, f"The quality is excellent and delivery took {i + 2} days, packed well.",
                  author=f"Customer {i}") for i in range(12)]  # fmt: skip
    reviews.append(rv(99, "Lovely aroma and smooth taste every morning for 3 weeks.",
                      author="Customer 0"))
    res = run(reviews, Brand(max_posts=5), platforms=(Platform.X,), today=TODAY)
    assert len(res.posts) == 5
    assert len({p.review_id for p in res.posts}) == 5


def test_banned_words_block_posts():
    b = Brand(cta="Grab this cheap deal!", banned_words=["cheap"])
    res = run([rv(1, "The quality is excellent and it feels premium in hand, love it.")], b,
              platforms=(Platform.INSTAGRAM,), today=TODAY)  # fmt: skip
    assert not res.posts and res.blocked_posts[0]["failed"] == ["no_banned_words"]


def test_ingest_google_and_judgeme_columns():
    google = ("reviewId,comment,starRating,reviewer,createTime\n"
              "A1,Great value for money,FIVE,Ann,2026-10-01T10:00:00\n")
    reviews, skipped = from_csv(google, "google")
    assert reviews[0].rating == 5 and reviews[0].id == "A1" and reviews[0].review_date
    judge = ("review_id,title,body,rating,reviewer_name,verified,can_feature\n"
             "7,Hi,Fits well and comfy,4,Raj K,Verified,yes\n8,,,5,X,,\n")  # fmt: skip
    reviews, skipped = from_csv(judge)
    assert reviews[0].verified and reviews[0].consent_to_name and skipped == 1
    with pytest.raises(ValueError):
        from_csv("foo,bar\n1,2\n")
