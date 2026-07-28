#!/usr/bin/env python3
"""Module 9 — The index that doesn't fit.  YOUR WORK GOES HERE.

Four TODOs. Two about building an index without holding it in memory, two
about making the result smaller.

    python exercises/09-index-that-doesnt-fit/starter.py --scale small
    python exercises/09-index-that-doesnt-fit/verify.py

Needs: numpy. Standard library otherwise.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import human_bytes, rule, scale_parser   # noqa: E402

TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# ==========================================================================
# TODO 1 — gaps instead of document ids
# ==========================================================================
#
# A posting list is a sorted list of document ids:
#
#     [3, 17, 18, 92, 415, 416, 417]
#
# Sorted means each id is bigger than the one before, so you can store the
# DIFFERENCES instead and lose nothing:
#
#     [3, 14, 1, 74, 323, 1, 1]
#
# The first entry is the id itself; every entry after it is the step from the
# previous one. The numbers get much smaller, which is the whole point —
# module 3 showed that a small number needs fewer bytes.
#
# Return the list of gaps.

def to_gaps(postings: list[int]) -> list[int]:
    # TODO
    ...


def from_gaps(gaps: list[int]) -> list[int]:
    """Undo to_gaps. Written for you, so you can check yourself."""
    out, running = [], 0
    for gap in gaps:
        running += gap
        out.append(running)
    return out


# ==========================================================================
# TODO 2 — variable-length bytes
# ==========================================================================
#
# Now write those small numbers using as few bytes as each one needs.
#
# The scheme, called varbyte: take seven bits at a time, low bits first. Every
# byte carries seven bits of the number in its low positions. The high bit is
# a flag: 1 means "this is the last byte of this number", 0 means "keep
# reading".
#
#     value 3     ->  1 byte   0b1000_0011
#     value 200   ->  2 bytes  0b0100_1000, 0b1000_0001
#
# So values under 128 take one byte instead of four. Return `bytes`.

def varbyte_encode(numbers: list[int]) -> bytes:
    out = bytearray()
    for number in numbers:
        # TODO: emit seven bits at a time, low bits first, and set the high
        # bit on the final byte of each number
        ...
    return bytes(out)


def varbyte_decode(data: bytes) -> list[int]:
    """Undo varbyte_encode. Written for you."""
    out, value, shift = [], 0, 0
    for byte in data:
        value |= (byte & 0x7F) << shift
        if byte & 0x80:
            out.append(value)
            value, shift = 0, 0
        else:
            shift += 7
    return out


# ==========================================================================
# TODO 3 — build an index in blocks, spilling each one to disk
# ==========================================================================
#
# The technique is called SPIMI: single-pass in-memory indexing.
#
#   * read documents one at a time, never holding the corpus
#   * accumulate postings in a dict until you have `block_size` documents
#   * write that dict to disk as a sorted run of "term<TAB>id,id,id" lines
#   * throw the dict away and start the next block
#
# Peak memory is then set by block_size, not by corpus size. That is the
# entire idea.
#
# Return the list of paths you wrote.

def build_blocks(docs, out_dir: Path, block_size: int = 10_000) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths, block, doc_id = [], {}, 0
    for text in docs:
        # TODO: add this document's distinct tokens to `block`
        ...
        doc_id += 1
        if doc_id % block_size == 0:
            # TODO: spill `block` to a file, append the path, clear the dict
            ...
    # TODO: don't lose the final partial block
    return paths


def write_block(block: dict[str, list[int]], path: Path) -> None:
    """Write one block as sorted term lines. Written for you."""
    with path.open("w", encoding="utf-8") as f:
        for term in sorted(block):
            f.write(f"{term}\t{','.join(str(d) for d in block[term])}\n")


# ==========================================================================
# TODO 4 — merge the sorted runs
# ==========================================================================
#
# Every block file is sorted by term. Merge them into one sorted file without
# loading any of them entirely — open all of them at once and always take the
# smallest term available, joining the posting lists when several files carry
# the same term.
#
# heapq.merge does exactly this if you feed it (term, postings) pairs. Peak
# memory stays at one line per file.
#
# Return the number of distinct terms written.

def merge_blocks(paths: list[Path], out_path: Path) -> int:
    import heapq   # noqa: F401
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def iter_block_lines(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            term, _, ids = line.rstrip("\n").partition("\t")
            yield term, [int(x) for x in ids.split(",") if x]


def main() -> None:
    from common import iter_eval_corpus, resolve_n
    args = scale_parser(__doc__, default="small").parse_args()
    n = resolve_n(args)

    scratch = Path(__file__).parent / "_index"
    docs = (t for _, t in iter_eval_corpus(n))

    rule("1 · gaps")
    postings = [3, 17, 18, 92, 415, 416, 417]
    gaps = to_gaps(postings)
    print(f"  ids   {postings}")
    print(f"  gaps  {gaps}")
    print(f"  round trip ok: {from_gaps(gaps or []) == postings}")

    rule("2 · varbyte")
    raw = varbyte_encode(gaps or [])
    print(f"  {len(postings)} ids as 4-byte integers: {len(postings) * 4} bytes")
    print(f"  the same, as gaps in varbyte:          {len(raw)} bytes")
    print(f"  round trip ok: {varbyte_decode(raw) == gaps}")

    rule("3 · building in blocks")
    paths = build_blocks(docs, scratch, block_size=10_000)
    print(f"  wrote {len(paths) if paths else 0} block files")

    rule("4 · merging")
    terms = merge_blocks(paths or [], scratch / "merged.txt")
    print(f"  merged into {terms if terms else 0:,} terms")


if __name__ == "__main__":
    main()
