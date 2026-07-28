#!/usr/bin/env python3
"""Module 8 — Retrieve: ranked by what?  YOUR WORK GOES HERE.

Five TODOs. Three scorers, then the two measurements that tell you whether a
scorer is any good. The measurements are the point of the module.

    python exercises/08-retrieve/starter.py --queries 200
    python exercises/08-retrieve/verify.py

Needs: numpy. Needs the corpus:
    python data/fetch.py --only msmarco
"""
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule, scale_parser   # noqa: E402

TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# ==========================================================================
# The index you are scoring against — built for you, from module 7's idea
# ==========================================================================
#
# postings[term] = list of (doc, term frequency in that doc)
# doc_len[doc]   = how many tokens that document has
# df[term]       = how many documents contain the term
# N              = number of documents
# avgdl          = mean document length

class Index:
    def __init__(self, docs: list[str]):
        self.N = len(docs)
        self.postings: dict[str, list[tuple[int, int]]] = {}
        self.doc_len = [0] * len(docs)
        for doc_id, text in enumerate(docs):
            counts: dict[str, int] = {}
            for token in tokenize(text):
                counts[token] = counts.get(token, 0) + 1
            self.doc_len[doc_id] = sum(counts.values())
            for term, tf in counts.items():
                self.postings.setdefault(term, []).append((doc_id, tf))
        self.df = {term: len(p) for term, p in self.postings.items()}
        self.avgdl = sum(self.doc_len) / max(self.N, 1)


# ==========================================================================
# TODO 1 — score by raw term counts
# ==========================================================================
#
# The most obvious thing anyone tries: add up how many times the query's words
# appear in each document. Return {doc: score} for documents with any match.
#
# Run it, then look at the lengths of the documents it likes.

def score_term_counts(index: Index, query: str) -> dict[int, float]:
    scores: dict[int, float] = {}
    # TODO
    ...
    return scores


# ==========================================================================
# TODO 2 — tf-idf: a rare word says more than a common one
# ==========================================================================
#
# Two fixes at once.
#
#   term frequency   how often the word occurs in this document, damped so the
#                    tenth occurrence counts for less than the first:
#                        tf_weight = 1 + log(tf)
#
#   inverse document frequency
#                    how rare the word is across the whole corpus. A word in
#                    every document tells you nothing:
#                        idf = log(N / df)
#
# score = sum over query terms of tf_weight * idf, divided by sqrt(doc_len)
# to stop long documents winning by sheer size.

def score_tfidf(index: Index, query: str) -> dict[int, float]:
    scores: dict[int, float] = {}
    # TODO
    ...
    return scores


# ==========================================================================
# TODO 3 — BM25, which is what everyone actually uses
# ==========================================================================
#
# Same two ideas, tuned by forty years of measurement:
#
#   idf(t)  = log(1 + (N - df + 0.5) / (df + 0.5))
#
#   score  += idf(t) * ( tf * (k1 + 1) )
#                    / ( tf + k1 * (1 - b + b * doc_len/avgdl) )
#
# k1 controls how fast extra occurrences stop helping (usually 1.2).
# b  controls how hard long documents are penalised (usually 0.75; b=0 turns
#    the length penalty off entirely).
#
# Both are knobs somebody set for you. In TODO 5 you get to move them and find
# out whether your instinct about which way is any good.

def score_bm25(index: Index, query: str, k1: float = 1.2,
               b: float = 0.75) -> dict[int, float]:
    scores: dict[int, float] = {}
    # TODO
    ...
    return scores


# ==========================================================================
# TODO 4 — precision@k: of the k you returned, how many were right?
# ==========================================================================
#
# `ranked` is a list of doc ids, best first. `relevant` is the set of doc ids
# somebody judged relevant for this query.
#
# Return the fraction of the top k that are in `relevant`.
# If fewer than k results came back, still divide by k — returning three good
# results out of a requested ten is not perfect precision.

def precision_at_k(ranked: list[int], relevant: set[int], k: int = 10) -> float:
    # TODO
    ...


# ==========================================================================
# TODO 5 — NDCG@k: being right early is worth more
# ==========================================================================
#
# Precision does not care whether the right answer was first or tenth. NDCG
# does, by discounting each position logarithmically.
#
#   DCG  = sum over positions i (counting from 1) of
#              relevance(i) / log2(i + 1)
#          where relevance is 1 if the document at that position is relevant
#
#   IDCG = the DCG of the best possible ranking — every relevant document
#          first, as many as exist or as fit in k
#
#   NDCG = DCG / IDCG, or 0.0 when there is nothing relevant to find
#
# Return NDCG@k.

def ndcg_at_k(ranked: list[int], relevant: set[int], k: int = 10) -> float:
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def top_k(scores: dict[int, float], k: int = 10) -> list[int]:
    return [doc for doc, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]


def main() -> None:
    ap = scale_parser(__doc__, default="small")
    ap.add_argument("--queries", type=int, default=200)
    args = ap.parse_args()

    from common import eval_corpus, load_queries, resolve_n, usable_queries

    n = resolve_n(args)
    corpus = eval_corpus(n)
    pids = [p for p, _ in corpus]
    docs = [t for _, t in corpus]
    pid_to_doc = {p: i for i, p in enumerate(pids)}

    print(f"indexing {len(docs):,} passages…")
    index = Index(docs)

    queries = load_queries()
    judged = usable_queries(set(pids))
    qids = sorted(judged)[:args.queries]

    rule("1 · what raw term counts like")
    q = queries[qids[0]]
    print(f"  query: {q!r}")
    for name, fn in (("term counts", score_term_counts),
                     ("tf-idf", score_tfidf),
                     ("BM25", score_bm25)):
        scores = fn(index, q) or {}
        ranked = top_k(scores)
        lengths = [index.doc_len[d] for d in ranked]
        print(f"  {name:<12} top-10 mean length "
              f"{sum(lengths) / len(lengths) if lengths else 0:>6.0f} tokens")

    rule("2 · scoring the scorers")
    for name, fn in (("term counts", score_term_counts),
                     ("tf-idf", score_tfidf),
                     ("BM25", score_bm25)):
        p_sum = n_sum = 0.0
        for qid in qids:
            relevant = {pid_to_doc[p] for p in judged[qid]}
            ranked = top_k(fn(index, queries[qid]) or {})
            p_sum += precision_at_k(ranked, relevant) or 0.0
            n_sum += ndcg_at_k(ranked, relevant) or 0.0
        print(f"  {name:<12} P@10 {p_sum / len(qids):.4f}   "
              f"NDCG@10 {n_sum / len(qids):.4f}")


if __name__ == "__main__":
    main()
