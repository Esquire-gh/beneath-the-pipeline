#!/usr/bin/env python3
"""Module 14 — What vectors can't answer.  YOUR WORK GOES HERE.

    python exercises/14-what-vectors-cant-answer/starter.py
    python exercises/14-what-vectors-cant-answer/verify.py

Every fact in this corpus is known, because the generator wrote it. So both
kinds of question can be graded exactly:

    descriptive   "which invoice from Acme includes a servo motor?"
                  the answer is a document — which is what a retriever returns
    aggregate     "how many invoices exceed $10,000?"
                  the answer is a number nobody wrote down

Needs: pymupdf, sentence-transformers, numpy. sqlite3 is in the standard library.
"""
import argparse
import json
import math
import re
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import human_time, normalized, rule   # noqa: E402

INVOICES = REPO / "data" / "invoices"
TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# --------------------------------------------------------------------------
# 1 · parse the PDFs — the pipeline's only input
# --------------------------------------------------------------------------

def parse_invoices() -> dict[str, str]:
    import fitz
    out = {}
    for path in sorted((INVOICES / "pdf").glob("*.pdf")):
        with fitz.open(path) as doc:
            out[path.stem] = "\n".join(page.get_text() for page in doc)
    return out



# ==========================================================================
# TODO 1 — design a schema, and write the extractor that fills it
# ==========================================================================
#
# You are the format author now. Decide what a record holds. Everything you
# leave out is a question the table can never answer later.
#
# Return a dict with at least: invoice_id, vendor, customer, issue_date,
# terms, purchase_order, total, status, and a list of line_items where each
# item has description, quantity, uom, unit_price and amount.
#
# The text you are parsing looks like this (PyMuPDF puts each drawn run on
# its own line, which is module 5's lesson made useful):
#
#     Contoso Manufacturing
#     4 Kiln Street, Pittsburgh, PA 15201
#     INVOICE
#     INV-10000
#     ...
#     Total due
#     $5,287.86
#
# Grade yourself against ground_truth.json before going further. An argument
# about what retrieval cannot do is worthless if the data was mangled on the
# way in.

def extract_record(text: str, vendors: list[str], customers: list[str]) -> dict:
    # TODO
    ...


# ==========================================================================
# TODO 2 — load the records into SQLite
# ==========================================================================
#
# Two tables: invoices, and line_items keyed by invoice_id. Return the
# connection. sqlite3.connect(":memory:") is fine.

def build_sqlite(records: list[dict]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    # TODO: CREATE TABLE, then INSERT
    ...
    return conn


# ==========================================================================
# TODO 3 — answer the aggregate questions with SQL
# ==========================================================================
#
# ground_truth.json gives every aggregate question a `sql_hint` naming the
# operation it wants. Match the question and run the query.
#
# Return the answer, or None if you do not handle that question shape.

def answer_with_sql(conn: sqlite3.Connection, question: dict):
    # TODO
    ...


# ==========================================================================
# TODO 4 — evidence coverage
# ==========================================================================
#
# How do you grade a RETRIEVER on "how many invoices exceed $10,000" without
# inventing an answer for it?
#
# Measure what fraction of the documents needed to answer actually came back.
# To count invoices over a threshold you have to see all of them; a top-4
# retrieval can show you four. That ratio is the honest number, and it needs
# no language model.

def evidence_coverage(retrieved: list[str], required: list[str]) -> float:
    # TODO
    ...


# ==========================================================================
# TODO 5 — the router
# ==========================================================================
#
# Return "sql" or "retrieval". Rules, not a model — a dozen words is enough,
# and then you measure how often they are right.
#
# Note which way your router errs. Sending a descriptive question to SQL loses
# a good answer; sending an aggregate to the retriever produces a confident
# wrong one. Those are not equally bad.

def route(question: str) -> str:
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def main() -> None:
    truth_path = INVOICES / "ground_truth.json"
    if not truth_path.exists():
        sys.exit("missing invoices — run: python data/fetch.py --only invoices")
    truth = json.loads(truth_path.read_text())
    invoices = truth["invoices"]
    questions = truth["questions"]
    vendors = sorted({r["vendor"] for r in invoices})
    customers = sorted({r["customer"] for r in invoices})

    rule("1 · parse and extract")
    docs = parse_invoices()
    records = [extract_record(t, vendors, customers) for t in docs.values()]
    records = [r for r in records if r]
    by_id = {r["invoice_id"]: r for r in invoices}
    correct = sum(1 for r in records
                  if r.get("invoice_id") in by_id
                  and r.get("total") is not None
                  and abs(r["total"] - by_id[r["invoice_id"]]["total"]) < 0.005)
    print(f"  {len(records)} records, {correct} with the right total")

    rule("2 · both stores")
    conn = build_sqlite(records)
    print("  SQLite ready" if conn else "  (build_sqlite returned nothing)")

    rule("3 · aggregate questions")
    hits = 0
    for q in questions["aggregate"][:8]:
        got = answer_with_sql(conn, q)
        ok = got is not None and (
            abs(got - q["answer"]) < 0.02
            if isinstance(q["answer"], (int, float)) else got == q["answer"])
        hits += ok
        print(f"  {q['question'][:54]:<56} true {q['answer']!s:>12}  "
              f"yours {got!s:>12}  {'ok' if ok else 'MISS'}")

    rule("4 · the router")
    for q in questions["descriptive"][:2] + questions["aggregate"][:2]:
        print(f"  {route(q['question'])!s:<10} {q['question'][:60]}")


if __name__ == "__main__":
    main()
