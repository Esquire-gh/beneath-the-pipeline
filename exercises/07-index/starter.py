#!/usr/bin/env python3
"""Module 7 — Index: what db.add() built.  YOUR WORK GOES HERE.

Four TODOs. You will build the two structures a vector database builds, and
measure what each one bought and what it cost.

    python exercises/07-index/starter.py --scale small
    python exercises/07-index/verify.py

Needs: numpy. Needs the corpus and (for TODO 4) the cached vectors:
    python data/fetch.py --only msmarco --small
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (eval_corpus, human_bytes, human_time, resolve_n,   # noqa: E402
                    rule, scale_parser)

TOKEN = re.compile(r"[a-z0-9]+")


# ==========================================================================
# TODO 1 — tokenize, the same way for documents and for queries
# ==========================================================================
#
# Lowercase the text and pull out runs of letters and digits. Return a list of
# tokens, in order, duplicates kept.
#
# This has to be the SAME function for indexing and for searching. If a
# document is indexed under "Block" and a query is looked up as "block", the
# index will confidently tell you there are no matches. Most "the index is
# broken" bugs are this.

def tokenize(text: str) -> list[str]:
    # TODO — one line with TOKEN.findall is fine
    ...


# ==========================================================================
# TODO 2 — the scan: no index at all
# ==========================================================================
#
# Look for `word` by reading every passage, every time. Return the sorted list
# of passage ids that contain it.
#
# `passages` is a list of (pid, text). This is the honest baseline — it is
# what grep does, and it always works.

def scan(passages, word: str) -> list[int]:
    # TODO
    ...


# ==========================================================================
# TODO 3 — the inverted index
# ==========================================================================
#
# Build a dict from word -> sorted list of passage ids containing that word.
# That list is called a POSTING LIST, and the pair (word, list) is the whole
# idea of an inverted index: instead of asking "what words does this document
# have", you can ask "what documents have this word".
#
# Sort each posting list and store each id once. Both matter later: module 9
# compresses these lists and needs them sorted, and module 11 skips through
# them and needs them without duplicates.

def build_inverted_index(passages) -> dict[str, list[int]]:
    index = {}
    # TODO
    ...
    return index


# ==========================================================================
# TODO 4 — brute-force nearest neighbour
# ==========================================================================
#
# `vectors` is an (n, dims) array where every row has length 1 already, so the
# cosine similarity between two rows is just their dot product — module 6's
# formula with both divisions by 1.
#
# Score `query` against EVERY row and return the indices of the top k, best
# first. One matrix multiply does the whole thing.
#
# This is what a vector database does before anyone optimises it, and at this
# scale it is genuinely fine. Module 12 is where it stops being fine.

def brute_force_topk(vectors, query, k: int = 10):
    # TODO — numpy: vectors @ query, then argsort
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def index_size_bytes(index) -> int:
    """Roughly how much memory the index occupies.

    sys.getsizeof does not follow references, so a dict of lists needs walking
    by hand. This undercounts the small integer objects Python interns, and
    that is fine — the number is for comparison, not for accounting.
    """
    import sys as _sys
    total = _sys.getsizeof(index)
    for word, postings in index.items():
        total += _sys.getsizeof(word) + _sys.getsizeof(postings)
        total += 8 * len(postings)
    return total


def main() -> None:
    args = scale_parser(__doc__, default="small").parse_args()
    n = resolve_n(args)

    print(f"loading {n:,} passages…")
    passages = list(enumerate(t for _, t in eval_corpus(n)))

    rule("1 · tokenizing")
    tokens = tokenize("The Block device, and 4096 BYTES.")
    print(f"  {tokens}")

    rule("2 · scan vs index")
    import time
    for word in ("manhattan", "block", "the"):
        t0 = time.perf_counter()
        hits = scan(passages, word)
        scan_s = time.perf_counter() - t0
        print(f"  scan  {word:<12} {len(hits) if hits else 0:>7,} hits "
              f"in {human_time(scan_s)}")

    t0 = time.perf_counter()
    index = build_inverted_index(passages)
    build_s = time.perf_counter() - t0
    print(f"\n  built an index of {len(index) if index else 0:,} words "
          f"in {human_time(build_s)}  ({human_bytes(index_size_bytes(index or {}))})")

    for word in ("manhattan", "block", "the"):
        t0 = time.perf_counter()
        hits = (index or {}).get(word, [])
        look_s = time.perf_counter() - t0
        print(f"  index {word:<12} {len(hits):>7,} hits in {human_time(look_s)}")

    rule("3 · brute-force nearest neighbour")
    from common import embed_corpus, normalized
    vectors = normalized(embed_corpus(min(n, 20_000)))
    top = brute_force_topk(vectors, vectors[0], k=5)
    print(f"  nearest 5 to passage 0: {list(top) if top is not None else None}")


if __name__ == "__main__":
    main()
