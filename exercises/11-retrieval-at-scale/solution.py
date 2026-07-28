#!/usr/bin/env python3
"""Module 11 — worked solution, and the source of the module page's numbers.

    python exercises/11-retrieval-at-scale/solution.py --scale part2 --queries 200
    python exercises/11-retrieval-at-scale/solution.py --scale big --queries 100

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
                    rule, scale_parser, usable_queries, write_measurements)

SLUG = "11-retrieval-at-scale"
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
        """Jump `stride` postings at a time, then step the last few.

        A skip pointer is nothing more than this: because the list is sorted,
        you can look ahead, see the value is still too small, and move a whole
        block without reading what is inside it.
        """
        n = len(self.ids)
        while self.i + stride < n and self.ids[self.i + stride] < target:
            self.i += stride
            self.stats["touched"] += 1      # one look, whole block skipped
            self.stats["skips"] += 1
        while self.i < n and self.ids[self.i] < target:
            self.i += 1
            self.stats["touched"] += 1


# --------------------------------------------------------------------------
# three ways to answer the same query
# --------------------------------------------------------------------------

def taat(index: ScaleIndex, query: str, k: int = 10):
    """Term at a time: accumulate scores for every document any term touches."""
    stats = {"touched": 0, "skips": 0, "scored": 0}
    scores: dict[int, float] = {}
    # DISTINCT query terms. WAND keeps one upper bound per term, so it can
    # only ever count a term once; if this loop counted a repeated query word
    # twice the three strategies would be scoring different things and the
    # comparison would be meaningless.
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


def daat(index: ScaleIndex, query: str, k: int = 10, skip: bool = True):
    """Document at a time: walk all posting lists together, in document order.

    Scores exactly the same documents as term-at-a-time, but never holds a
    score map — it finishes each document before moving on.
    """
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
    while True:
        live = [c for c in cursors if not c.exhausted]
        if not live:
            break
        current = min(c.doc for c in live)
        score = 0.0
        for c in live:
            if c.doc == current:
                score += c.score()
        stats["scored"] += 1
        if len(heap) < k:
            heapq.heappush(heap, (score, -current))
        elif (score, -current) > heap[0]:
            # compare the whole tuple, not just the score: two documents with
            # equal scores must be ordered the same way by every strategy, or
            # "the same answer" stops meaning anything
            heapq.heapreplace(heap, (score, -current))
        for c in live:
            if c.doc == current:
                if skip:
                    c.advance_skipping(current + 1, index.skip_stride)
                else:
                    c.advance_linear(current + 1)
    top = sorted(((-d, s) for s, d in heap), key=lambda kv: (-kv[1], kv[0]))
    return [(d, s) for d, s in top], stats


def wand(index: ScaleIndex, query: str, k: int = 10, skip: bool = True):
    """Refuse to score documents that cannot reach the top k.

    Each term carries the largest score it could ever contribute. Sort the
    cursors by their current document; walk the upper bounds up until they
    could beat the worst of the current top k. The document at that point is
    the PIVOT — nothing before it can win, so jump straight there.
    """
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

    while True:
        live = [c for c in cursors if not c.exhausted]
        if not live:
            break
        live.sort(key=lambda c: c.doc)

        # find the pivot: the first document where the accumulated upper
        # bounds could exceed the current threshold
        total, pivot = 0.0, None
        for c in live:
            total += c.upper
            if total > threshold:
                pivot = c
                break
        if pivot is None:
            break                     # nothing left can beat the top k

        stats["pivots"] += 1
        if live[0].doc == pivot.doc:
            # every cursor before the pivot is already here: score it
            current = pivot.doc
            score = 0.0
            for c in live:
                if c.doc == current:
                    score += c.score()
            stats["scored"] += 1
            if len(heap) < k:
                heapq.heappush(heap, (score, -current))
                if len(heap) == k:
                    threshold = heap[0][0]
            elif (score, -current) > heap[0]:
                heapq.heapreplace(heap, (score, -current))
                threshold = heap[0][0]
            for c in live:
                if c.doc == current:
                    c.advance_linear(current + 1)
        else:
            # move a lagging cursor up to the pivot without scoring anything.
            # This is the jump a skip pointer exists for: the target is far
            # away, and everything in between is known to be irrelevant.
            for c in live:
                if c.doc < pivot.doc:
                    if skip:
                        c.advance_skipping(pivot.doc, index.skip_stride)
                    else:
                        c.advance_linear(pivot.doc)
                    break

    top = sorted(((-d, s) for s, d in heap), key=lambda kv: (-kv[1], kv[0]))
    return [(d, s) for d, s in top], stats


# --------------------------------------------------------------------------

def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--stride", type=int, default=64)
    args = ap.parse_args()
    n = resolve_n(args)

    m = {"n_passages": n, "skip_stride": args.stride}

    print(f"indexing {n:,} passages…")
    t0 = time.perf_counter()
    index = ScaleIndex((t for _, t in iter_eval_corpus(n)), skip_stride=args.stride)
    m["index_build_seconds"] = time.perf_counter() - t0
    m["postings"] = index.n_postings
    m["vocabulary"] = len(index.postings)
    print(f"  {index.n_postings:,} postings, {len(index.postings):,} terms, "
          f"{human_time(m['index_build_seconds'])}")

    queries = load_queries()
    pids = [p for p, _ in []] or None
    from common import eval_corpus
    corpus_pids = {p for p, _ in eval_corpus(n)}
    judged = usable_queries(corpus_pids)
    qids = sorted(judged)[:args.queries]
    m["n_queries"] = len(qids)

    # how many postings a query term set covers, before any pruning
    covered = []
    for qid in qids:
        covered.append(sum(index.df(t) for t in set(tokenize(queries[qid]))))
    covered.sort()
    m["postings_per_query"] = {
        "median": covered[len(covered) // 2],
        "max": covered[-1],
    }
    print(f"  a median query's terms cover "
          f"{covered[len(covered) // 2]:,} postings")

    rule("three strategies, identical answers")
    strategies = [
        ("taat", "term at a time", lambda q: taat(index, q)),
        ("daat", "document at a time", lambda q: daat(index, q, skip=False)),
        ("wand_linear", "WAND, stepping one at a time",
         lambda q: wand(index, q, skip=False)),
        ("wand", "WAND with skip pointers", lambda q: wand(index, q, skip=True)),
    ]

    m["strategies"] = {}
    reference_answers = None
    for key, label, fn in strategies:
        touched = scored = 0
        latencies = []
        answers = []
        for qid in qids:
            t0 = time.perf_counter()
            top, stats = fn(queries[qid])
            latencies.append(time.perf_counter() - t0)
            touched += stats["touched"]
            scored += stats["scored"]
            answers.append([d for d, _ in top])
        latencies.sort()

        if reference_answers is None:
            reference_answers = answers
            agree = agree_set = 1.0
        else:
            same = sum(1 for a, b in zip(answers, reference_answers) if a == b)
            same_set = sum(1 for a, b in zip(answers, reference_answers)
                           if set(a) == set(b))
            agree, agree_set = same / len(answers), same_set / len(answers)

        m["strategies"][key] = {
            "label": label,
            "postings_touched_per_query": touched / len(qids),
            "documents_scored_per_query": scored / len(qids),
            "median_seconds": latencies[len(latencies) // 2],
            "p99_seconds": latencies[int(len(latencies) * 0.99)],
            "max_seconds": latencies[-1],
            "agreement_with_taat": agree,
            "same_set_as_taat": agree_set,
        }
        print(f"  {label:<32} {touched / len(qids):>12,.0f} postings  "
              f"{scored / len(qids):>10,.0f} scored  "
              f"median {latencies[len(latencies) // 2] * 1000:>7.2f} ms  "
              f"p99 {latencies[int(len(latencies) * 0.99)] * 1000:>7.2f} ms  "
              f"agree {agree:.0%}")

    s = m["strategies"]
    m["reduction"] = {
        "postings_taat_vs_wand": (s["taat"]["postings_touched_per_query"]
                                  / max(s["wand"]["postings_touched_per_query"], 1)),
        "scored_taat_vs_wand": (s["taat"]["documents_scored_per_query"]
                                / max(s["wand"]["documents_scored_per_query"], 1)),
        "postings_skip_vs_linear": (s["wand_linear"]["postings_touched_per_query"]
                                    / max(s["wand"]["postings_touched_per_query"], 1)),
        "speed_taat_vs_wand": (s["taat"]["median_seconds"]
                               / max(s["wand"]["median_seconds"], 1e-12)),
    }
    m["tail"] = {
        key: {"median_ms": v["median_seconds"] * 1000,
              "p99_ms": v["p99_seconds"] * 1000,
              "p99_over_median": v["p99_seconds"] / max(v["median_seconds"], 1e-12)}
        for key, v in s.items()
    }
    # Where the orderings differ, are the SCORES different, or only the order?
    # Term-at-a-time adds one term's contribution across all documents; WAND
    # adds all contributions for one document. Same numbers, different order
    # of addition — and module 3 said that is not the same sum.
    gaps = []
    order_diffs = 0
    for qid in qids:
        a, _ = taat(index, queries[qid])
        b, _ = wand(index, queries[qid])
        if [d for d, _ in a] != [d for d, _ in b]:
            order_diffs += 1
            sa = {d: sc for d, sc in a}
            sb = {d: sc for d, sc in b}
            shared = set(sa) & set(sb)
            if shared:
                gaps.append(max(abs(sa[d] - sb[d]) for d in shared))
    m["float_order"] = {
        "queries_with_different_order": order_diffs,
        "max_score_difference": max(gaps) if gaps else 0.0,
        "median_score_difference": sorted(gaps)[len(gaps) // 2] if gaps else 0.0,
        "note": ("Any remaining difference is the order of floating-point "
                 "addition: term-at-a-time sums one term across all documents, "
                 "WAND sums all terms for one document. IEEE 754 addition is "
                 "not associative, so near-tied documents can swap places."),
    }
    print(f"\n  {order_diffs} of {len(qids)} queries came back in a "
          f"different order")
    if gaps:
        print(f"  largest score difference on a shared document: "
              f"{max(gaps):.3e}")

    print(f"\n  WAND touched "
          f"{m['reduction']['postings_taat_vs_wand']:.1f}x fewer postings "
          f"and fully scored "
          f"{m['reduction']['scored_taat_vs_wand']:.1f}x fewer documents")
    print(f"  skip pointers cut postings touched by "
          f"{m['reduction']['postings_skip_vs_linear']:.2f}x within WAND")
    print(f"  WAND's top 10 is the same SET as term-at-a-time's for "
          f"{s['wand']['same_set_as_taat']:.0%} of queries, "
          f"in the same ORDER for {s['wand']['agreement_with_taat']:.0%}")
    for key, v in m["tail"].items():
        print(f"  {key:<14} p99 is {v['p99_over_median']:.1f}x its median")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
