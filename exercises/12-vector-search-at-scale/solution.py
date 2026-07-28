#!/usr/bin/env python3
"""Module 12 — worked solution, and the source of the module page's numbers.

    python exercises/12-vector-search-at-scale/solution.py --scale part2
    python exercises/12-vector-search-at-scale/solution.py --scale big

Brute force is slow and exactly right. HNSW is fast and approximately right.
This measures the exchange rate, sweeps the knob that sets it, and then adds a
metadata filter and watches the whole arrangement stop helping.
"""
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (embed_corpus, embed_queries, eval_corpus, human_bytes,   # noqa: E402
                    human_time, load_queries, normalized, resolve_n, rule,
                    scale_parser, usable_queries, write_measurements)

SLUG = "12-vector-search-at-scale"
K = 10


def brute_force_topk(vectors, query, k=K):
    import numpy as np
    scores = vectors @ query
    top = np.argpartition(-scores, k)[:k]
    return top[np.argsort(-scores[top])]


def recall_at_k(approx, truth, k=K) -> float:
    """Of the k genuinely nearest vectors, how many did the index return?

    Recall against brute force, not against the relevance judgments. This
    measures whether the index found what it was ASKED to find; module 8's
    NDCG measures whether that was worth finding. Both matter, and they are
    different questions.
    """
    return len(set(approx[:k]) & set(truth[:k])) / k


