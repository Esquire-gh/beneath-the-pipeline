#!/usr/bin/env python3
"""Module 11 — Retrieval at scale.  YOUR WORK GOES HERE.

    python exercises/11-retrieval-at-scale/starter.py --scale small --queries 60
    python exercises/11-retrieval-at-scale/verify.py

Three ways to answer the same query, scoring identical results:

    term-at-a-time   touch every posting of every query term
    document-at-a-time with skips   the same, but able to jump
    WAND             refuse to score documents that cannot reach the top k

Every strategy reports how many postings it touched, and the answers are
checked against each other. A faster wrong answer is not a result.
"""
import heapq
import math
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (human_time, iter_eval_corpus, load_queries, resolve_n,   # noqa: E402
                    rule, scale_parser, usable_queries)

TOKEN = re.compile(r"[a-z0-9]+")
K1, B = 1.2, 0.75


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# --------------------------------------------------------------------------
# the index, with per-term upper bounds
# --------------------------------------------------------------------------

class ScaleIndex:
    """Module 8's BM25 index, plus the one extra number WAND needs.

    For each term, the largest BM25 contribution any single document could
    get from it. Computed once at build time; it is what makes it possible to
    rule a document out before scoring it.
    """

    def __init__(self, docs, skip_stride: int = 64):
        import numpy as np

        self.postings: dict[str, tuple] = {}
        doc_len: list[int] = []
        build: dict[str, list[tuple[int, int]]] = {}

        for doc_id, text in enumerate(docs):
            counts: dict[str, int] = {}
            for token in tokenize(text):
                counts[token] = counts.get(token, 0) + 1
            doc_len.append(sum(counts.values()))
            for term, tf in counts.items():
                build.setdefault(term, []).append((doc_id, tf))

        self.N = len(doc_len)
        self.doc_len = np.asarray(doc_len, dtype="float32")
        self.avgdl = float(self.doc_len.mean()) if self.N else 1.0
        self.skip_stride = skip_stride

        self.idf: dict[str, float] = {}
        self.upper: dict[str, float] = {}
        for term, plist in build.items():
            ids = np.fromiter((d for d, _ in plist), dtype="int64", count=len(plist))
            tfs = np.fromiter((t for _, t in plist), dtype="float32", count=len(plist))
            df = len(ids)
            idf = math.log(1 + (self.N - df + 0.5) / (df + 0.5))
            norm = 1 - B + B * self.doc_len[ids] / self.avgdl
            contrib = idf * (tfs * (K1 + 1)) / (tfs + K1 * norm)
            self.postings[term] = (ids, tfs, contrib)
            self.idf[term] = idf
            self.upper[term] = float(contrib.max())

    def df(self, term: str) -> int:
        entry = self.postings.get(term)
        return len(entry[0]) if entry else 0

    @property
    def n_postings(self) -> int:
        return sum(len(v[0]) for v in self.postings.values())


# --------------------------------------------------------------------------
# cursors — the thing that walks a posting list
# --------------------------------------------------------------------------

class Cursor:
    """One query term's position in its posting list.

    `touched` counts postings stepped over. That counter is the module's
    instrument: every strategy moves cursors, and the difference between
    strategies is how many postings they have to move across.
    """

    def __init__(self, term, ids, contrib, upper, stats):
        self.term = term
        self.ids = ids
        self.contrib = contrib
        self.upper = upper
        self.i = 0
        self.stats = stats

    @property
    def doc(self) -> int:
        return int(self.ids[self.i]) if self.i < len(self.ids) else -1

    @property
    def exhausted(self) -> bool:
        return self.i >= len(self.ids)

    def score(self) -> float:
        return float(self.contrib[self.i])

    def advance_linear(self, target: int) -> None:
        """Step forward one posting at a time until reaching target."""
        while self.i < len(self.ids) and self.ids[self.i] < target:
            self.i += 1
            self.stats["touched"] += 1

    def advance_skipping(self, target: int, stride: int) -> None:
        """TODO 2 — jump `stride` postings at a time, then step the last few.

        A skip pointer is nothing more than this: because the list is sorted,
        you can look ahead, see the value is still too small, and move a whole
        block without reading what is inside it.

        Count every look as one touched posting.
        """
        # TODO
        ...



# ==========================================================================
# TODO 1 — document at a time
# ==========================================================================
#
# Module 8 scored TERM at a time: take a query word, walk its whole posting
# list adding into a score map, then the next word. It needs a score map
# holding every document any term touched.
#
# Do it DOCUMENT at a time instead. Give each query term a Cursor. Repeatedly:
#
#   * find the smallest document id any live cursor is sitting on
#   * add up the contributions of every cursor sitting on that document
#   * push the score into a heap of the best k
#   * advance every cursor that was on that document past it
#
# Never build a score map. A heap of k is all you keep.
#
# Return (list of (doc, score) best first, stats).
#
# Tie-breaking matters: when two documents score equally, every strategy in
# this module must order them the same way, or "the same answer" means
# nothing. Compare the whole tuple (score, -doc), not just the score.

