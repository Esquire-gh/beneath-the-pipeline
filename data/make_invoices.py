#!/usr/bin/env python3
"""Generate module 14's invoice corpus, with ground truth.

Module 14 asks whether similarity search can answer "how many invoices exceed
$10,000" and "what is the total across all invoices from Acme Corp". Grading
those answers needs a corpus where every fact is known — not estimated, not
annotated afterwards, but known, because the generator wrote it.

So this writes two things from the same source of truth:

    data/invoices/pdf/INV-####.pdf     what the pipeline sees
    data/invoices/ground_truth.json    what the answer actually is

The PDFs are the only input to the pipeline. The JSON is only ever used to
score it.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent

VENDORS = [
    ("Acme Corp", "1450 Foundry Road, Cleveland, OH 44113"),
    ("Northwind Traders", "88 Harbour Lane, Seattle, WA 98104"),
    ("Contoso Manufacturing", "4 Kiln Street, Pittsburgh, PA 15201"),
    ("Globex Industrial", "220 Vector Way, Austin, TX 78702"),
    ("Initech Systems", "919 Cubicle Drive, San Jose, CA 95110"),
    ("Umbra Logistics", "7 Dock Terrace, Newark, NJ 07102"),
    ("Stark Components", "1 Tower Plaza, Long Island City, NY 11101"),
    ("Wayne Fabrication", "300 Cavern Road, Gotham, NJ 07030"),
]

CUSTOMERS = [
    "Blue Harbor Robotics", "Ridgeline Analytics", "Cascade Foundry",
    "Meridian Freight", "Pinewood Instruments",
]

CATALOG = [
    ("Steel bracket, 40mm", 12.50, "ea"),
    ("Hex bolt M8 (box of 200)", 34.00, "box"),
    ("Aluminium extrusion, 2m", 78.25, "ea"),
    ("Bearing assembly, sealed", 145.00, "ea"),
    ("Hydraulic hose, 3m", 96.40, "ea"),
    ("Servo motor, 400W", 412.00, "ea"),
    ("Control board rev. C", 1_240.00, "ea"),
    ("Cable harness, custom", 268.75, "ea"),
    ("Machining service", 155.00, "hr"),
    ("Powder coating", 88.00, "unit"),
    ("Freight, palletised", 320.00, "shipment"),
    ("Calibration service", 210.00, "hr"),
    ("Gasket set, nitrile", 44.90, "set"),
    ("Linear rail, 1m", 187.30, "ea"),
    ("Stepper driver module", 63.15, "ea"),
]

TERMS = ["Net 30", "Net 45", "Net 60", "Due on receipt"]
TAX_RATE = 0.0725


def _money(x: float) -> str:
    return f"${x:,.2f}"


def build_records(n: int, seed: int = 20260728) -> list[dict]:
    rng = random.Random(seed)
    start = date(2025, 1, 6)
    records = []
    for i in range(n):
        vendor, vendor_addr = rng.choice(VENDORS)
        # Acme appears more often, so aggregate queries about it have weight.
        if rng.random() < 0.22:
            vendor, vendor_addr = VENDORS[0]

        issued = start + timedelta(days=rng.randrange(0, 400))
        n_lines = rng.choices([1, 2, 3, 4, 5, 6, 7], [3, 6, 8, 8, 6, 4, 2])[0]
        items = []
        for _ in range(n_lines):
            desc, unit, uom = rng.choice(CATALOG)
            qty = rng.choices([1, 2, 3, 5, 8, 12, 25, 40],
                              [6, 6, 5, 4, 3, 3, 2, 1])[0]
            # a little price drift, so totals are not guessable from the catalog
            unit_price = round(unit * rng.uniform(0.94, 1.09), 2)
            items.append({
                "description": desc,
                "uom": uom,
                "quantity": qty,
                "unit_price": unit_price,
                "amount": round(qty * unit_price, 2),
            })
        subtotal = round(sum(it["amount"] for it in items), 2)
        tax = round(subtotal * TAX_RATE, 2)
        total = round(subtotal + tax, 2)

        records.append({
            "invoice_id": f"INV-{10_000 + i}",
            "vendor": vendor,
            "vendor_address": vendor_addr,
            "customer": rng.choice(CUSTOMERS),
            "issue_date": issued.isoformat(),
            "due_date": (issued + timedelta(
                days={"Net 30": 30, "Net 45": 45, "Net 60": 60,
                      "Due on receipt": 0}[(t := rng.choice(TERMS))])).isoformat(),
            "terms": t,
            "purchase_order": f"PO-{rng.randrange(50_000, 99_999)}",
            "currency": "USD",
            "line_items": items,
            "subtotal": subtotal,
            "tax_rate": TAX_RATE,
            "tax": tax,
            "total": total,
            "status": rng.choices(["paid", "open", "overdue"], [6, 3, 1])[0],
        })
    return records


def render_invoice(rec: dict, path: Path) -> None:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    w, h = LETTER
    c = canvas.Canvas(str(path), pagesize=LETTER)
    c.setTitle(f"{rec['vendor']} — {rec['invoice_id']}")
    left, right = 0.85 * inch, w - 0.85 * inch
    y = h - 0.95 * inch

    c.setFont("Helvetica-Bold", 17)
    c.drawString(left, y, rec["vendor"])
    c.setFont("Helvetica", 8.5)
    c.drawString(left, y - 13, rec["vendor_address"])

    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(right, y, "INVOICE")
    c.setFont("Helvetica", 9)
    c.drawRightString(right, y - 15, rec["invoice_id"])

    y -= 45
    c.setLineWidth(0.8)
    c.line(left, y, right, y)

    y -= 20
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(left, y, "BILL TO")
    c.drawString(left + 2.9 * inch, y, "ISSUED")
    c.drawString(left + 4.1 * inch, y, "DUE")
    c.drawString(left + 5.2 * inch, y, "TERMS")
    c.setFont("Helvetica", 9.5)
    c.drawString(left, y - 14, rec["customer"])
    c.drawString(left + 2.9 * inch, y - 14, rec["issue_date"])
    c.drawString(left + 4.1 * inch, y - 14, rec["due_date"])
    c.drawString(left + 5.2 * inch, y - 14, rec["terms"])
    c.setFont("Helvetica", 8.5)
    c.drawString(left, y - 27, f"Purchase order {rec['purchase_order']}")

    y -= 52
    cols = [left, left + 3.5 * inch, left + 4.35 * inch,
            left + 5.25 * inch, right]
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(cols[0], y, "DESCRIPTION")
    c.drawRightString(cols[1], y, "QTY")
    c.drawRightString(cols[2], y, "UOM")
    c.drawRightString(cols[3], y, "UNIT PRICE")
    c.drawRightString(cols[4], y, "AMOUNT")
    y -= 5
    c.line(left, y, right, y)

    c.setFont("Helvetica", 9.5)
    for it in rec["line_items"]:
        y -= 17
        c.drawString(cols[0], y, it["description"])
        c.drawRightString(cols[1], y, str(it["quantity"]))
        c.drawRightString(cols[2], y, it["uom"])
        c.drawRightString(cols[3], y, _money(it["unit_price"]))
        c.drawRightString(cols[4], y, _money(it["amount"]))

    y -= 10
    c.line(left + 3.5 * inch, y, right, y)
    for label, value, bold in (
        ("Subtotal", rec["subtotal"], False),
        (f"Sales tax ({rec['tax_rate'] * 100:.2f}%)", rec["tax"], False),
        ("Total due", rec["total"], True),
    ):
        y -= 17
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if bold else 9.5)
        c.drawRightString(cols[3], y, label)
        c.drawRightString(cols[4], y, _money(value))

    y -= 34
    c.setFont("Helvetica", 8.5)
    c.drawString(left, y, f"Status: {rec['status']}.  "
                          f"Remit in {rec['currency']}.  "
                          f"Reference {rec['invoice_id']} on payment.")
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(left, 0.7 * inch,
                 "Generated for Beneath the Pipeline, module 14. "
                 "Not a real invoice.")
    c.showPage()
    c.save()


# --------------------------------------------------------------------------
# the question sets module 14 scores against
# --------------------------------------------------------------------------

def build_question_sets(records: list[dict]) -> dict:
    """Two sets of questions, and the true answer to every one of them.

    Descriptive questions are about what a document says. Aggregate questions
    are about what the whole corpus adds up to. The corpus contains the facts
    for both; only one kind survives a similarity search.
    """
    by_vendor: dict[str, list[dict]] = {}
    for r in records:
        by_vendor.setdefault(r["vendor"], []).append(r)

    aggregate = []
    for vendor, rs in sorted(by_vendor.items()):
        aggregate.append({
            "id": f"agg-total-{vendor.split()[0].lower()}",
            "question": f"What is the total across all invoices from {vendor}?",
            "kind": "sum",
            "answer": round(sum(r["total"] for r in rs), 2),
            "sql_hint": "SELECT SUM(total) FROM invoices WHERE vendor = ?",
        })
        aggregate.append({
            "id": f"agg-count-{vendor.split()[0].lower()}",
            "question": f"How many invoices did {vendor} issue?",
            "kind": "count",
            "answer": len(rs),
            "sql_hint": "SELECT COUNT(*) FROM invoices WHERE vendor = ?",
        })

    for threshold in (5_000, 10_000, 20_000):
        aggregate.append({
            "id": f"agg-over-{threshold}",
            "question": f"How many invoices exceed ${threshold:,}?",
            "kind": "count",
            "answer": sum(1 for r in records if r["total"] > threshold),
            "sql_hint": "SELECT COUNT(*) FROM invoices WHERE total > ?",
        })

    largest = max(records, key=lambda r: r["total"])
    aggregate += [
        {"id": "agg-largest", "kind": "lookup",
         "question": "Which invoice has the largest total?",
         "answer": largest["invoice_id"],
         "sql_hint": "SELECT invoice_id FROM invoices ORDER BY total DESC LIMIT 1"},
        {"id": "agg-grand-total", "kind": "sum",
         "question": "What is the total value of every invoice in the corpus?",
         "answer": round(sum(r["total"] for r in records), 2),
         "sql_hint": "SELECT SUM(total) FROM invoices"},
        {"id": "agg-mean", "kind": "sum",
         "question": "What is the average invoice total?",
         "answer": round(sum(r["total"] for r in records) / len(records), 2),
         "sql_hint": "SELECT AVG(total) FROM invoices"},
        {"id": "agg-overdue", "kind": "count",
         "question": "How many invoices are overdue?",
         "answer": sum(1 for r in records if r["status"] == "overdue"),
         "sql_hint": "SELECT COUNT(*) FROM invoices WHERE status = 'overdue'"},
        {"id": "agg-servo-qty", "kind": "sum",
         "question": "How many servo motors were ordered in total?",
         "answer": sum(it["quantity"] for r in records for it in r["line_items"]
                       if it["description"].startswith("Servo motor")),
         "sql_hint": "SELECT SUM(quantity) FROM line_items "
                     "WHERE description LIKE 'Servo motor%'"},
    ]

    # Descriptive questions name one document and ask what it says. The right
    # answer is a document id, which is exactly what a retriever returns.
    rng = random.Random(31337)
    descriptive = []
    for r in rng.sample(records, k=40):
        item = max(r["line_items"], key=lambda it: it["amount"])
        descriptive.append({
            "id": f"desc-{r['invoice_id']}",
            "question": f"Which invoice from {r['vendor']} to {r['customer']} "
                        f"includes {item['description'].lower()}?",
            "kind": "retrieval",
            "answer": r["invoice_id"],
        })
    for r in rng.sample(records, k=20):
        descriptive.append({
            "id": f"desc-po-{r['invoice_id']}",
            "question": f"What did {r['vendor']} bill on purchase order "
                        f"{r['purchase_order']}?",
            "kind": "retrieval",
            "answer": r["invoice_id"],
        })

    return {"descriptive": descriptive, "aggregate": aggregate}


def generate_invoices(out_dir: Path, n: int = 300) -> dict:
    pdf_dir = out_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    records = build_records(n)
    for i, rec in enumerate(records):
        render_invoice(rec, pdf_dir / f"{rec['invoice_id']}.pdf")
        if (i + 1) % 50 == 0:
            print(f"    {i + 1}/{n} invoices")

    questions = build_question_sets(records)
    truth = {
        "invoices": records,
        "questions": questions,
        "note": "Generated by data/make_invoices.py. The PDFs are the only "
                "input to the pipeline; this file is only used for scoring.",
    }
    (out_dir / "ground_truth.json").write_text(
        json.dumps(truth, indent=2) + "\n")

    total = sum(r["total"] for r in records)
    print(f"  {n} invoices, {len(questions['descriptive'])} descriptive and "
          f"{len(questions['aggregate'])} aggregate questions")
    print(f"  corpus value {_money(total)} — a number no retriever will find")
    return truth


if __name__ == "__main__":
    generate_invoices(HERE / "invoices", n=300)