def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--ef-construction", type=int, default=200)
    ap.add_argument("--M", type=int, default=16)
    args = ap.parse_args()
    n = resolve_n(args)

    import numpy as np
    import hnswlib

    m = {"n_passages": n, "k": K, "M": args.M,
         "ef_construction": args.ef_construction}

    corpus = eval_corpus(n)
    pids = [p for p, _ in corpus]
    pid_to_doc = {p: i for i, p in enumerate(pids)}
    vectors = normalized(embed_corpus(n))
    dims = vectors.shape[1]
    m["dims"] = dims
    m["vector_bytes"] = int(vectors.nbytes)
    print(f"  {len(vectors):,} vectors x {dims} dims = "
          f"{human_bytes(vectors.nbytes)}")

    queries = load_queries()
    judged = usable_queries(set(pids))
    qids = sorted(judged)[:args.queries]
    qvecs = normalized(embed_queries([queries[qid] for qid in qids]))
    m["n_queries"] = len(qids)

    # ---- the truth, and what it costs ------------------------------------
    rule("1 · brute force: exactly right, and slow")
    truth = []
    latencies = []
    for q in qvecs:
        t0 = time.perf_counter()
        truth.append(brute_force_topk(vectors, q))
        latencies.append(time.perf_counter() - t0)
    latencies.sort()
    m["brute_force"] = {
        "median_seconds": latencies[len(latencies) // 2],
        "p99_seconds": latencies[int(len(latencies) * 0.99)],
        "comparisons_per_query": len(vectors),
        "multiply_adds_per_query": int(len(vectors) * dims),
        "recall": 1.0,
    }
    print(f"  median {human_time(m['brute_force']['median_seconds'])} per query, "
          f"p99 {human_time(m['brute_force']['p99_seconds'])}")
    print(f"  {len(vectors) * dims:,} multiply-adds every time")

    # ---- build the graph -------------------------------------------------
    rule("2 · building an HNSW index")
    index = hnswlib.Index(space="ip", dim=dims)   # vectors are unit length,
    t0 = time.perf_counter()                       # so inner product IS cosine
    index.init_index(max_elements=len(vectors), ef_construction=args.ef_construction,
                     M=args.M)
    index.add_items(vectors, np.arange(len(vectors)))
    build_seconds = time.perf_counter() - t0

    graph_path = Path(__file__).parent / "_hnsw.bin"
    index.save_index(str(graph_path))
    graph_bytes = graph_path.stat().st_size
    graph_path.unlink(missing_ok=True)

    m["hnsw_build"] = {
        "seconds": build_seconds,
        "bytes": graph_bytes,
        "bytes_over_vectors": graph_bytes / vectors.nbytes,
        "per_vector_bytes": graph_bytes / len(vectors),
    }
    print(f"  built in {human_time(build_seconds)}")
    print(f"  the graph is {human_bytes(graph_bytes)} on top of "
          f"{human_bytes(vectors.nbytes)} of vectors "
          f"({graph_bytes / vectors.nbytes:.2f}x)")

    # ---- the knob --------------------------------------------------------
    rule("3 · sweeping ef_search — quality as a dial")
    m["sweep"] = []
    print(f"  {'ef':>6}  {'recall@10':>10}  {'median':>10}  {'p99':>10}  "
          f"{'vs brute force':>15}")
    for ef in (10, 16, 24, 32, 48, 64, 96, 128, 192, 256, 512):
        index.set_ef(max(ef, K))
        recalls, lat = [], []
        for i, q in enumerate(qvecs):
            t0 = time.perf_counter()
            labels, _ = index.knn_query(q, k=K)
            lat.append(time.perf_counter() - t0)
            recalls.append(recall_at_k(list(labels[0]), list(truth[i])))
        lat.sort()
        row = {
            "ef": ef,
            "recall": sum(recalls) / len(recalls),
            "median_seconds": lat[len(lat) // 2],
            "p99_seconds": lat[int(len(lat) * 0.99)],
            "speedup": (m["brute_force"]["median_seconds"]
                        / lat[len(lat) // 2]),
        }
        m["sweep"].append(row)
        print(f"  {ef:>6}  {row['recall']:>10.4f}  "
              f"{row['median_seconds'] * 1000:>8.3f}ms  "
              f"{row['p99_seconds'] * 1000:>8.3f}ms  "
              f"{row['speedup']:>13.0f}x")

    perfect = [r for r in m["sweep"] if r["recall"] >= 0.999]
    m["first_perfect_ef"] = perfect[0]["ef"] if perfect else None
    cheapest = m["sweep"][0]
    m["knob"] = {
        "lowest_ef_recall": cheapest["recall"],
        "lowest_ef_speedup": cheapest["speedup"],
        "recall_range": m["sweep"][-1]["recall"] - cheapest["recall"],
        "speedup_range": cheapest["speedup"] / m["sweep"][-1]["speedup"],
    }
    print(f"\n  at ef={cheapest['ef']}: {cheapest['recall']:.1%} of the right "
          f"answers, {cheapest['speedup']:.0f}x faster")
    print(f"  at ef={m['sweep'][-1]['ef']}: "
          f"{m['sweep'][-1]['recall']:.1%}, "
          f"{m['sweep'][-1]['speedup']:.0f}x faster")
    print(f"  the whole trade is one integer")

    # ---- what approximation does to the thing you actually care about ----
    rule("4 · and what it does to NDCG")
    sys.path.insert(0, str(REPO / "exercises" / "08-retrieve"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "retrieve", REPO / "exercises" / "08-retrieve" / "solution.py")
    retrieve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retrieve)

    m["quality"] = []
    for ef in (10, 32, 128, 512):
        index.set_ef(max(ef, K))
        ndcg = 0.0
        for i, qid in enumerate(qids):
            labels, _ = index.knn_query(qvecs[i], k=K)
            relevant = {pid_to_doc[p] for p in judged[qid]}
            ndcg += retrieve.ndcg_at_k([int(x) for x in labels[0]], relevant, K)
        m["quality"].append({"ef": ef, "ndcg_at_10": ndcg / len(qids)})
        print(f"  ef={ef:>4}  NDCG@10 {ndcg / len(qids):.4f}")

    exact_ndcg = 0.0
    for i, qid in enumerate(qids):
        relevant = {pid_to_doc[p] for p in judged[qid]}
        exact_ndcg += retrieve.ndcg_at_k([int(x) for x in truth[i]], relevant, K)
    m["exact_ndcg_at_10"] = exact_ndcg / len(qids)
    print(f"  exact     NDCG@10 {exact_ndcg / len(qids):.4f}")
    m["ndcg_cost_of_lowest_ef"] = (m["exact_ndcg_at_10"]
                                   - m["quality"][0]["ndcg_at_10"])

    # ---- the filtered-search cliff ---------------------------------------
    rule("5 · add a filter matching about 1% of documents")
    #
    # A metadata filter is the most ordinary request in the world: "search
    # only this customer's documents". Give every vector a synthetic bucket
    # and ask for one of them.
    rng = np.random.default_rng(4242)
    bucket = rng.integers(0, 100, size=len(vectors))
    allowed = np.flatnonzero(bucket == 7)
    m["filter"] = {"selectivity": len(allowed) / len(vectors),
                   "matching_documents": int(len(allowed))}
    print(f"  {len(allowed):,} of {len(vectors):,} documents match "
          f"({len(allowed) / len(vectors):.1%})")

    # the honest answer: brute force over the matching subset
    subset = vectors[allowed]
    lat = []
    filtered_truth = []
    for q in qvecs:
        t0 = time.perf_counter()
        scores = subset @ q
        top = np.argpartition(-scores, K)[:K]
        filtered_truth.append([int(allowed[j]) for j in top[np.argsort(-scores[top])]])
        lat.append(time.perf_counter() - t0)
    lat.sort()
    m["filter"]["brute_force_subset"] = {
        "median_seconds": lat[len(lat) // 2],
        "recall": 1.0,
        "vectors_compared": int(len(allowed)),
    }
    print(f"  brute force over just those: "
          f"{human_time(lat[len(lat) // 2])} per query, perfect recall")

    # what the graph does: search, then throw away what does not match
    m["filter"]["post_filter"] = []
    print(f"  {'ef':>6}  {'kept of 10':>11}  {'recall@10':>10}  {'median':>10}")
    for ef in (10, 64, 256, 1024, 4096):
        index.set_ef(max(ef, K))
        kept, recalls, lat = [], [], []
        for i, q in enumerate(qvecs):
            t0 = time.perf_counter()
            labels, _ = index.knn_query(q, k=min(ef, len(vectors)))
            got = [int(x) for x in labels[0] if bucket[int(x)] == 7][:K]
            lat.append(time.perf_counter() - t0)
            kept.append(len(got))
            recalls.append(len(set(got) & set(filtered_truth[i])) / K)
        lat.sort()
        row = {"ef": ef, "mean_kept": sum(kept) / len(kept),
               "recall": sum(recalls) / len(recalls),
               "median_seconds": lat[len(lat) // 2],
               "empty_rate": sum(1 for x in kept if x == 0) / len(kept)}
        m["filter"]["post_filter"].append(row)
        print(f"  {ef:>6}  {row['mean_kept']:>11.2f}  {row['recall']:>10.4f}  "
              f"{row['median_seconds'] * 1000:>8.3f}ms")

    best_post = max(m["filter"]["post_filter"], key=lambda r: r["recall"])
    m["filter"]["verdict"] = {
        "best_post_filter_recall": best_post["recall"],
        "best_post_filter_ef": best_post["ef"],
        "best_post_filter_seconds": best_post["median_seconds"],
        "subset_scan_seconds": m["filter"]["brute_force_subset"]["median_seconds"],
        "subset_scan_wins": (m["filter"]["brute_force_subset"]["median_seconds"]
                             < best_post["median_seconds"]),
    }
    print(f"\n  the graph's best filtered recall is {best_post['recall']:.1%} "
          f"at ef={best_post['ef']}, costing "
          f"{human_time(best_post['median_seconds'])}")
    print(f"  scanning the {len(allowed):,} matching vectors takes "
          f"{human_time(m['filter']['brute_force_subset']['median_seconds'])} "
          f"and is exactly right")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
