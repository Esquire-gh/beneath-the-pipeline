#!/usr/bin/env python3
"""Module 8 — worked solution, and the source of the module page's numbers.

    python exercises/08-retrieve/solution.py --scale part2 --queries 1000

This file is also the instrument the rest of the site uses: modules 11, 12 and
15 import `evaluate`, `ndcg_at_k` and the BM25 index from here.
"""
import math
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (embed_corpus, embed_queries, eval_corpus, human_time,   # noqa: E402
                    load_queries, normalized, resolve_n, rule, scale_parser,
                    usable_queries, write_measurements)

SLUG = "08-retrieve"
TOKEN = re.compile(r"[a-z0-9]+")

# A short, ordinary English stopword list — used only by the "improvement"
# that module 8 measures and rejects.
STOPWORDS = set("""a an and are as at be by for from has have how in is it its of
on or that the this to was were what when where which who why will with""".split())


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# --------------------------------------------------------------------------
# the index
# --------------------------------------------------------------------------

class Index:
    """Module 7's inverted index, with term frequencies kept alongside.

    Two representations of the same postings: dict-of-lists, which is what the
    readable scorer walks, and flat arrays, which is what the vectorised
    scorer needs to run 1,000 queries in a reasonable time. The solution
    asserts they agree.
    """

    def __init__(self, docs: list[str], tokenizer=tokenize):
        import numpy as np

        self.N = len(docs)
        self.tokenize = tokenizer
        self.postings: dict[str, list[tuple[int, int]]] = {}
        self.doc_len = [0] * len(docs)

        for doc_id, text in enumerate(docs):
            counts: dict[str, int] = {}
            for token in tokenizer(text):
                counts[token] = counts.get(token, 0) + 1
            self.doc_len[doc_id] = sum(counts.values())
            for term, tf in counts.items():
                self.postings.setdefault(term, []).append((doc_id, tf))

        self.df = {term: len(p) for term, p in self.postings.items()}
        self.avgdl = sum(self.doc_len) / max(self.N, 1)
        self.doc_len_arr = np.asarray(self.doc_len, dtype="float32")

        self.fast: dict[str, tuple] = {}
        for term, plist in self.postings.items():
            ids = np.fromiter((d for d, _ in plist), dtype="int32", count=len(plist))
            tfs = np.fromiter((t for _, t in plist), dtype="float32", count=len(plist))
            self.fast[term] = (ids, tfs)

    @property
    def n_postings(self) -> int:
        return sum(len(p) for p in self.postings.values())


# --------------------------------------------------------------------------
# three scorers, readable
# --------------------------------------------------------------------------

def score_term_counts(index: Index, query: str) -> dict[int, float]:
    scores: dict[int, float] = {}
    for term in index.tokenize(query):
        for doc, tf in index.postings.get(term, ()):
            scores[doc] = scores.get(doc, 0.0) + tf
    return scores


def score_tfidf(index: Index, query: str) -> dict[int, float]:
    scores: dict[int, float] = {}
    for term in index.tokenize(query):
        df = index.df.get(term)
        if not df:
            continue
        idf = math.log(index.N / df)
        for doc, tf in index.postings[term]:
            scores[doc] = scores.get(doc, 0.0) + (1 + math.log(tf)) * idf
    for doc in scores:
        scores[doc] /= math.sqrt(index.doc_len[doc]) or 1.0
    return scores


def score_bm25(index: Index, query: str, k1: float = 1.2,
               b: float = 0.75) -> dict[int, float]:
    scores: dict[int, float] = {}
    for term in index.tokenize(query):
        df = index.df.get(term)
        if not df:
            continue
        idf = math.log(1 + (index.N - df + 0.5) / (df + 0.5))
        for doc, tf in index.postings[term]:
            norm = 1 - b + b * index.doc_len[doc] / index.avgdl
            scores[doc] = scores.get(doc, 0.0) + idf * (tf * (k1 + 1)) / (tf + k1 * norm)
    return scores


