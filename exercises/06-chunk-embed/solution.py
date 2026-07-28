#!/usr/bin/env python3
"""Module 6 — worked solution, and the source of the module page's numbers.

    python exercises/06-chunk-embed/solution.py
    python exercises/06-chunk-embed/solution.py --scale part2

Read this after you have written your own.
"""
import math
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (human_bytes, human_time, iter_passages, resolve_n, rule,   # noqa: E402
                    scale_parser, write_measurements)

SLUG = "06-chunk-embed"
PDFS = REPO / "data" / "hard_pdfs"

CAT = "the cat sat on the mat"
FELINE = "a feline rested upon soft carpet"
UNRELATED = "quarterly revenue exceeded analyst expectations"
CONTRADICTION = "the cat did not sit on the mat"

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


# --------------------------------------------------------------------------
# 1 · chunking is a decision, not a utility function
# --------------------------------------------------------------------------

def chunk_fixed(text: str, size: int = 500, overlap: int = 100) -> list[dict]:
    chunks, step = [], size - overlap
    for start in range(0, len(text), step):
        piece = text[start:start + size]
        if piece.strip():
            chunks.append({"start": start, "end": start + len(piece),
                           "text": piece})
    return chunks


def chunk_sentences(text: str, max_chars: int = 500) -> list[dict]:
    chunks, buf, start = [], [], 0
    pos = 0
    for sentence in SENTENCE_END.split(text):
        if not sentence:
            continue
        if buf and sum(len(s) + 1 for s in buf) + len(sentence) > max_chars:
            body = " ".join(buf)
            chunks.append({"start": start, "end": start + len(body), "text": body})
            start = pos
            buf = []
        if not buf:
            start = pos
        buf.append(sentence)
        pos += len(sentence) + 1
    if buf:
        body = " ".join(buf)
        chunks.append({"start": start, "end": start + len(body), "text": body})
    return chunks


def straddling_chunks(text: str, chunks: list[dict]) -> list[dict]:
    out = []
    for c in chunks:
        i = c["start"]
        if i == 0 or i >= len(text):
            continue
        if not text[i - 1].isspace() and not text[i].isspace():
            left = text[:i].split()[-1] if text[:i].split() else ""
            right = text[i:].split()[0] if text[i:].split() else ""
            out.append({"start": i, "broken_word": left + right,
                        "left": left, "right": right})
    return out


# --------------------------------------------------------------------------
# 3 · cosine similarity, by hand
# --------------------------------------------------------------------------

def cosine(a, b) -> float:
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) * float(x) for x in a))
    nb = math.sqrt(sum(float(y) * float(y) for y in b))
    return dot / (na * nb)


# --------------------------------------------------------------------------

