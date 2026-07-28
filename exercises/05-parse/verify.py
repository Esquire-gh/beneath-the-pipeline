#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/05-parse/verify.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

PDFS = REPO / "data" / "hard_pdfs"

CSV_CASES = [
    ('a,b,c', ['a', 'b', 'c']),
    ('a,,c', ['a', '', 'c']),
    ('"a,b",c', ['a,b', 'c']),
    ('"he said ""hi""",x', ['he said "hi"', 'x']),
    ('trailing,', ['trailing', '']),
    ('"",x', ['', 'x']),
    ('INV-10007,"Acme Corp, Ltd.",3,"He said ""ship it""",1240.50,',
     ['INV-10007', 'Acme Corp, Ltd.', '3', 'He said "ship it"', '1240.50', '']),
]


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

    for line, expected in CSV_CASES:
        try:
            got = yours.parse_csv_line(line)
            check(f"parse_csv_line({line[:34]!r})", got == expected,
                  f"yours {got!r}, expected {expected!r}")
        except Exception as e:
            check(f"parse_csv_line({line[:34]!r})", False,
                  f"{type(e).__name__}: {e}")

    clean = PDFS / "gen-clean-1col.pdf"
    if not clean.exists():
        print("missing PDFs — run: python data/fetch.py --only pdfs")
        return 1

    try:
        got = yours.count_word_in_raw_bytes(clean, "storage")
        want = ref.count_word_in_raw_bytes(clean, "storage")
        check("count_word_in_raw_bytes returns a number",
              isinstance(got, int), f"got {type(got).__name__}")
        check("count_word_in_raw_bytes agrees with the reference",
              got == want,
              f"yours {got}, expected {want} — the answer being 0 is the point")
    except Exception as e:
        check("count_word_in_raw_bytes runs", False, f"{type(e).__name__}: {e}")

    try:
        a = ref.extract_pymupdf(clean)
        b = ref.extract_pdfplumber(clean)
        got, want = yours.compare(a, b), ref.compare(a, b)
        check("compare returns a dict", isinstance(got, dict),
              f"got {type(got).__name__}")
        if isinstance(got, dict):
            for key in ("char_ratio", "same_words", "only_in_a", "only_in_b"):
                check(f"compare reports '{key}'", key in got,
                      f"keys present: {sorted(got)}")
            if "char_ratio" in got:
                check("char_ratio matches difflib's ratio",
                      abs(got["char_ratio"] - want["char_ratio"]) < 1e-9,
                      f"yours {got['char_ratio']!r}, "
                      f"expected {want['char_ratio']!r}")
            if "same_words" in got:
                check("same_words compares sorted word lists, not raw strings",
                      got["same_words"] == want["same_words"],
                      f"yours {got['same_words']!r}, "
                      f"expected {want['same_words']!r}")
        # a self-check the reader can reason about
        got_same = yours.compare("a b c", "c b a")
        check("compare says 'a b c' and 'c b a' are the same bag of words",
              isinstance(got_same, dict) and got_same.get("same_words") is True,
              f"got {got_same!r}")
    except Exception as e:
        check("compare runs", False, f"{type(e).__name__}: {e}")

    rule("module 5 — your parsing against the reference")
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
