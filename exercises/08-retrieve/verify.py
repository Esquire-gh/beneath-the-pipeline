#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/08-retrieve/verify.py

The metric checks use hand-worked examples, so a failure tells you which term
of the formula is wrong rather than just that a number differs.
"""
import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

DOCS = [
    "the block device hands back bytes the block is the unit",
    "a storage engine batches writes to stay off the boundary",
    "block block block block block",
    "reading many small files costs more than one large file",
    "the the the the the the the the the the the the the the",
]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    yours, ref = load("starter"), load("solution")
    index_y = yours.Index(DOCS)
    index_r = ref.Index(DOCS)
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    # ---- scorers ---------------------------------------------------------
    for fn_name in ("score_term_counts", "score_tfidf", "score_bm25"):
        try:
            got = getattr(yours, fn_name)(index_y, "block device")
            want = getattr(ref, fn_name)(index_r, "block device")
            check(f"{fn_name} returns a dict", isinstance(got, dict),
                  f"got {type(got).__name__}")
            if isinstance(got, dict):
                check(f"{fn_name} scores the same documents",
                      set(got) == set(want),
                      f"yours {sorted(got)}, expected {sorted(want)}")
                close = all(abs(got.get(d, 0) - want[d]) < 1e-9 for d in want)
                check(f"{fn_name} scores match the reference", close,
                      f"yours {dict(sorted(got.items()))}, "
                      f"expected {dict(sorted(want.items()))}")
        except Exception as e:
            check(f"{fn_name} runs", False, f"{type(e).__name__}: {e}")

    try:
        counts = yours.score_term_counts(index_y, "block")
        check("raw term counts rank the five-'block' document first",
              counts and max(counts, key=counts.get) == 2,
              f"top document is {max(counts, key=counts.get) if counts else None}, "
              f"expected 2")
    except Exception as e:
        check("score_term_counts on 'block'", False, f"{type(e).__name__}: {e}")

    try:
        bm = yours.score_bm25(index_y, "the")
        check("BM25 does not reward the all-stopword document most",
              bm and max(bm, key=bm.get) != 4,
              "document 4 is nothing but 'the' repeated — BM25's idf should "
              "make that term nearly worthless")
    except Exception as e:
        check("score_bm25 on 'the'", False, f"{type(e).__name__}: {e}")

    # ---- precision@k -----------------------------------------------------
    try:
        cases = [
            ([1, 2, 3], {1, 2, 3}, 3, 1.0),
            ([1, 2, 3], {9}, 3, 0.0),
            ([1, 9, 9], {1}, 3, 1 / 3),
            ([1], {1}, 10, 0.1),          # 1 good result out of 10 requested
            ([], {1}, 10, 0.0),
        ]
        for ranked, rel, k, want in cases:
            got = yours.precision_at_k(ranked, rel, k)
            check(f"precision_at_k({ranked}, {sorted(rel)}, k={k}) == {want:.4f}",
                  got is not None and abs(float(got) - want) < 1e-9,
                  f"got {got!r} — when fewer than k results come back, still "
                  f"divide by k")
    except Exception as e:
        check("precision_at_k runs", False, f"{type(e).__name__}: {e}")

    # ---- ndcg@k ----------------------------------------------------------
    try:
        check("ndcg_at_k is 1.0 when the only relevant document is first",
              abs(float(yours.ndcg_at_k([7, 1, 2], {7}, 10)) - 1.0) < 1e-9,
              f"got {yours.ndcg_at_k([7, 1, 2], {7}, 10)!r}")

        want = (1 / math.log2(3)) / 1.0
        got = yours.ndcg_at_k([1, 7, 2], {7}, 10)
        check("ndcg_at_k discounts a hit at position 2 to 1/log2(3)",
              got is not None and abs(float(got) - want) < 1e-9,
              f"got {got!r}, expected {want:.6f}")

        check("ndcg_at_k is 0.0 when nothing relevant is retrieved",
              abs(float(yours.ndcg_at_k([1, 2, 3], {9}, 10))) < 1e-12,
              f"got {yours.ndcg_at_k([1, 2, 3], {9}, 10)!r}")

        check("ndcg_at_k is 0.0 when there is nothing relevant to find",
              abs(float(yours.ndcg_at_k([1, 2, 3], set(), 10))) < 1e-12,
              f"got {yours.ndcg_at_k([1, 2, 3], set(), 10)!r}")

        perfect = yours.ndcg_at_k([1, 2, 9, 9], {1, 2}, 10)
        check("ndcg_at_k is 1.0 when both relevant documents are first two",
              perfect is not None and abs(float(perfect) - 1.0) < 1e-9,
              f"got {perfect!r} — the ideal ranking has as many relevant "
              f"documents as exist, not one")

        check("ndcg_at_k respects k",
              abs(float(yours.ndcg_at_k([9] * 10 + [7], {7}, 10))) < 1e-12,
              "a hit at position 11 must not count for NDCG@10")
    except Exception as e:
        check("ndcg_at_k runs", False, f"{type(e).__name__}: {e}")

    rule("module 8 — your scorers and metrics against the reference")
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}")
        if detail and not ok:
            print(f"         {detail}")
        failed += 0 if ok else 1

    print()
    print(f"all {len(checks)} checks pass." if not failed else
          f"{failed} of {len(checks)} checks failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
