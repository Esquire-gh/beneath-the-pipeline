#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/14-what-vectors-cant-answer/verify.py
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

INVOICES = REPO / "data" / "invoices"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    truth_path = INVOICES / "ground_truth.json"
    if not truth_path.exists():
        print("missing invoices — run: python data/fetch.py --only invoices")
        return 1
    truth = json.loads(truth_path.read_text())
    invoices = truth["invoices"]
    vendors = sorted({r["vendor"] for r in invoices})
    customers = sorted({r["customer"] for r in invoices})

    yours, ref = load("starter"), load("solution")
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    docs = ref.parse_invoices()
    sample_ids = sorted(docs)[:40]
    by_id = {r["invoice_id"]: r for r in invoices}

    # ---- TODO 1 ----------------------------------------------------------
    try:
        recs = [yours.extract_record(docs[i], vendors, customers)
                for i in sample_ids]
        check("extract_record returns a dict",
              recs and isinstance(recs[0], dict),
              f"got {type(recs[0]).__name__ if recs else None}")
        if recs and isinstance(recs[0], dict):
            required = {"invoice_id", "vendor", "customer", "issue_date",
                        "terms", "purchase_order", "total", "status",
                        "line_items"}
            missing = required - set(recs[0])
            check("the record has the required fields", not missing,
                  f"missing: {sorted(missing)}")
            for field in ("invoice_id", "vendor", "customer", "total",
                          "purchase_order", "status"):
                hits = 0
                for i, rec in zip(sample_ids, recs):
                    real = by_id.get(rec.get("invoice_id"))
                    if not real:
                        continue
                    got, want = rec.get(field), real.get(field)
                    if field == "total":
                        hits += got is not None and abs(got - want) < 0.005
                    else:
                        hits += got == want
                check(f"'{field}' extracted correctly for all 40 samples",
                      hits == len(sample_ids),
                      f"{hits}/{len(sample_ids)} correct")
            counts_ok = sum(
                1 for rec in recs
                if by_id.get(rec.get("invoice_id"))
                and len(rec.get("line_items") or [])
                == len(by_id[rec["invoice_id"]]["line_items"]))
            check("line items are all found", counts_ok == len(sample_ids),
                  f"{counts_ok}/{len(sample_ids)} invoices with the right "
                  f"number of line items")
    except Exception as e:
        check("extract_record runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 2 and 3 ----------------------------------------------------
    try:
        all_recs = [ref.extract_record(t, vendors, customers)
                    for t in docs.values()]
        conn = yours.build_sqlite(all_recs)
        check("build_sqlite returns a connection", conn is not None,
              f"got {type(conn).__name__}")
        if conn is not None:
            n = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
            check("every invoice was inserted", n == len(all_recs),
                  f"{n} rows, expected {len(all_recs)}")
            li = conn.execute("SELECT COUNT(*) FROM line_items").fetchone()[0]
            check("line items were inserted", li > n, f"{li} line item rows")

            correct = 0
            for q in truth["questions"]["aggregate"]:
                got = yours.answer_with_sql(conn, q)
                want = q["answer"]
                correct += bool(got is not None and (
                    abs(got - want) < 0.02
                    if isinstance(want, (int, float)) else got == want))
            check("SQL answers every aggregate question exactly",
                  correct == len(truth["questions"]["aggregate"]),
                  f"{correct}/{len(truth['questions']['aggregate'])} correct — "
                  f"check the sql_hint field for the operation each wants")
    except Exception as e:
        check("build_sqlite / answer_with_sql run", False,
              f"{type(e).__name__}: {e}")

    # ---- TODO 4 ----------------------------------------------------------
    try:
        cases = [
            (["a", "b"], ["a", "b"], 1.0),
            (["a"], ["a", "b", "c", "d"], 0.25),
            ([], ["a"], 0.0),
            (["z"], ["a"], 0.0),
        ]
        for got_docs, needed, want in cases:
            got = yours.evidence_coverage(got_docs, needed)
            check(f"evidence_coverage({got_docs}, {needed}) == {want}",
                  got is not None and abs(float(got) - want) < 1e-9,
                  f"got {got!r}")
    except Exception as e:
        check("evidence_coverage runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 5 ----------------------------------------------------------
    try:
        right = 0
        for q in truth["questions"]["descriptive"]:
            right += yours.route(q["question"]) == "retrieval"
        for q in truth["questions"]["aggregate"]:
            right += yours.route(q["question"]) == "sql"
        total = (len(truth["questions"]["descriptive"])
                 + len(truth["questions"]["aggregate"]))
        check("the router sends at least 90% of questions to the right store",
              right / total >= 0.9, f"{right}/{total} routed correctly")
    except Exception as e:
        check("route runs", False, f"{type(e).__name__}: {e}")

    rule("module 14 — your extraction, tables and router")
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}")
        if detail and not ok:
            print(f"         {detail}")
        failed += 0 if ok else 1
    print()
    print(f"all {len(checks)} checks pass." if not failed else
          f"{failed} of {len(checks)} checks failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