def score_bm25_fast(index: Index, query: str, k1: float = 1.2, b: float = 0.75):
    """The same arithmetic, one array operation per query term.

    Identical results, fast enough to run a thousand queries. Verified against
    the readable version in main().
    """
    import numpy as np
    scores = np.zeros(index.N, dtype="float32")
    for term in index.tokenize(query):
        entry = index.fast.get(term)
        if entry is None:
            continue
        ids, tfs = entry
        df = len(ids)
        idf = math.log(1 + (index.N - df + 0.5) / (df + 0.5))
        norm = 1 - b + b * index.doc_len_arr[ids] / index.avgdl
        np.add.at(scores, ids, idf * (tfs * (k1 + 1)) / (tfs + k1 * norm))
    return scores


# --------------------------------------------------------------------------
# the measurements — the actual subject of this module
# --------------------------------------------------------------------------

def precision_at_k(ranked: list[int], relevant: set[int], k: int = 10) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for doc in ranked[:k] if doc in relevant) / k


def ndcg_at_k(ranked: list[int], relevant: set[int], k: int = 10) -> float:
    if not relevant:
        return 0.0
    dcg = sum(1.0 / math.log2(i + 2)
              for i, doc in enumerate(ranked[:k]) if doc in relevant)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0


def reciprocal_rank(ranked: list[int], relevant: set[int], k: int = 10) -> float:
    for i, doc in enumerate(ranked[:k]):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def evaluate(rank_fn, qids, queries, judged, pid_to_doc, k: int = 10) -> dict:
    """Run a ranking function over a query set and report what it scored.

    rank_fn(query_text) -> list of doc ids, best first.
    """
    p = n = mrr = 0.0
    latencies = []
    for qid in qids:
        relevant = {pid_to_doc[pid] for pid in judged[qid]}
        t0 = time.perf_counter()
        ranked = rank_fn(queries[qid])
        latencies.append(time.perf_counter() - t0)
        p += precision_at_k(ranked, relevant, k)
        n += ndcg_at_k(ranked, relevant, k)
        mrr += reciprocal_rank(ranked, relevant, k)
    latencies.sort()
    return {
        "queries": len(qids),
        f"p_at_{k}": p / len(qids),
        f"ndcg_at_{k}": n / len(qids),
        f"mrr_at_{k}": mrr / len(qids),
        "median_seconds": latencies[len(latencies) // 2],
        "p99_seconds": latencies[min(int(len(latencies) * 0.99), len(latencies) - 1)],
    }


def topk_from_array(scores, k=10):
    import numpy as np
    if k >= len(scores):
        return list(np.argsort(-scores))
    top = np.argpartition(-scores, k)[:k]
    return list(top[np.argsort(-scores[top])])


def top_k(scores: dict[int, float], k: int = 10) -> list[int]:
    return [doc for doc, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]


# --------------------------------------------------------------------------

def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    ap.add_argument("--queries", type=int, default=1000)
    args = ap.parse_args()
    n = resolve_n(args)

    import numpy as np

    m = {"n_passages": n}

    corpus = eval_corpus(n)
    pids = [p for p, _ in corpus]
    docs = [t for _, t in corpus]
    pid_to_doc = {p: i for i, p in enumerate(pids)}

    print(f"indexing {len(docs):,} passages…")
    t0 = time.perf_counter()
    index = Index(docs)
    m["index_build_seconds"] = time.perf_counter() - t0
    m["vocabulary"] = len(index.postings)
    m["postings"] = index.n_postings
    m["avgdl"] = index.avgdl
    print(f"  {len(index.postings):,} terms, {index.n_postings:,} postings, "
          f"{human_time(m['index_build_seconds'])}")

    queries = load_queries()
    judged = usable_queries(set(pids))
    qids = sorted(judged)[:args.queries]
    m["n_queries"] = len(qids)
    m["n_queries_available"] = len(judged)
    print(f"  {len(judged):,} queries have judgments in this corpus; "
          f"scoring {len(qids):,}")

    # the readable and fast BM25 must agree, or the rest is meaningless
    probe = queries[qids[0]]
    slow = score_bm25(index, probe)
    fast = score_bm25_fast(index, probe)
    worst = max(abs(fast[d] - s) for d, s in slow.items()) if slow else 0.0
    m["bm25_readable_vs_fast_max_diff"] = float(worst)
    print(f"  readable and vectorised BM25 agree to {worst:.2e}")

    # ---- how many documents even match? ---------------------------------
    matched = []
    for qid in qids[:200]:
        hits = set()
        for term in tokenize(queries[qid]):
            hits.update(d for d, _ in index.postings.get(term, ()))
        matched.append(len(hits))
    matched.sort()
    m["matching_docs"] = {
        "median": matched[len(matched) // 2],
        "max": matched[-1],
        "returned": 10,
    }
    print(f"  a median query matches {matched[len(matched) // 2]:,} passages. "
          f"you return 10.")

    # ---- the three scorers ----------------------------------------------
    rule("1 · what each scorer likes")
    #
    # The textbook complaint about raw term counts is that long documents win.
    # Check whether that is true HERE before repeating it: MS MARCO passages
    # are deliberately uniform in length, so the classic story may not fire.
    lens = sorted(index.doc_len)
    m["length_distribution"] = {
        "p10": lens[len(lens) // 10],
        "median": lens[len(lens) // 2],
        "p90": lens[len(lens) * 9 // 10],
        "max": lens[-1],
        "mean": index.avgdl,
    }
    print(f"  passage lengths: p10 {lens[len(lens)//10]}, "
          f"median {lens[len(lens)//2]}, p90 {lens[len(lens)*9//10]}, "
          f"max {lens[-1]} tokens")

    q = queries[qids[0]]
    m["length_bias"] = {"query": q}
    for name, fn in (("term_counts", score_term_counts),
                     ("tfidf", score_tfidf),
                     ("bm25", score_bm25)):
        ranked = top_k(fn(index, q))
        lengths = [index.doc_len[d] for d in ranked]
        m["length_bias"][name] = {
            "mean_top10_length": sum(lengths) / len(lengths),
            "corpus_mean_length": index.avgdl,
            "top1_text": " ".join(docs[ranked[0]].split())[:230],
        }
        print(f"  {name:<12} top-10 mean length "
              f"{sum(lengths) / len(lengths):>6.0f} tokens "
              f"(corpus average {index.avgdl:.0f})")

    # Where does a raw term-count score actually come from? Split each query's
    # score contribution into ordinary words and stopwords.
    stop_share = []
    for qid in qids[:300]:
        terms = tokenize(queries[qid])
        total = stop = 0
        for term in terms:
            postings = index.postings.get(term, ())
            weight = sum(tf for _, tf in postings)
            total += weight
            if term in STOPWORDS:
                stop += weight
        if total:
            stop_share.append(stop / total)
    m["stopword_share"] = {
        "queries": len(stop_share),
        "mean": sum(stop_share) / len(stop_share) if stop_share else 0.0,
        "note": "share of a raw term-count score contributed by stopwords",
    }
    print(f"  {m['stopword_share']['mean']:.0%} of a raw term-count score comes "
          f"from stopwords")

    rule("2 · scoring the scorers")
    m["runs"] = {}

    def run(key, label, rank_fn):
        # Keys have to be plain identifiers: the build script looks measurements
        # up by dotted path, so a key containing a dot or a space is unreachable.
        res = evaluate(rank_fn, qids, queries, judged, pid_to_doc)
        res["label"] = label
        m["runs"][key] = res
        print(f"  {label:<26} P@10 {res['p_at_10']:.4f}   "
              f"NDCG@10 {res['ndcg_at_10']:.4f}   "
              f"MRR@10 {res['mrr_at_10']:.4f}   "
              f"{human_time(res['median_seconds'])}/query")
        return res

    run("term_counts", "raw term counts",
        lambda q: top_k(score_term_counts(index, q)))
    run("tfidf", "tf-idf", lambda q: top_k(score_tfidf(index, q)))
    baseline = run("bm25", "BM25 (k1=1.2, b=0.75)",
                   lambda q: topk_from_array(score_bm25_fast(index, q)))

    # ---- the vector side -------------------------------------------------
    rule("3 · the same queries, by vector similarity")
    vectors = normalized(embed_corpus(n))
    qvecs = normalized(embed_queries([queries[qid] for qid in qids]))
    qvec_by_id = {qid: qvecs[i] for i, qid in enumerate(qids)}

    def dense_rank(query_text, _cache={}):
        raise RuntimeError("unused")

    dense_res = {"p": 0.0, "n": 0.0, "mrr": 0.0}
    lat = []
    for i, qid in enumerate(qids):
        relevant = {pid_to_doc[pid] for pid in judged[qid]}
        t0 = time.perf_counter()
        scores = vectors @ qvec_by_id[qid]
        ranked = topk_from_array(scores)
        lat.append(time.perf_counter() - t0)
        dense_res["p"] += precision_at_k(ranked, relevant)
        dense_res["n"] += ndcg_at_k(ranked, relevant)
        dense_res["mrr"] += reciprocal_rank(ranked, relevant)
    lat.sort()
    m["runs"]["dense"] = {
        "label": "dense (MiniLM, brute force)",
        "queries": len(qids),
        "p_at_10": dense_res["p"] / len(qids),
        "ndcg_at_10": dense_res["n"] / len(qids),
        "mrr_at_10": dense_res["mrr"] / len(qids),
        "median_seconds": lat[len(lat) // 2],
        "p99_seconds": lat[int(len(lat) * 0.99)],
    }
    d = m["runs"]["dense"]
    print(f"  {'dense (MiniLM, brute force)':<26} P@10 {d['p_at_10']:.4f}   "
          f"NDCG@10 {d['ndcg_at_10']:.4f}   MRR@10 {d['mrr_at_10']:.4f}   "
          f"{human_time(d['median_seconds'])}/query")

    # ---- the part every tutorial skips ----------------------------------
    rule("4 · four changes that sound like improvements")
    m["tuning"] = {}

    def tuned(name, description, rank_fn):
        res = evaluate(rank_fn, qids, queries, judged, pid_to_doc)
        delta = res["ndcg_at_10"] - baseline["ndcg_at_10"]
        m["tuning"][name] = {
            "description": description,
            "ndcg_at_10": res["ndcg_at_10"],
            "p_at_10": res["p_at_10"],
            "delta_ndcg": delta,
            "helped": delta > 0,
        }
        print(f"  {description:<44} NDCG {res['ndcg_at_10']:.4f}  "
              f"{delta:+.4f}  {'better' if delta > 0 else 'WORSE'}")
        return res

    def no_stopwords(text):
        return [t for t in tokenize(text) if t not in STOPWORDS]

    print(f"  {'BM25 baseline':<44} NDCG {baseline['ndcg_at_10']:.4f}")

    stop_index = Index(docs, tokenizer=no_stopwords)
    tuned("drop_stopwords", "drop stopwords from the index and query",
          lambda q: topk_from_array(score_bm25_fast(stop_index, q)))

    tuned("k1_high", "raise k1 to 2.5 — reward repeated terms more",
          lambda q: topk_from_array(score_bm25_fast(index, q, k1=2.5)))

    tuned("b_zero", "set b to 0 — stop penalising long documents",
          lambda q: topk_from_array(score_bm25_fast(index, q, b=0.0)))

    tuned("b_one", "set b to 1 — penalise long documents fully",
          lambda q: topk_from_array(score_bm25_fast(index, q, b=1.0)))

    hurt = [k for k, v in m["tuning"].items() if not v["helped"]]
    m["dense_caveat"] = (
        "all-MiniLM-L6-v2 was trained on data that includes MS MARCO, so its "
        "score here flatters it relative to a corpus it has never seen. The "
        "comparison is honest about ordering on THIS benchmark and should not "
        "be read as 'dense beats BM25 by 0.19 everywhere'.")
    m["tuning_summary"] = {
        "n_tried": len(m["tuning"]),
        "n_hurt": len(hurt),
        "hurt": hurt,
        "baseline_ndcg": baseline["ndcg_at_10"],
    }
    print(f"\n  {len(hurt)} of {len(m['tuning'])} plausible improvements "
          f"made the ranking worse.")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