def main() -> None:
    ap = scale_parser(__doc__, default="tiny")
    args = ap.parse_args()
    n = resolve_n(args)

    import numpy as np
    from sentence_transformers import SentenceTransformer

    m = {}

    # ---- chunking -------------------------------------------------------
    text = "\n".join(t for _, t in iter_passages(200))
    rule("1 · two ways to cut the same text")
    fixed = chunk_fixed(text)
    sents = chunk_sentences(text)
    broken = straddling_chunks(text, fixed)
    broken_sent = straddling_chunks(text, sents)

    m["chunking"] = {
        "source_chars": len(text),
        "size": 500, "overlap": 100,
        "fixed_chunks": len(fixed),
        "sentence_chunks": len(sents),
        "fixed_broken_words": len(broken),
        "sentence_broken_words": len(broken_sent),
        "fixed_broken_ratio": len(broken) / len(fixed),
        "examples": broken[:6],
        "mean_fixed_chars": sum(len(c["text"]) for c in fixed) / len(fixed),
        "mean_sentence_chars": sum(len(c["text"]) for c in sents) / len(sents),
    }
    print(f"  {len(text):,} characters of passages")
    print(f"  fixed 500/100:      {len(fixed):,} chunks, "
          f"{len(broken):,} boundaries inside a word "
          f"({len(broken) / len(fixed):.0%})")
    print(f"  sentence boundaries:{len(sents):>6,} chunks, "
          f"{len(broken_sent):,} boundaries inside a word")
    for b in broken[:5]:
        print(f"    at {b['start']:>6}: {b['left']!r} + {b['right']!r} "
              f"-> {b['broken_word']!r}")

    # ---- a table, cut in half -------------------------------------------
    rule("2 · the same cut, applied to a table")
    tables_pdf = PDFS / "gen-tables.pdf"
    if tables_pdf.exists():
        import fitz
        with fitz.open(tables_pdf) as doc:
            table_text = "\n".join(p.get_text() for p in doc)
        tchunks = chunk_fixed(table_text, size=500, overlap=100)
        # Find a chunk boundary that lands inside a row of numbers.
        victim = None
        for c in tchunks[1:]:
            head = c["text"][:120]
            tail = table_text[max(0, c["start"] - 120):c["start"]]
            if any(ch.isdigit() for ch in head[:40]) and \
               any(ch.isdigit() for ch in tail[-40:]):
                victim = {"start": c["start"],
                          "before": " ".join(tail.split())[-110:],
                          "after": " ".join(head.split())[:110]}
                break
        m["table_cut"] = victim
        m["table_chunks"] = len(tchunks)
        if victim:
            print(f"  chunk boundary at character {victim['start']}:")
            print(f"    …{victim['before']}")
            print(f"    ---- CUT ----")
            print(f"    {victim['after']}…")

    # ---- tokenization: text becomes integers -----------------------------
    rule("3 · text becomes integers, by a learned agreement")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    tok = model.tokenizer
    ids = tok(CAT)["input_ids"]
    pieces = tok.convert_ids_to_tokens(ids)
    m["tokens"] = {
        "text": CAT,
        "ids": ids,
        "pieces": pieces,
        "n_tokens": len(ids),
        "vocab_size": tok.vocab_size,
    }
    print(f"  {CAT!r}")
    print(f"  -> {len(ids)} tokens from a vocabulary of {tok.vocab_size:,}")
    for p, i in zip(pieces, ids):
        print(f"     {p:<12} {i}")

    odd = "unbelievability"
    odd_ids = tok(odd)["input_ids"]
    m["tokens_rare"] = {
        "text": odd,
        "pieces": tok.convert_ids_to_tokens(odd_ids),
        "n_tokens": len(odd_ids),
    }
    print(f"  {odd!r} -> {tok.convert_ids_to_tokens(odd_ids)}")

    # ---- embedding ------------------------------------------------------
    rule("4 · similarity without shared words")
    sentences = [CAT, FELINE, UNRELATED, CONTRADICTION]
    t0 = time.perf_counter()
    vecs = model.encode(sentences, batch_size=32)
    encode_seconds = time.perf_counter() - t0

    shared = sorted(set(CAT.split()) & set(FELINE.split()))
    m["embedding"] = {
        "model": "all-MiniLM-L6-v2",
        "dims": int(vecs.shape[1]),
        "dtype": str(vecs.dtype),
        "bytes_per_vector": int(vecs[0].nbytes),
        "shared_words_cat_feline": shared,
        "sentences": sentences,
        "first_eight_floats": [float(x) for x in vecs[0][:8]],
        "encode_seconds_4": encode_seconds,
    }
    pairs = {
        "cat_feline": cosine(vecs[0], vecs[1]),
        "cat_unrelated": cosine(vecs[0], vecs[2]),
        "feline_unrelated": cosine(vecs[1], vecs[2]),
        "cat_contradiction": cosine(vecs[0], vecs[3]),
    }
    m["similarity"] = pairs
    m["similarity_numpy_check"] = float(
        np.dot(vecs[0], vecs[1])
        / (np.linalg.norm(vecs[0]) * np.linalg.norm(vecs[1])))

    print(f"  each sentence became {vecs.shape[1]} numbers "
          f"({human_bytes(vecs[0].nbytes)} each, {vecs.dtype})")
    print(f"  words shared by the first two sentences: {shared}")
    for k, v in pairs.items():
        print(f"    {k:<20} {v:+.4f}")

    # ---- throughput, so the reader can budget ---------------------------
    rule(f"5 · embedding {n:,} passages")
    passages = [t for _, t in iter_passages(n)]
    t0 = time.perf_counter()
    all_vecs = model.encode(passages, batch_size=256, show_progress_bar=False)
    seconds = time.perf_counter() - t0
    m["throughput"] = {
        "n_passages": len(passages),
        "seconds": seconds,
        "per_second": len(passages) / seconds,
        "total_bytes": int(all_vecs.nbytes),
        "bytes_per_million": int(all_vecs.nbytes / len(passages) * 1_000_000),
        "device": str(model.device),
    }
    print(f"  {len(passages):,} passages in {human_time(seconds)} "
          f"({len(passages) / seconds:,.0f}/s on {model.device})")
    print(f"  {human_bytes(all_vecs.nbytes)} of vectors — "
          f"{human_bytes(all_vecs.nbytes / len(passages) * 1_000_000)} per million")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
