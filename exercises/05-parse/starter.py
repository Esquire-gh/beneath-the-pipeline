#!/usr/bin/env python3
"""Module 5 — Parse: the agreement, honoured or not.  YOUR WORK GOES HERE.

Three TODOs. You will honour one simple agreement by hand, fail to find text
in a PDF, and then measure how far two PDF libraries disagree.

    python exercises/05-parse/starter.py       # run yours
    python exercises/05-parse/verify.py        # check it

Needs: pymupdf, pdfplumber, and data/hard_pdfs (python data/fetch.py --only pdfs).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

PDFS = REPO / "data" / "hard_pdfs"

# A CSV row that is harder than it looks. Every awkward case is deliberate.
TRICKY_CSV = 'INV-10007,"Acme Corp, Ltd.",3,"He said ""ship it""",1240.50,'


# ==========================================================================
# TODO 1 — honour a simple agreement by hand
# ==========================================================================
#
# CSV's agreement, in full:
#
#   * fields are separated by commas
#   * a field may be wrapped in double quotes
#   * inside quotes, a comma is data, not a separator
#   * inside quotes, two double quotes in a row mean one literal double quote
#   * an empty field is an empty string, not None
#
# That is the entire format. Walk the line one character at a time and split
# it. Do not use the csv module — the point is that you can write this, and
# that it is *possible* to write it, because the agreement records structure.
#
# For the line above, the right answer is:
#   ['INV-10007', 'Acme Corp, Ltd.', '3', 'He said "ship it"', '1240.50', '']

def parse_csv_line(line: str) -> list[str]:
    fields, field, in_quotes = [], [], False
    i = 0
    while i < len(line):
        ch = line[i]
        # TODO: handle the quote character, the comma, and everything else
        ...
        i += 1
    # TODO: don't forget the last field
    return fields


# ==========================================================================
# TODO 2 — try to find the text in a PDF's bytes, and fail
# ==========================================================================
#
# Open a PDF as raw bytes and count how many times a word you can plainly see
# on the page appears in them. Return the count.
#
# You already know how to look at bytes — module 2. Do that here, honestly,
# and report what you find. The expected answer is not a large number.

def count_word_in_raw_bytes(pdf_path: Path, word: str) -> int:
    raw = pdf_path.read_bytes()
    # TODO: count occurrences of `word` in `raw` (encode the word first)
    ...


# ==========================================================================
# TODO 3 — measure how far two extractions disagree
# ==========================================================================
#
# Given two strings, return a dict with:
#
#   char_ratio   difflib.SequenceMatcher(None, a, b).ratio()  — 1.0 is identical
#   same_words   whether sorted(a.split()) == sorted(b.split())
#                (i.e. the same bag of words, possibly in a different order)
#   only_in_a    how many words appear in a but not b
#   only_in_b    how many words appear in b but not a
#
# `same_words` matters: two extractions can contain exactly the same words in
# a different order, and that is a different kind of failure from missing words.

def compare(a: str, b: str) -> dict:
    import difflib   # noqa: F401
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def extract_pymupdf(path: Path, sort: bool = False) -> str:
    import fitz
    with fitz.open(path) as doc:
        return "\n".join(page.get_text("text", sort=sort) for page in doc)


def extract_pdfplumber(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def main() -> None:
    rule("1 · a format whose agreement records structure")
    print(f"  input:  {TRICKY_CSV}")
    print(f"  yours:  {parse_csv_line(TRICKY_CSV)}")
    print(f"  expect: ['INV-10007', 'Acme Corp, Ltd.', '3', "
          f"'He said \"ship it\"', '1240.50', '']")

    clean = PDFS / "gen-clean-1col.pdf"
    if not clean.exists():
        sys.exit("missing PDFs — run: python data/fetch.py --only pdfs")

    rule("2 · looking for the text in a PDF's bytes")
    for word in ("storage", "block", "device"):
        print(f"  '{word}' appears {count_word_in_raw_bytes(clean, word)} "
              f"time(s) in the raw bytes")
    print("  now open the PDF and count how many times you can see it on the page.")

    rule("3 · two libraries, one document")
    for name in ("gen-clean-1col.pdf", "gen-2col.pdf", "gen-tables.pdf"):
        path = PDFS / name
        if not path.exists():
            continue
        a, b = extract_pymupdf(path), extract_pdfplumber(path)
        print(f"  {name:<22} {compare(a, b)}")


if __name__ == "__main__":
    main()
