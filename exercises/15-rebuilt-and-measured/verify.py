#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/15-rebuilt-and-measured/verify.py
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

EVAL_DOCS = REPO / "data" / "eval_docs"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    yours, ref = load("starter"), load("solution")
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    # ---- TODO 1 ----------------------------------------------------------
    try:
        a, b = [10, 11, 12, 13], [13, 12, 99, 10]
        got = yours.reciprocal_rank_fusion([a, b])
        want = ref.reciprocal_rank_fusion([a, b])
        check("reciprocal_rank_fusion returns a list",
              isinstance(got, list), f"got {type(got).__name__}")
        if isinstance(got, list):
            check("the fused ranking matches the reference",
                  list(got) == list(want),
                  f"yours {list(got)}, reference {list(want)}")
            check("every document from both lists survives",
                  set(got) == set(a) | set(b),
                  f"missing {sorted((set(a) | set(b)) - set(got))}")
            single = yours.reciprocal_rank_fusion([[5, 6, 7]])
            check("fusing one list returns it unchanged",
                  list(single) == [5, 6, 7], f"got {single}")
            top_both = yours.reciprocal_rank_fusion([[1, 2, 3], [1, 3, 2]])
            check("a document ranked first by both lists comes first",
                  top_both and top_both[0] == 1, f"got {top_both}")
            check("k damps the top positions",
                  list(yours.reciprocal_rank_fusion([a, b], k=1))
                  == list(ref.reciprocal_rank_fusion([a, b], k=1)),
                  "the k argument is not being used")
    except Exception as e:
        check("reciprocal_rank_fusion runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 2 ----------------------------------------------------------
    truth_path = EVAL_DOCS / "ground_truth.json"
    if not truth_path.exists():
        check("the evaluation documents exist", False,
              "run: python data/make_eval_docs.py")
    else:
        truth = json.loads(truth_path.read_text())
        scanned = [d for d in truth["documents"].values() if d["scanned"]][:2]
        text_docs = [d for d in truth["documents"].values()
                     if not d["scanned"]][:2]
        try:
            for d in text_docs:
                got = yours.extract_with_ocr_fallback(
                    EVAL_DOCS / "pdf" / d["file"]) or ""
                check(f"text document {d['file']} extracts",
                      len(got.strip()) > 200, f"{len(got.strip())} characters")
            for d in scanned:
                got = yours.extract_with_ocr_fallback(
                    EVAL_DOCS / "pdf" / d["file"]) or ""
                check(f"scanned document {d['file']} falls back to OCR",
                      len(got.strip()) > 200,
                      f"{len(got.strip())} characters — a scanned page yields "
                      f"nothing from a text extractor, so the fallback has to "
                      f"detect that and run OCR")
                terms = d["distinctive_terms"]
                found = sum(1 for t in terms if t.split()[0].lower()
                            in got.lower())
                check(f"OCR recovered the distinctive words of {d['file']}",
                      found >= 1,
                      f"found {found} of {len(terms)} distinctive terms")
        except Exception as e:
            check("extract_with_ocr_fallback runs", False,
                  f"{type(e).__name__}: {e}")

    rule("module 15 — your fusion and extraction")
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
