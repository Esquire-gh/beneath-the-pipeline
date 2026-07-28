#!/usr/bin/env python3
"""Module 15 — the pipeline, rebuilt, and measured against reality.

    python exercises/15-rebuilt-and-measured/solution.py --scale part2

Two tables.

    First: what each retrieval stage adds. BM25, dense, the two fused, then a
    cross-encoder rerank over the top 50 — scored with module 8's harness.

    Second: the reckoning. The same complete pipeline run three times over the
    same twenty documents, differing only in which program turned the PDFs
    into text.
"""
import json
import math
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (embed_corpus, embed_queries, eval_corpus, human_time,   # noqa: E402
                    iter_passages, load_queries, normalized, resolve_n, rule,
                    scale_parser, usable_queries, write_measurements)

SLUG = "15-rebuilt-and-measured"
EVAL_DOCS = REPO / "data" / "eval_docs"
TOKEN = re.compile(r"[a-z0-9]+")

RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def load_module(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# the pipeline, from parts built in Part II
# --------------------------------------------------------------------------

def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Combine ranked lists without needing their scores to be comparable.

    BM25 scores and cosine similarities live on different scales and cannot be
    added. Ranks can: a document's contribution is 1/(k + its rank), summed
    across the lists. The constant k damps the influence of the very top
    positions so one list cannot dominate.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return [d for d, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


class Pipeline:
    """BM25 + dense + fusion + rerank over one set of documents."""

    def __init__(self, texts: list[str], model=None, reranker=None,
                 vectors=None):
        import numpy as np
        from sentence_transformers import SentenceTransformer

        self.texts = texts
        self.N = len(texts)
        self.postings: dict[str, list[tuple[int, int]]] = {}
        self.doc_len = []
        for i, text in enumerate(texts):
            counts: dict[str, int] = {}
            for tok in tokenize(text):
                counts[tok] = counts.get(tok, 0) + 1
            self.doc_len.append(sum(counts.values()))
            for term, tf in counts.items():
                self.postings.setdefault(term, []).append((i, tf))
        self.avgdl = sum(self.doc_len) / max(self.N, 1)

        self.model = model or SentenceTransformer("all-MiniLM-L6-v2")
        if vectors is None:
            vecs = self.model.encode(texts, batch_size=64,
                                     show_progress_bar=False).astype("float32")
            self.vectors = normalized(vecs)
        else:
            self.vectors = vectors
        self.reranker = reranker

    def bm25(self, query: str, k=10, k1=1.2, b=0.75) -> list[int]:
        scores: dict[int, float] = {}
        for term in set(tokenize(query)):
            plist = self.postings.get(term)
            if not plist:
                continue
            idf = math.log(1 + (self.N - len(plist) + 0.5) / (len(plist) + 0.5))
            for doc, tf in plist:
                norm = 1 - b + b * self.doc_len[doc] / self.avgdl
                scores[doc] = scores.get(doc, 0.0) + \
                    idf * (tf * (k1 + 1)) / (tf + k1 * norm)
        return [d for d, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]

    def dense(self, qvec, k=10) -> list[int]:
        import numpy as np
        scores = self.vectors @ qvec
        if k >= len(scores):
            return list(np.argsort(-scores))
        top = np.argpartition(-scores, k)[:k]
        return [int(x) for x in top[np.argsort(-scores[top])]]

    def fused(self, query: str, qvec, k=10, pool=100) -> list[int]:
        return reciprocal_rank_fusion(
            [self.bm25(query, k=pool), self.dense(qvec, k=pool)])[:k]

    def reranked(self, query: str, qvec, k=10, pool=50) -> list[int]:
        candidates = self.fused(query, qvec, k=pool, pool=max(pool, 100))
        if not self.reranker or not candidates:
            return candidates[:k]
        pairs = [(query, self.texts[d][:2000]) for d in candidates]
        scores = self.reranker.predict(pairs, show_progress_bar=False)
        order = sorted(range(len(candidates)), key=lambda i: -scores[i])
        return [candidates[i] for i in order[:k]]


# --------------------------------------------------------------------------
# the three extraction paths
# --------------------------------------------------------------------------

def extract_pymupdf(path: Path) -> str:
    import fitz
    with fitz.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


def extract_pdfplumber(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract_with_ocr_fallback(path: Path, min_chars: int = 40) -> str:
    """What a serious pipeline does: try the cheap path, detect that it failed,
    fall back to OCR. Module 13's ladder, implemented."""
    import io

    import fitz
    import pytesseract
    from PIL import Image

    text = extract_pymupdf(path)
    if len(text.strip()) >= min_chars:
        return text
    out = []
    with fitz.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            out.append(pytesseract.image_to_string(img))
    return "\n".join(out)


# --------------------------------------------------------------------------

def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--rerank-pool", type=int, default=50)
    ap.add_argument("--distractors", type=int, default=2000)
    args = ap.parse_args()
    n = resolve_n(args)

    import numpy as np
    from sentence_transformers import CrossEncoder, SentenceTransformer

    retrieve = load_module("retrieve",
                           REPO / "exercises" / "08-retrieve" / "solution.py")
    m = {"n_passages": n, "rerank_pool": args.rerank_pool,
         "reranker": RERANKER}

    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("loading the reranker…")
    reranker = CrossEncoder(RERANKER)

    # ======================================================================
    rule("TABLE 1 · what each stage adds")
    # ======================================================================
    corpus = eval_corpus(n)
    pids = [p for p, _ in corpus]
    texts = [t for _, t in corpus]
    pid_to_doc = {p: i for i, p in enumerate(pids)}
    vectors = normalized(embed_corpus(n))

    queries = load_queries()
    judged = usable_queries(set(pids))
    qids = sorted(judged)[:args.queries]
    qvecs = normalized(embed_queries([queries[qid] for qid in qids]))

    pipe = Pipeline(texts, model=model, reranker=reranker, vectors=vectors)
    print(f"  {len(texts):,} passages, {len(qids)} judged queries")

    stages = [
        ("bm25", "BM25 alone", lambda q, v: pipe.bm25(q, k=10)),
        ("dense", "dense alone", lambda q, v: pipe.dense(v, k=10)),
        ("fused", "fused (reciprocal rank fusion)",
         lambda q, v: pipe.fused(q, v, k=10)),
        ("reranked", f"fused, then reranked over {args.rerank_pool}",
         lambda q, v: pipe.reranked(q, v, k=10, pool=args.rerank_pool)),
    ]

    m["stages"] = {}
    previous = None
    for key, label, fn in stages:
        ndcg = p10 = mrr = 0.0
        lat = []
        for i, qid in enumerate(qids):
            relevant = {pid_to_doc[p] for p in judged[qid]}
            t0 = time.perf_counter()
            ranked = [int(x) for x in fn(queries[qid], qvecs[i])]
            lat.append(time.perf_counter() - t0)
            ndcg += retrieve.ndcg_at_k(ranked, relevant, 10)
            p10 += retrieve.precision_at_k(ranked, relevant, 10)
            mrr += retrieve.reciprocal_rank(ranked, relevant, 10)
        lat.sort()
        row = {
            "label": label,
            "ndcg_at_10": ndcg / len(qids),
            "p_at_10": p10 / len(qids),
            "mrr_at_10": mrr / len(qids),
            "median_seconds": lat[len(lat) // 2],
            "p99_seconds": lat[int(len(lat) * 0.99)],
        }
        row["gain_over_previous"] = (row["ndcg_at_10"] - previous
                                     if previous is not None else None)
        previous = row["ndcg_at_10"]
        m["stages"][key] = row
        gain = "" if row["gain_over_previous"] is None else \
            f"  {row['gain_over_previous']:+.4f}"
        print(f"  {label:<38} NDCG {row['ndcg_at_10']:.4f}{gain:<10}  "
              f"{human_time(row['median_seconds'])}/query")

    s = m["stages"]
    m["architecture_spread"] = (max(v["ndcg_at_10"] for v in s.values())
                                - min(v["ndcg_at_10"] for v in s.values()))
    m["rerank_cost"] = (s["reranked"]["median_seconds"]
                        / s["fused"]["median_seconds"])
    print(f"\n  best minus worst architecture: {m['architecture_spread']:.4f} NDCG")
    print(f"  the rerank costs {m['rerank_cost']:.0f}x the fused query it "
          f"reorders")

    # ======================================================================
    rule("TABLE 2 · the same pipeline, three extractions")
    # ======================================================================
    truth_path = EVAL_DOCS / "ground_truth.json"
    if not truth_path.exists():
        sys.exit("missing evaluation documents — run: python data/make_eval_docs.py")
    truth = json.loads(truth_path.read_text())
    doc_keys = sorted(truth["documents"])
    doc_files = {k: EVAL_DOCS / "pdf" / truth["documents"][k]["file"]
                 for k in doc_keys}
    eval_queries = truth["queries"]

    n_scanned = sum(1 for k in doc_keys if truth["documents"][k]["scanned"])
    print(f"  {len(doc_keys)} documents ({n_scanned} of them scanned), "
          f"{len(eval_queries)} queries, "
          f"{args.distractors:,} distractor passages")

    distractors = [t for _, t in iter_passages(args.distractors)]

    extractors = [
        ("pymupdf", "PyMuPDF", extract_pymupdf),
        ("pdfplumber", "pdfplumber", extract_pdfplumber),
        ("ocr_fallback", "PyMuPDF, OCR when it returns nothing",
         extract_with_ocr_fallback),
    ]

    m["extractions"] = {}
    for key, label, extract in extractors:
        t0 = time.perf_counter()
        extracted = {k: extract(doc_files[k]) for k in doc_keys}
        extract_seconds = time.perf_counter() - t0

        empty = [k for k in doc_keys if len(extracted[k].strip()) < 40]
        chars = sum(len(extracted[k]) for k in doc_keys)

        docs_texts = [extracted[k] for k in doc_keys] + distractors
        pipe2 = Pipeline(docs_texts, model=model, reranker=reranker)
        qvecs2 = normalized(embed_queries([q["query"] for q in eval_queries]))

        results = {}
        for stage_key, stage_label, fn in (
                ("bm25", "BM25", lambda q, v: pipe2.bm25(q, k=10)),
                ("dense", "dense", lambda q, v: pipe2.dense(v, k=10)),
                ("fused", "fused", lambda q, v: pipe2.fused(q, v, k=10)),
                ("reranked", "reranked",
                 lambda q, v: pipe2.reranked(q, v, k=10,
                                             pool=args.rerank_pool))):
            ndcg = hits1 = hits10 = 0.0
            by_kind = {"text": [0, 0], "scanned": [0, 0]}
            for i, q in enumerate(eval_queries):
                target = doc_keys.index(q["answer"])
                ranked = [int(x) for x in fn(q["query"], qvecs2[i])]
                ndcg += retrieve.ndcg_at_k(ranked, {target}, 10)
                hit10 = target in ranked[:10]
                hits10 += hit10
                hits1 += bool(ranked and ranked[0] == target)
                bucket = "scanned" if q["scanned"] else "text"
                by_kind[bucket][0] += hit10
                by_kind[bucket][1] += 1
            results[stage_key] = {
                "label": stage_label,
                "ndcg_at_10": ndcg / len(eval_queries),
                "accuracy_at_1": hits1 / len(eval_queries),
                "accuracy_at_10": hits10 / len(eval_queries),
                "text_accuracy": by_kind["text"][0] / max(by_kind["text"][1], 1),
                "scanned_accuracy": (by_kind["scanned"][0]
                                     / max(by_kind["scanned"][1], 1)),
            }

        m["extractions"][key] = {
            "label": label,
            "extract_seconds": extract_seconds,
            "characters": chars,
            "empty_documents": len(empty),
            "empty_list": empty,
            "stages": results,
        }
        r = m["extractions"][key]
        print(f"\n  {label}")
        print(f"    {len(empty)} of {len(doc_keys)} documents yielded no text; "
              f"{chars:,} characters total; {human_time(extract_seconds)}")
        for sk in ("bm25", "dense", "fused", "reranked"):
            v = results[sk]
            print(f"    {v['label']:<10} NDCG {v['ndcg_at_10']:.4f}   "
                  f"top-10 {v['accuracy_at_10']:.1%}   "
                  f"(text {v['text_accuracy']:.0%} / "
                  f"scanned {v['scanned_accuracy']:.0%})")

    # ---- the finding ----------------------------------------------------
    best_arch = {k: max(v["stages"][s]["ndcg_at_10"] for s in v["stages"])
                 for k, v in m["extractions"].items()}
    worst_arch = {k: min(v["stages"][s]["ndcg_at_10"] for s in v["stages"])
                  for k, v in m["extractions"].items()}
    m["spread"] = {
        "across_extractors": max(best_arch.values()) - min(best_arch.values()),
        "across_architectures_worst_extractor":
            max(worst_arch.values()) - min(worst_arch.values()),
        "across_architectures_within_best_extractor":
            max(m["extractions"]["ocr_fallback"]["stages"][s]["ndcg_at_10"]
                for s in m["extractions"]["ocr_fallback"]["stages"])
            - min(m["extractions"]["ocr_fallback"]["stages"][s]["ndcg_at_10"]
                  for s in m["extractions"]["ocr_fallback"]["stages"]),
        "msmarco_architecture_spread": m["architecture_spread"],
    }
    m["spread"]["extractor_beats_architecture"] = (
        m["spread"]["across_extractors"]
        > m["spread"]["across_architectures_within_best_extractor"])
    m["spread"]["ratio"] = (
        m["spread"]["across_extractors"]
        / max(m["spread"]["across_architectures_within_best_extractor"], 1e-9))

    # The sharpest form of the comparison: the WORST architecture on the good
    # extraction against the BEST architecture on a broken one.
    good = m["extractions"]["ocr_fallback"]["stages"]
    bad = m["extractions"]["pymupdf"]["stages"]
    worst_good_key = min(good, key=lambda k: good[k]["ndcg_at_10"])
    best_bad_key = max(bad, key=lambda k: bad[k]["ndcg_at_10"])
    m["crossover"] = {
        "worst_architecture_good_extraction": good[worst_good_key]["ndcg_at_10"],
        "worst_architecture_name": good[worst_good_key]["label"],
        "best_architecture_bad_extraction": bad[best_bad_key]["ndcg_at_10"],
        "best_architecture_name": bad[best_bad_key]["label"],
        "gap": (good[worst_good_key]["ndcg_at_10"]
                - bad[best_bad_key]["ndcg_at_10"]),
    }
    m["scanned_share"] = n_scanned / len(doc_keys)
    print(f"\n  the WORST architecture ({worst_good_key}) on the good "
          f"extraction scores {good[worst_good_key]['ndcg_at_10']:.4f}")
    print(f"  the BEST  architecture ({best_bad_key}) on the broken "
          f"extraction scores {bad[best_bad_key]['ndcg_at_10']:.4f}")
    print(f"  no retrieval architecture closes a gap of "
          f"{m['crossover']['gap']:.4f}")

    rule("the finding")
    print(f"  spread between EXTRACTORS (best architecture each):  "
          f"{m['spread']['across_extractors']:.4f} NDCG")
    print(f"  spread between ARCHITECTURES (best extractor):       "
          f"{m['spread']['across_architectures_within_best_extractor']:.4f} NDCG")
    print(f"  the same spread on MS MARCO clean text:              "
          f"{m['architecture_spread']:.4f} NDCG")
    print(f"\n  extraction matters more than architecture: "
          f"{m['spread']['extractor_beats_architecture']}")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
