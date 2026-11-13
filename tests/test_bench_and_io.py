import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from proofpost.cli import main
from proofpost.evaluate import evaluate
from proofpost.export import workbook
from proofpost.pipeline import run
from proofpost.synth import TODAY, generate

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("phrasing,seed", [("dev", 3), ("held_out", 4)])
def test_benchmark_zero_problems(phrasing, seed):
    r = evaluate(120, seed, phrasing)
    assert r["proofpost"]["posts_with_any_problem"] == 0
    assert r["naive"]["posts_with_any_problem"] > 100
    assert r["proofpost"]["eligible_coverage"] >= 0.9


def test_workbook_sheets():
    res = run([x.review for x in generate(24, 2)], today=TODAY)
    wb = load_workbook(io.BytesIO(workbook(res)))
    assert wb.sheetnames == ["Approval queue", "Not used (and why)", "Summary"]
    assert wb["Approval queue"].max_row == len(res.posts) + 1


def test_cli_on_sample_export(tmp_path, capsys):
    out = tmp_path / "q.csv"
    code = main([str(ROOT / "data/samples/reviews_judgeme.csv"), "--brand",
                 str(ROOT / "config/brand.example.yaml"), "--out", str(out), "--json"])  # fmt: skip
    s = json.loads(capsys.readouterr().out)
    assert code == 0 and out.exists() and s["posts_ready_for_approval"] > 0


def test_n8n_workflow_is_importable_shape():
    wf = json.loads((ROOT / "workflows/proofpost-weekly.json").read_text())
    names = [n["name"] for n in wf["nodes"]]
    assert len(names) == len(set(names))
    for n in wf["nodes"]:
        assert {"id", "name", "type", "typeVersion", "position", "parameters"} <= set(n)
    for src, conn in wf["connections"].items():
        assert src in names
        for branch in conn["main"]:
            assert all(t["node"] in names for t in branch)
    http = next(n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.httpRequest")
    assert http["parameters"]["url"].endswith("/v1/posts")
    assert all("credentials" not in n for n in wf["nodes"])  # users attach their own


def test_api():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from proofpost.api import app

    c = TestClient(app)
    rows = [{"review": x.review.text, "rating": x.review.rating, "author": x.review.author}
            for x in generate(24, 5)]  # fmt: skip
    r = c.post("/v1/posts", json={"reviews": rows, "brand": {"name": "Brewly"}})
    body = r.json()
    assert r.status_code == 200 and body["summary"]["reviews_in"] == 24 and body["posts"]
    assert c.post("/v1/posts", json={"reviews": [{"foo": 1}]}).status_code == 422
    assert c.post("/v1/posts", json={"reviews": []}).status_code == 422


def test_streamlit_app():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception and at.metric[0].value == "36"
