#!/usr/bin/env python3
"""Module 5 — worked solution, and the source of the module page's numbers.

    python exercises/05-parse/solution.py

Read this after you have written your own.
"""
import difflib
import json
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule, write_measurements   # noqa: E402

SLUG = "05-parse"
PDFS = REPO / "data" / "hard_pdfs"

TRICKY_CSV = 'INV-10007,"Acme Corp, Ltd.",3,"He said ""ship it""",1240.50,'
TRICKY_JSON = ('{"invoice": "INV-10007", "vendor": "Acme Corp, Ltd.", '
               '"note": "He said \\"ship it\\"", "total": 1240.50, "tags": []}')


# --------------------------------------------------------------------------
# 1 · honouring a simple agreement by hand
# --------------------------------------------------------------------------

def parse_csv_line(line: str) -> list[str]:
    fields, field, in_quotes = [], [], False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            if in_quotes and i + 1 < len(line) and line[i + 1] == '"':
                field.append('"')        # two quotes mean one literal quote
                i += 1
            else:
                in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            fields.append("".join(field))
            field = []
        else:
            field.append(ch)
        i += 1
    fields.append("".join(field))
    return fields


# --------------------------------------------------------------------------
# 2 · the text is not in the bytes
# --------------------------------------------------------------------------

def count_word_in_raw_bytes(pdf_path: Path, word: str) -> int:
    return pdf_path.read_bytes().count(word.encode())


def content_stream(pdf_path: Path, page_no: int = 0) -> bytes:
    """The instructions a PDF page actually holds, decompressed.

    This is the mechanism the whole module turns on: a page is not text, it is
    a list of drawing commands.
    """
    import fitz
    with fitz.open(pdf_path) as doc:
        page = doc[page_no]
        xref = page.get_contents()[0]
        raw = doc.xref_stream(xref)      # PyMuPDF decompresses for us
        return raw


def raw_compressed_stream(pdf_path: Path) -> dict:
    """Show that the bytes on disk are compressed, which is why step 2 failed."""
    raw = pdf_path.read_bytes()
    marker = raw.find(b"/FlateDecode")
    return {"has_flatedecode": marker != -1, "at_offset": marker}


# --------------------------------------------------------------------------
# 3 · measuring disagreement
# --------------------------------------------------------------------------

def compare(a: str, b: str) -> dict:
    wa, wb = a.split(), b.split()
    return {
        "char_ratio": difflib.SequenceMatcher(None, a, b).ratio(),
        "same_words": sorted(wa) == sorted(wb),
        "only_in_a": len(set(wa) - set(wb)),
        "only_in_b": len(set(wb) - set(wa)),
        "chars_a": len(a),
        "chars_b": len(b),
        "words_a": len(wa),
        "words_b": len(wb),
        "word_gap": abs(len(wa) - len(wb)),
        "word_gap_pct": (abs(len(wa) - len(wb)) / max(len(wa), len(wb), 1)),
    }


def first_difference(a: str, b: str, context: int = 90) -> dict:
    """Where the two extractions first part company, with a little context."""
    sm = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            return {
                "tag": tag,
                "offset": i1,
                "a": " ".join(a[i1:i1 + context].split()),
                "b": " ".join(b[j1:j1 + context].split()),
            }
    return {}


def extract_pymupdf(path: Path, sort: bool = False) -> str:
    import fitz
    with fitz.open(path) as doc:
        return "\n".join(page.get_text("text", sort=sort) for page in doc)


