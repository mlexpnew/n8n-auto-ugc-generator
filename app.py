"""ProofPost demo (Streamlit): upload a reviews export, get posts ready for approval.

    pip install -e ".[app]" && streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from proofpost.brand import Brand, load  # noqa: E402
from proofpost.export import workbook  # noqa: E402
from proofpost.ingest import from_csv  # noqa: E402
from proofpost.pipeline import run  # noqa: E402

ROOT = Path(__file__).parent
st.set_page_config(page_title="ProofPost", page_icon="💬", layout="wide")
st.title("ProofPost")
st.caption("Real customer reviews in. Compliant, on-brand posts out, every quote word for word. "
           "Nothing is published: you approve every post.")  # fmt: skip

base = load(ROOT / "config" / "brand.example.yaml")
with st.sidebar:
    st.subheader("Brand voice")
    name = st.text_input("Brand", base.name)
    tone = st.selectbox("Tone", ["warm", "crisp", "playful"], index=0)
    emoji = st.toggle("Emoji on Instagram", base.emoji)
    tags = st.text_input("Hashtags", " ".join(base.hashtags))
    cta = st.text_input("Instagram call to action", base.cta)
brand = Brand(**{**base.model_dump(), "name": name, "tone": tone, "emoji": emoji,
                 "hashtags": tags.split(), "cta": cta})  # fmt: skip

up = st.file_uploader("Reviews export (CSV from Google, Shopify review apps, Amazon or a sheet)",
                      type="csv")  # fmt: skip
data = up.getvalue() if up else (ROOT / "data" / "samples" / "reviews_judgeme.csv").read_bytes()
if not up:
    st.info("Showing 36 sample reviews with real-world traps: phone numbers, health claims, "
            "free-for-review posts, mixed reviews, duplicates. Upload your own export anytime.")

reviews, skipped = from_csv(data)
res = run(reviews, brand)
s = res.summary()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Reviews in", s["reviews_in"])
c2.metric("Posts ready", s["posts_ready_for_approval"])
c3.metric("Held back", s["reviews_rejected"])
c4.metric("Personal data removed", s["reviews_with_personal_data_redacted"])

tab_posts, tab_rejected = st.tabs(["Posts for approval", "Not used, and why"])
with tab_posts:
    for platform in ("instagram", "linkedin", "x"):
        ps = [p for p in res.posts if p.platform.value == platform]
        st.subheader(f"{platform.title()} ({len(ps)})")
        for p in ps[:6]:
            with st.container(border=True):
                st.text(p.text)
                st.caption(f"Review {p.review_id} · {', '.join(p.aspects) or 'general'} · "
                           f"all {len(p.checks)} checks passed")  # fmt: skip
with tab_rejected:
    text_by_id = {r.id: r.text for r in reviews}
    rows = [{"review": text_by_id.get(r.review_id, "")[:140], "why not used": "; ".join(r.reasons)}
            for r in res.rejected]  # fmt: skip
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.download_button("Download approval queue (Excel)", workbook(res), "approval_queue.xlsx")