def daat(index: ScaleIndex, query: str, k: int = 10, skip: bool = True):
    stats = {"touched": 0, "skips": 0, "scored": 0}
    cursors = []
    for term in set(tokenize(query)):
        entry = index.postings.get(term)
        if entry is None:
            continue
        ids, _tfs, contrib = entry
        cursors.append(Cursor(term, ids, contrib, index.upper[term], stats))
    if not cursors:
        return [], stats

    heap: list[tuple[float, int]] = []
    # TODO: the loop described above
    ...
    top = sorted(((-d, s) for s, d in heap), key=lambda kv: (-kv[1], kv[0]))
    return [(d, s) for d, s in top], stats


# ==========================================================================
# TODO 2 — skip pointers
# ==========================================================================
#
# Fill in Cursor.advance_skipping, above. Posting lists are sorted, so you can
# look `stride` entries ahead: if the value there is still smaller than your
# target, move the whole block without reading what is inside it. Then step
# the last few one at a time.
#
# Count every look as one touched posting — a skip is cheap, not free.
#
# Advancing to `current + 1` can never skip anything. Skipping only pays when
# the target is far away, which is what TODO 3 produces.


# ==========================================================================
# TODO 3 — WAND: refuse to score what cannot win
# ==========================================================================
#
# index.upper[term] is the largest score any single document could ever get
# from that term. It is computed once at build time.
#
# Keep the k best scores so far; the worst of them is your THRESHOLD.
# Repeatedly:
#
#   * sort the live cursors by the document they are on
#   * add up their upper bounds going down that list; the first cursor where
#     the running total exceeds the threshold is the PIVOT
#   * if no such cursor exists, nothing left can beat the top k — stop
#   * if the first cursor is already on the pivot's document, every cursor
#     before the pivot is too: score that document and advance past it
#   * otherwise advance one lagging cursor UP TO the pivot's document without
#     scoring anything. That is the jump skip pointers exist for.
#
# Update the threshold whenever the heap changes.
#
# Return the same shape as daat. It must return the SAME top k.

def wand(index: ScaleIndex, query: str, k: int = 10, skip: bool = True):
    stats = {"touched": 0, "skips": 0, "scored": 0, "pivots": 0}
    cursors = []
    for term in set(tokenize(query)):
        entry = index.postings.get(term)
        if entry is None:
            continue
        ids, _tfs, contrib = entry
        cursors.append(Cursor(term, ids, contrib, index.upper[term], stats))
    if not cursors:
        return [], stats

    heap: list[tuple[float, int]] = []
    threshold = 0.0
    # TODO
    ...
    top = sorted(((-d, s) for s, d in heap), key=lambda kv: (-kv[1], kv[0]))
    return [(d, s) for d, s in top], stats


# --------------------------------------------------------------------------
# term at a time — written for you, as the baseline to match
# --------------------------------------------------------------------------

def taat(index: ScaleIndex, query: str, k: int = 10):
    stats = {"touched": 0, "skips": 0, "scored": 0}
    scores: dict[int, float] = {}
    for term in set(tokenize(query)):
        entry = index.postings.get(term)
        if entry is None:
            continue
        ids, _tfs, contrib = entry
        stats["touched"] += len(ids)
        for doc, value in zip(ids.tolist(), contrib.tolist()):
            scores[doc] = scores.get(doc, 0.0) + value
    stats["scored"] = len(scores)
    top = heapq.nlargest(k, scores.items(), key=lambda kv: (kv[1], -kv[0]))
    return [(d, s) for d, s in top], stats


def main() -> None:
    ap = scale_parser(__doc__, default="small")
    ap.add_argument("--queries", type=int, default=60)
    args = ap.parse_args()
    n = resolve_n(args)

    print(f"indexing {n:,} passages…")
    index = ScaleIndex((t for _, t in iter_eval_corpus(n)))
    print(f"  {index.n_postings:,} postings, {len(index.postings):,} terms")

    from common import eval_corpus
    corpus_pids = {p for p, _ in eval_corpus(n)}
    queries = load_queries()
    judged = usable_queries(corpus_pids)
    qids = sorted(judged)[:args.queries]

    rule("the same query, three ways — the answers must match")
    reference = None
    for label, fn in (("term at a time", lambda q: taat(index, q)),
                      ("document at a time", lambda q: daat(index, q)),
                      ("WAND", lambda q: wand(index, q))):
        touched = scored = agree = 0
        answers = []
        t0 = time.perf_counter()
        for qid in qids:
            top, stats = fn(queries[qid])
            touched += stats["touched"]
            scored += stats["scored"]
            answers.append([d for d, _ in (top or [])])
        seconds = (time.perf_counter() - t0) / len(qids)
        if reference is None:
            reference = answers
            agree = len(qids)
        else:
            agree = sum(1 for a, b in zip(answers, reference) if a == b)
        print(f"  {label:<20} {touched / len(qids):>10,.0f} postings  "
              f"{scored / len(qids):>9,.0f} scored  "
              f"{human_time(seconds)}/query  "
              f"same answer {agree}/{len(qids)}")


if __name__ == "__main__":
    main()