def extract_pdfplumber(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


# --------------------------------------------------------------------------

def main() -> None:
    m = {}

    rule("1 · CSV — an agreement that records structure")
    fields = parse_csv_line(TRICKY_CSV)
    m["csv"] = {"input": TRICKY_CSV, "fields": fields, "n_fields": len(fields)}
    print(f"  input:  {TRICKY_CSV}")
    for i, f in enumerate(fields):
        print(f"    field {i}: {f!r}")

    import csv as csv_module
    from io import StringIO
    reference = next(csv_module.reader(StringIO(TRICKY_CSV)))
    m["csv"]["matches_stdlib"] = reference == fields
    print(f"  matches the standard library's reader: {reference == fields}")

    rule("2 · JSON — a different agreement, same kind of thing")
    parsed = json.loads(TRICKY_JSON)
    m["json"] = {"input": TRICKY_JSON, "parsed": parsed,
                 "keys": sorted(parsed)}
    print(f"  {parsed}")
    print("  brackets and escapes instead of delimiters and quoting.")
    print("  in both formats, the structure is written down. that is the point.")

    clean = PDFS / "gen-clean-1col.pdf"
    two_col = PDFS / "gen-2col.pdf"
    tables = PDFS / "gen-tables.pdf"
    if not clean.exists():
        sys.exit("missing PDFs — run: python data/fetch.py --only pdfs")

    rule("3 · looking for the text in a PDF's bytes")
    words = ["storage", "block", "device", "The"]
    raw_counts = {w: count_word_in_raw_bytes(clean, w) for w in words}
    text = extract_pymupdf(clean)
    page_counts = {w: text.count(w) for w in words}
    m["raw_bytes"] = {
        "file": clean.name,
        "file_size": clean.stat().st_size,
        "raw_counts": raw_counts,
        "page_counts": page_counts,
        "compression": raw_compressed_stream(clean),
    }
    for w in words:
        print(f"  '{w}': {raw_counts[w]} in the raw bytes, "
              f"{page_counts[w]} on the page")
    print(f"  the file declares /FlateDecode at offset "
          f"{m['raw_bytes']['compression']['at_offset']} — the text is compressed.")

    rule("4 · what a page actually holds, once decompressed")
    stream = content_stream(clean)
    head = stream[:600].decode("latin-1")
    m["content_stream"] = {
        "total_bytes": len(stream),
        "excerpt": head,
        "n_Tj": stream.count(b"Tj") + stream.count(b"TJ"),
        "n_Td": stream.count(b"Td") + stream.count(b"TD"),
        "n_Tf": stream.count(b"Tf"),
    }
    print(f"  {len(stream):,} bytes of drawing instructions")
    print(f"  {m['content_stream']['n_Tf']} font selections, "
          f"{m['content_stream']['n_Td']} move-the-pen commands, "
          f"{m['content_stream']['n_Tj']} show-this-text commands")
    for line in head.splitlines()[:12]:
        print(f"    {line}")

    rule("5 · two libraries, five documents")
    m["extractions"] = {}
    real = [PDFS / n for n in ("acl-2col-01.pdf", "irs-1040.pdf")]
    for path in [clean, two_col, tables] + [p for p in real if p.exists()]:
        if not path.exists():
            continue
        a = extract_pymupdf(path)
        b = extract_pdfplumber(path)
        cmp = compare(a, b)
        cmp["first_difference"] = first_difference(a, b)
        m["extractions"][path.stem] = cmp
        print(f"  {path.name:<22} char similarity "
              f"{cmp['char_ratio']:.3f}   same bag of words: {cmp['same_words']}"
              f"   ({cmp['words_a']} vs {cmp['words_b']} words)")

    rule("6 · the same library, told to read in coordinate order")
    # Not a different library — the SAME one, with layout awareness turned off.
    # This is module 13c's subject, previewed with one argument.
    naive = extract_pymupdf(two_col, sort=True)
    smart = extract_pymupdf(two_col, sort=False)
    cmp = compare(smart, naive)
    cmp["first_difference"] = first_difference(smart, naive)
    cmp["naive_excerpt"] = " ".join(naive[300:640].split())
    cmp["smart_excerpt"] = " ".join(smart[300:640].split())
    m["reading_order"] = cmp
    print(f"  two-column page, same extractor, layout awareness off:")
    print(f"    char similarity {cmp['char_ratio']:.3f}, "
          f"same bag of words: {cmp['same_words']}")
    print(f"    in coordinate order: {cmp['naive_excerpt'][:150]}…")

    path = write_measurements(SLUG, m)
    print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
