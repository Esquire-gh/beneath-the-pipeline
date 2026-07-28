#!/usr/bin/env python3
"""Module 10 — Ingestion vs query speed, and keeping what you built.

Four TODOs. Three about accepting new documents without rebuilding, one about
writing an index down so a later version of your code can still read it.

    python exercises/10-ingestion-vs-query/starter.py --scale small
    python exercises/10-ingestion-vs-query/verify.py

Standard library only.
"""
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import human_bytes, rule, scale_parser   # noqa: E402

TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# ==========================================================================
# A segment: a small index over one batch of documents, never modified again
# ==========================================================================
#
# Written for you. The idea is the whole module: instead of one index you keep
# editing, you make many small indexes you never edit. Deleting is a tombstone;
# updating is a delete plus an add. Nothing is ever changed in place.

class Segment:
    def __init__(self, docs: dict[int, str]):
        self.postings: dict[str, list[int]] = {}
        self.doc_ids: list[int] = []
        for doc_id, text in docs.items():
            self.doc_ids.append(doc_id)
            for token in set(tokenize(text)):
                self.postings.setdefault(token, []).append(doc_id)
        for plist in self.postings.values():
            plist.sort()

    @property
    def n_docs(self) -> int:
        return len(self.doc_ids)

    @property
    def n_postings(self) -> int:
        return sum(len(p) for p in self.postings.values())

    def search(self, term: str) -> list[int]:
        return self.postings.get(term, [])


# ==========================================================================
# TODO 1 — search across every segment
# ==========================================================================
#
# A query has to consult every segment and combine the answers, because no
# single segment knows about the whole corpus. That is the price of never
# editing anything: reads get more expensive as segments accumulate.
#
# Return the sorted list of document ids, with no duplicates.
# Also return how many segments you had to touch — that number is called the
# query FANOUT, and it is what the merge policy exists to control.

def search_all(segments: list[Segment], term: str) -> tuple[list[int], int]:
    # TODO: return (sorted unique doc ids, number of segments consulted)
    ...


# ==========================================================================
# TODO 2 — merge two segments into one
# ==========================================================================
#
# Combining two segments means merging their posting lists term by term. The
# result is one segment holding everything both held.
#
# Return a new Segment. You may build it directly from the merged postings
# rather than re-tokenizing — use Segment.__new__(Segment) and set the fields,
# or add a classmethod. Re-tokenizing would work too and is slower, which is
# itself part of the lesson: merging costs real work.

def merge_segments(a: Segment, b: Segment) -> Segment:
    # TODO
    ...


# ==========================================================================
# TODO 3 — a merge policy
# ==========================================================================
#
# Segments arrive one per batch. Left alone, you end up with thousands and
# every query touches all of them. Merging them all into one after every batch
# makes queries fast and ingestion impossibly slow.
#
# The policy in between: whenever there are `fan` or more segments of about the
# same size, merge those into one bigger segment. Small segments get folded
# into big ones a level at a time, so most merges are cheap and the expensive
# ones are rare.
#
# Implement it by bucketing segments by size tier — tier = how many times you
# can divide n_docs by `fan` — and merging any tier with `fan` or more members.
#
# Return (new segment list, number of documents rewritten by the merges).
# That second number is the cost: every merge rewrites every posting it touches.

def apply_merge_policy(segments: list[Segment], fan: int = 4) -> tuple[list[Segment], int]:
    # TODO
    ...


# ==========================================================================
# TODO 4 — write the index down, with a version number
# ==========================================================================
#
# Module 3 said reading a field needs three facts: offset, width, byte order.
# Now you are the format author, so you have to WRITE those facts down.
#
# The header, all little-endian:
#
#   offset  width  meaning
#        0      4  the ASCII magic bytes  b"BTP1"
#        4      2  format version         (unsigned 16-bit)
#        6      2  flags                  (unsigned 16-bit, 0 for now)
#        8      4  number of terms        (unsigned 32-bit)
#
# Then, per term: a 2-byte length, the term's UTF-8 bytes, a 4-byte posting
# count, then that many 4-byte document ids.
#
# Return the bytes.

MAGIC = b"BTP1"
VERSION = 1


def write_index(segment: Segment, version: int = VERSION) -> bytes:
    out = bytearray()
    # TODO: header, then one record per term
    ...
    return bytes(out)


def read_index(data: bytes) -> tuple[dict, dict[str, list[int]]]:
    """Read what write_index wrote. Written for you — read it before TODO 4,
    it tells you exactly what the bytes have to look like."""
    if data[:4] != MAGIC:
        raise ValueError(f"not a BTP index: starts with {data[:4]!r}")
    version, flags, n_terms = struct.unpack_from("<HHI", data, 4)
    if version > VERSION:
        raise ValueError(
            f"index was written by version {version}; this reader "
            f"understands up to {VERSION}. Refusing to guess.")
    header = {"version": version, "flags": flags, "terms": n_terms}
    postings, offset = {}, 12
    for _ in range(n_terms):
        (term_len,) = struct.unpack_from("<H", data, offset)
        offset += 2
        term = data[offset:offset + term_len].decode("utf-8")
        offset += term_len
        (count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        postings[term] = list(struct.unpack_from(f"<{count}I", data, offset))
        offset += 4 * count
    return header, postings


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def batches(docs, size: int):
    batch, next_id = {}, 0
    for text in docs:
        batch[next_id] = text
        next_id += 1
        if len(batch) >= size:
            yield batch
            batch = {}
    if batch:
        yield batch


def main() -> None:
    from common import iter_eval_corpus, resolve_n
    args = scale_parser(__doc__, default="small").parse_args()
    n = resolve_n(args)

    rule("1 · segments accumulate")
    segments = []
    for batch in batches((t for _, t in iter_eval_corpus(min(n, 50_000))), 5_000):
        segments.append(Segment(batch))
    print(f"  {len(segments)} segments, "
          f"{sum(s.n_docs for s in segments):,} documents")

    hits, fanout = search_all(segments, "block") or ([], 0)
    print(f"  searching 'block' touched {fanout} segments, "
          f"found {len(hits):,} documents")

    rule("2 · a merge policy")
    merged, rewritten = apply_merge_policy(list(segments)) or ([], 0)
    print(f"  {len(segments)} segments -> {len(merged)} after merging")
    print(f"  {rewritten:,} documents rewritten to get there")

    rule("3 · writing it down")
    blob = write_index(segments[0])
    print(f"  segment 0: {segments[0].n_postings:,} postings, "
          f"{human_bytes(len(blob))}")
    header, postings = read_index(blob)
    print(f"  read back: {header}")
    print(f"  round trip ok: {postings == segments[0].postings}")


if __name__ == "__main__":
    main()
