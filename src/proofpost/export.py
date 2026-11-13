"""Approval queue a social media manager can work through, plus a rejection log."""

from __future__ import annotations

import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .pipeline import Result

QUEUE_COLUMNS = ["platform", "post_text", "quote", "attribution", "rating", "aspects",
                 "review_id", "score", "status", "scheduled_for", "approved_by"]  # fmt: skip


def queue_rows(res: Result) -> list[dict]:
    return [{
        "platform": p.platform.value, "post_text": p.text, "quote": p.quote,
        "attribution": p.attribution, "rating": p.rating, "aspects": ", ".join(p.aspects),
        "review_id": p.review_id, "score": p.score, "status": p.status,
        "scheduled_for": "", "approved_by": "",
    } for p in res.posts]  # fmt: skip


def queue_csv(res: Result) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=QUEUE_COLUMNS)
    w.writeheader()
    w.writerows(queue_rows(res))
    return buf.getvalue()


def workbook(res: Result) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Approval queue"
    ws.append(QUEUE_COLUMNS)
    for row in queue_rows(res):
        ws.append([row[c] for c in QUEUE_COLUMNS])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="4C1D95")
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=3):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for col, width in zip("ABCDEFGHIJK", (11, 60, 45, 16, 7, 18, 10, 7, 17, 14, 14), strict=True):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    rj = wb.create_sheet("Not used (and why)")
    rj.append(["review_id", "reasons"])
    for c in rj[1]:
        c.font = Font(bold=True)
    for r in res.rejected:
        rj.append([r.review_id, "; ".join(r.reasons)])
    rj.column_dimensions["A"].width = 14
    rj.column_dimensions["B"].width = 90

    sm = wb.create_sheet("Summary")
    for k, v in res.summary().items():
        sm.append([k.replace("_", " "), v])
    sm.column_dimensions["A"].width = 40
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
