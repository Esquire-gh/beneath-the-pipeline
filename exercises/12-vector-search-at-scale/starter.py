#!/usr/bin/env python3
"""Module 12 — Vector search at scale.  YOUR WORK GOES HERE.

Three TODOs. The truth, the approximation, and the measurement that tells you
how far apart they are.

    python exercises/12-vector-search-at-scale/starter.py --scale part2
    python exercises/12-vector-search-at-scale/verify.py

Needs: hnswlib, numpy, sentence-transformers.
"""
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (embed_corpus, embed_queries, eval_corpus, human_bytes,   # noqa: E402
                    human_time, load_queries, normalized, resolve_n, rule,
                    scale_parser, usable_queries)

K = 10


# ==========================================================================
# TODO 1 — the truth
# ==========================================================================
#
# Every vector has length 1, so the cosine similarity is the dot product.
# Score the query against every vector and return the indices of the top k,
# best first. This is module 7's TODO 4 again, and it is what "right" means
# for the rest of this module — you cannot say an index is 90% correct until
# you have the 100% to compare against.

def brute_force_topk(vectors, query, k=K):
    # TODO
    ...


# ==========================================================================
# TODO 2 — build the graph
# ==========================================================================
#
# hnswlib, in four calls:
#
#     index = hnswlib.Index(space="ip", dim=dims)   # inner product: our
#                                                   # vectors are unit length,
#                                                   # so this IS cosine
#     index.init_index(max_elements=..., ef_construction=..., M=...)
#     index.add_items(vectors, numpy.arange(len(vectors)))
#     index.set_ef(ef_search)                       # the knob, set per query
#
# Return the built index. Time the build — it is a real cost and the module
# reports it.
#
# M controls how many edges each node keeps; ef_construction controls how hard
# the builder looks for good ones. Both are build-time; ef_search is the one
# you can change afterwards, which is why it is the knob that matters.

def build_hnsw(vectors, M: int = 16, ef_construction: int = 200):
    import hnswlib   # noqa: F401
    import numpy as np   # noqa: F401
    # TODO
    ...


# ==========================================================================
# TODO 3 — recall@k
# ==========================================================================
#
# Of the k genuinely nearest vectors, how many did the index return?
#
#     recall = |approx[:k] ∩ truth[:k]| / k
#
# Order does not matter here — this asks whether the index FOUND the right
# documents, not whether it ranked them well. Module 8's NDCG asks the second
# question, and the two can disagree.

def recall_at_k(approx, truth, k=K) -> float:
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    ap.add_argument("--queries", type=int, default=200)
    args = ap.parse_args()
    n = resolve_n(args)

    import numpy as np

    corpus = eval_corpus(n)
    pids = [p for p, _ in corpus]
    vectors = normalized(embed_corpus(n))
    print(f"  {len(vectors):,} vectors x {vectors.shape[1]} dims = "
          f"{human_bytes(vectors.nbytes)}")

    queries = load_queries()
    judged = usable_queries(set(pids))
    qids = sorted(judged)[:args.queries]
    qvecs = normalized(embed_queries([queries[qid] for qid in qids]))

    rule("1 · brute force — exactly right, and slow")
    truth, lat = [], []
    for q in qvecs:
        t0 = time.perf_counter()
        truth.append(brute_force_topk(vectors, q))
        lat.append(time.perf_counter() - t0)
    lat.sort()
    exact_seconds = lat[len(lat) // 2]
    print(f"  median {human_time(exact_seconds)} per query, "
          f"{len(vectors) * vectors.shape[1]:,} multiply-adds every time")

    rule("2 · building the graph")
    t0 = time.perf_counter()
    index = build_hnsw(vectors)
    print(f"  built in {human_time(time.perf_counter() - t0)}")

    rule("3 · the knob")
    print(f"  {'ef':>6}  {'recall@10':>10}  {'median':>10}  {'vs brute force':>15}")
    for ef in (10, 32, 64, 128, 256, 512):
        index.set_ef(max(ef, K))
        recalls, lat = [], []
        for i, q in enumerate(qvecs):
            t0 = time.perf_counter()
            labels, _ = index.knn_query(q, k=K)
            lat.append(time.perf_counter() - t0)
            recalls.append(recall_at_k(list(labels[0]), list(truth[i])))
        lat.sort()
        median = lat[len(lat) // 2]
        print(f"  {ef:>6}  {sum(recalls) / len(recalls):>10.4f}  "
              f"{median * 1000:>8.3f}ms  {exact_seconds / median:>13.0f}x")

    rule("4 · now add a filter matching about 1% of documents")
    rng = np.random.default_rng(4242)
    bucket = rng.integers(0, 100, size=len(vectors))
    allowed = np.flatnonzero(bucket == 7)
    print(f"  {len(allowed):,} of {len(vectors):,} documents match")
    print(f"  search the graph and discard what does not match, and see how "
          f"many of ten survive. then compare with scanning the "
          f"{len(allowed):,} matches directly.")
    for ef in (10, 64, 256, 1024):
        index.set_ef(max(ef, K))
        kept = []
        for q in qvecs:
            labels, _ = index.knn_query(q, k=min(ef, len(vectors)))
            kept.append(len([x for x in labels[0] if bucket[int(x)] == 7][:K]))
        print(f"  ef={ef:>5}: {sum(kept) / len(kept):>5.2f} of 10 results usable")


if __name__ == "__main__":
    main()
