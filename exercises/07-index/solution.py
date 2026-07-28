#!/usr/bin/env python3
"""Module 7 — worked solution, and the source of the module page's numbers.

    python exercises/07-index/solution.py --scale part2

Read this after you have written your own.
"""
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (embed_corpus, eval_corpus, human_bytes, human_time,   # noqa: E402
                    normalized, peak_rss_bytes, resolve_n, rule, scale_parser,
                    write_measurements)

SLUG = "07-index"
TOKEN = re.compile(r"[a-z0-9]+")

PROBE_WORDS = ["manhattan", "block", "photosynthesis", "the", "zyzzyva"]


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def scan(passages, word: str) -> list[int]:
    """The honest scan: tokenize every passage, every time."""
    word = word.lower()
    return sorted(pid for pid, text in passages if word in tokenize(text))


def scan_substring(passages, word: str) -> list[int]:
    """The fast scan, which is what grep does — and it is not the same thing.

    A substring search finds 'block' inside 'blockchain' and inside
    'roadblocks'. It is several times quicker and answers a different
    question, which is worth measuring next to the correct one.
    """
    word = word.lower()
    return sorted(pid for pid, text in passages if word in text.lower())


def build_inverted_index(passages) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for pid, text in passages:
        for token in set(tokenize(text)):
            index.setdefault(token, []).append(pid)
    for postings in index.values():
        postings.sort()
    return index


def brute_force_topk(vectors, query, k: int = 10):
    import numpy as np
    scores = vectors @ query
    if k >= len(scores):
        return np.argsort(-scores)
    top = np.argpartition(-scores, k)[:k]
    return top[np.argsort(-scores[top])]


def index_size_bytes(index) -> int:
    total = sys.getsizeof(index)
    for word, postings in index.items():
        total += sys.getsizeof(word) + sys.getsizeof(postings)
        total += 8 * len(postings)
    return total


def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    args = ap.parse_args()
    n = resolve_n(args)

    import numpy as np

    m = {"n_passages": n}

    print(f"loading {n:,} passages…")
    t0 = time.perf_counter()
    passages = list(enumerate(t for _, t in eval_corpus(n)))
    m["load_seconds"] = time.perf_counter() - t0
    corpus_bytes = sum(len(t.encode()) for _, t in passages)
    m["corpus_bytes"] = corpus_bytes
    print(f"  {human_bytes(corpus_bytes)} of text in {human_time(m['load_seconds'])}")

    # ---- the scan, which needs no index and is always correct -----------
    rule("1 · the scan — no index, read everything, every time")
    m["scan"] = {}
    m["scan_substring"] = {}
    for word in PROBE_WORDS:
        t0 = time.perf_counter()
        hits = scan(passages, word)
        seconds = time.perf_counter() - t0
        m["scan"][word] = {"hits": len(hits), "seconds": seconds}

        t0 = time.perf_counter()
        sub_hits = scan_substring(passages, word)
        sub_seconds = time.perf_counter() - t0
        m["scan_substring"][word] = {"hits": len(sub_hits),
                                     "seconds": sub_seconds}
        flag = "" if len(sub_hits) == len(hits) else \
            f"   <- substring scan finds {len(sub_hits):,}, a different answer"
        print(f"  {word:<16} {len(hits):>7,} hits  {human_time(seconds)}"
              f"   (substring: {human_time(sub_seconds)}){flag}")

    # ---- the inverted index ---------------------------------------------
    rule("2 · building the inverted index")
    rss_before = peak_rss_bytes()
    t0 = time.perf_counter()
    index = build_inverted_index(passages)
    build_seconds = time.perf_counter() - t0
    size = index_size_bytes(index)
    postings_total = sum(len(v) for v in index.values())

    m["inverted"] = {
        "build_seconds": build_seconds,
        "vocabulary": len(index),
        "postings": postings_total,
        "size_bytes": size,
        "size_vs_corpus": size / corpus_bytes,
        "postings_per_passage": postings_total / n,
        "rss_after_bytes": peak_rss_bytes(),
        "rss_before_bytes": rss_before,
    }
    print(f"  {len(index):,} distinct words, {postings_total:,} postings")
    print(f"  built in {human_time(build_seconds)}")
    print(f"  {human_bytes(size)} — {size / corpus_bytes:.2f}x the corpus text")

    rule("3 · looking a word up in it")
    #
    # One dict lookup is far below the clock's resolution — timing a single
    # one reports zero, which is not a measurement. Time a great many and
    # divide.
    REPS = 200_000
    m["lookup_reps"] = REPS
    m["lookup"] = {}
    for word in PROBE_WORDS:
        get = index.get
        t0 = time.perf_counter()
        for _ in range(REPS):
            hits = get(word, ())
        total = time.perf_counter() - t0
        per = total / REPS
        m["lookup"][word] = {"hits": len(hits), "seconds": per,
                             "total_seconds": total, "reps": REPS,
                             "speedup": m["scan"][word]["seconds"] / per}
        print(f"  {word:<16} {len(hits):>7,} hits  {per * 1e9:>6.0f} ns"
              f"   {m['scan'][word]['seconds'] / per:>12,.0f}x faster than the scan")

    m["mean_speedup"] = sum(v["speedup"] for v in m["lookup"].values()) / len(m["lookup"])

    # ---- the vector side, at the same scale ------------------------------
    rule("4 · the other index: brute-force nearest neighbour")
    vectors = normalized(embed_corpus(n))
    m["vectors"] = {
        "n": int(len(vectors)),
        "dims": int(vectors.shape[1]),
        "bytes": int(vectors.nbytes),
        "bytes_vs_corpus": vectors.nbytes / corpus_bytes,
    }
    print(f"  {len(vectors):,} vectors x {vectors.shape[1]} dims = "
          f"{human_bytes(vectors.nbytes)}  "
          f"({vectors.nbytes / corpus_bytes:.2f}x the corpus text)")

    rng = np.random.default_rng(11)
    queries = vectors[rng.choice(len(vectors), size=50, replace=False)]

    times = []
    for q in queries:
        t0 = time.perf_counter()
        brute_force_topk(vectors, q, k=10)
        times.append(time.perf_counter() - t0)
    times.sort()
    m["brute_force"] = {
        "queries": len(times),
        "median_seconds": times[len(times) // 2],
        "p99_seconds": times[int(len(times) * 0.99)],
        "comparisons_per_query": int(len(vectors)),
        "multiplications_per_query": int(len(vectors) * vectors.shape[1]),
        "build_seconds": 0.0,
    }
    print(f"  median {human_time(m['brute_force']['median_seconds'])} per query")
    print(f"  every query compares against all {len(vectors):,} vectors — "
          f"{len(vectors) * vectors.shape[1]:,} multiply-adds")
    print(f"  build time: none. there is no index. that is the trade.")

    # ---- the two structures, side by side --------------------------------
    rule("5 · two indexes over one corpus")
    m["comparison"] = {
        "inverted_build_seconds": build_seconds,
        "inverted_size_bytes": size,
        "inverted_query_seconds": m["lookup"]["block"]["seconds"],
        "vector_build_seconds": 0.0,
        "vector_size_bytes": int(vectors.nbytes),
        "vector_query_seconds": m["brute_force"]["median_seconds"],
    }
    print(f"  inverted index: {human_time(build_seconds)} to build, "
          f"{human_bytes(size)}, "
          f"{m['lookup']['block']['seconds'] * 1e9:.0f} ns per lookup")
    print(f"  vectors:        no build, "
          f"{human_bytes(vectors.nbytes)}, "
          f"{human_time(m['brute_force']['median_seconds'])} per query")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
