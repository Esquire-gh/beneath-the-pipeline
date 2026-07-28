#!/usr/bin/env python3
"""Module 13 — Why parsing is a hard problem.  YOUR WORK GOES HERE.

Mostly this module is investigation: run `solution.py` and read what happened.
But two functions are worth writing yourself, because everything the module
claims about accuracy rests on the first and every production ingestion
pipeline needs the second.

    python exercises/13-why-parsing-is-hard/starter.py
    python exercises/13-why-parsing-is-hard/verify.py
    python exercises/13-why-parsing-is-hard/solution.py    # the four experiments

Needs: pymupdf, pytesseract + the Tesseract binary.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

PDFS = REPO / "data" / "hard_pdfs"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ==========================================================================
# TODO 1 — edit distance, written out
# ==========================================================================
#
# The fewest single-character edits — insert, delete, substitute — that turn
# `a` into `b`. Also called Levenshtein distance.
#
# Write it rather than importing it. Every accuracy claim in this module is
# this number divided by a length, and it should not be a black box.
#
# The standard approach is one row of a table at a time:
#
#   previous[j] is the distance from a[:i-1] to b[:j]
#   current[j]  = min(previous[j] + 1,          delete a character from a
#                     current[j-1] + 1,         insert a character from b
#                     previous[j-1] + (differ)) substitute, free if equal

def edit_distance(a: str, b: str) -> int:
    # TODO
    ...


# ==========================================================================
# TODO 2 — character error rate
# ==========================================================================
#
# Edits per character of the ORIGINAL text. 0.0 is perfect.
#
# Normalise whitespace on both sides first, or you will be measuring how the
# OCR engine felt about line breaks rather than whether it read the words.
#
# Return 0.0 if the reference is empty — there is nothing to be wrong about.

def character_error_rate(reference: str, guess: str) -> float:
    # TODO
    ...


# ==========================================================================
# TODO 3 — detect that extraction failed
# ==========================================================================
#
# This is the one to take to work with you.
#
# A text extractor handed a scanned page does not raise. It returns an empty
# string, and the document silently vanishes from your corpus. Every other
# stage of a pipeline fails loudly; this one does not.
#
# Return True if `text` looks like a failed extraction — too short to be a
# page of prose. Say what your threshold is and why.

def extraction_failed(text: str, min_chars: int = 40) -> bool:
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def pymupdf_text(path: Path) -> str:
    import fitz
    with fitz.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


def main() -> None:
    clean = PDFS / "gen-clean-1col.pdf"
    scanned = PDFS / "gen-clean-1col-scanned.pdf"
    if not scanned.exists():
        sys.exit("missing PDFs — run: python data/fetch.py --only pdfs")

    rule("1 · edit distance")
    for a, b in (("kitten", "sitting"), ("block", "b1ock"), ("same", "same")):
        print(f"  {a!r} -> {b!r}: {edit_distance(a, b)}")
    print("  'kitten' to 'sitting' is 3. If you got that, the table is right.")

    rule("2 · character error rate")
    ref = "The disk hands back 4096 bytes."
    for guess in (ref, "The disk hands back 4O96 bytes.",
                  "Tbe d1sk hancls back 4O96 bytez."):
        print(f"  {character_error_rate(ref, guess)!s:<24} {guess!r}")

    rule("3 · detecting a failed extraction")
    for path in (clean, scanned):
        text = pymupdf_text(path)
        failed = extraction_failed(text)
        print(f"  {path.name:<32} {len(text.strip()):>5} chars   "
              f"failed={failed}")
    print("\n  the scanned document must come back as a failure. If both look "
          "fine,\n  your threshold is letting an empty page through.")


if __name__ == "__main__":
    main()
