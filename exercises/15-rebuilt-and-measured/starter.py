#!/usr/bin/env python3
"""Module 15 — the pipeline, rebuilt.  YOUR WORK GOES HERE.

Two TODOs. Everything else is a part you already built.

    python exercises/15-rebuilt-and-measured/starter.py --scale part2
    python exercises/15-rebuilt-and-measured/verify.py

Needs: pymupdf, pdfplumber, pytesseract + Tesseract, sentence-transformers,
numpy. Run `python data/make_eval_docs.py` first.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule, scale_parser   # noqa: E402


# ==========================================================================
# TODO 1 — reciprocal rank fusion
# ==========================================================================
#
# Combine several ranked lists into one. BM25 scores and cosine similarities
# cannot be added — they live on different scales. Ranks can be:
#
#     score(document) = sum over lists of  1 / (k + rank in that list)
#
# k damps the influence of the very top positions, so one list cannot
# dominate. 60 is the conventional value and it is not magic.
#
# Return the fused ranking, best first.

def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> list[int]:
    # TODO
    ...


# ==========================================================================
# TODO 2 — extract with an OCR fallback
# ==========================================================================
#
# Module 13's ladder, implemented. Try the cheap path. DETECT that it
# returned nothing. Fall back to rendering pages and running OCR.
#
# The detection is the part that matters: a text extractor returning an empty
# string is not an error, it is a silent success, and nothing downstream will
# tell you.

def extract_with_ocr_fallback(path: Path, min_chars: int = 40) -> str:
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def main() -> None:
    import json
    args = scale_parser(__doc__, default="part2").parse_args()

    eval_docs = REPO / "data" / "eval_docs"
    truth_path = eval_docs / "ground_truth.json"
    if not truth_path.exists():
        sys.exit("missing documents — run: python data/make_eval_docs.py")
    truth = json.loads(truth_path.read_text())

    rule("1 · reciprocal rank fusion")
    a = [10, 11, 12, 13]
    b = [13, 12, 99, 10]
    print(f"  list A     {a}")
    print(f"  list B     {b}")
    print(f"  fused      {reciprocal_rank_fusion([a, b])}")
    print("  a document ranked well by BOTH lists should come out on top.")

    rule("2 · extraction, with and without the fallback")
    import fitz
    for key, doc in sorted(truth["documents"].items())[:6]:
        path = eval_docs / "pdf" / doc["file"]
        with fitz.open(path) as d:
            plain = "".join(p.get_text() for p in d)
        got = extract_with_ocr_fallback(path) or ""
        print(f"  {doc['file']:<28} scanned={doc['scanned']!s:<5} "
              f"PyMuPDF {len(plain.strip()):>5} chars   "
              f"yours {len(got.strip()):>5} chars")

    print("\n  every document should yield text. If the scanned ones give 0, "
          "the fallback is not firing.")


if __name__ == "__main__":
    main()
