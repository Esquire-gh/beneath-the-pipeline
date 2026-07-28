#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/12-vector-search-at-scale/verify.py

Runs on a small synthetic set so it finishes in seconds.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    import numpy as np
    yours, ref = load("starter"), load("solution")
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    rng = np.random.default_rng(99)
    vectors = rng.normal(size=(4000, 64)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    queries = vectors[rng.choice(4000, size=20, replace=False)]

    # ---- TODO 1 ----------------------------------------------------------
    try:
        got = list(yours.brute_force_topk(vectors, queries[0], k=10))
        want = list(ref.brute_force_topk(vectors, queries[0], k=10))
        check("brute_force_topk returns k indices", len(got) == 10,
              f"got {len(got)}")
        check("brute_force_topk matches the reference",
              [int(x) for x in got] == [int(x) for x in want],
              f"yours {[int(x) for x in got]}, reference {[int(x) for x in want]}")
        scores = vectors @ queries[0]
        check("results are ordered best first",
              all(scores[int(got[i])] >= scores[int(got[i + 1])]
                  for i in range(len(got) - 1)),
              "scores are not decreasing — check the argsort direction")
        check("a vector is its own nearest neighbour",
              int(got[0]) == int(np.argmax(scores)),
              f"first result is {got[0]}, expected {int(np.argmax(scores))}")
    except Exception as e:
        check("brute_force_topk runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 3 ----------------------------------------------------------
    try:
        cases = [
            ([1, 2, 3], [1, 2, 3], 3, 1.0),
            ([1, 2, 3], [4, 5, 6], 3, 0.0),
            ([1, 2, 9], [1, 2, 3], 3, 2 / 3),
            ([3, 2, 1], [1, 2, 3], 3, 1.0),      # order must not matter
        ]
        for approx, truth, k, want in cases:
            got = yours.recall_at_k(approx, truth, k)
            check(f"recall_at_k({approx}, {truth}, k={k}) == {want:.4f}",
                  got is not None and abs(float(got) - want) < 1e-9,
                  f"got {got!r}")
    except Exception as e:
        check("recall_at_k runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 2 ----------------------------------------------------------
    try:
        index = yours.build_hnsw(vectors, M=16, ef_construction=100)
        check("build_hnsw returned an index",
              index is not None and hasattr(index, "knn_query"),
              f"got {type(index).__name__}")
        if index is not None and hasattr(index, "knn_query"):
            index.set_ef(200)
            recalls = []
            for q in queries:
                labels, _ = index.knn_query(q, k=10)
                truth = ref.brute_force_topk(vectors, q, k=10)
                recalls.append(
                    yours.recall_at_k([int(x) for x in labels[0]],
                                      [int(x) for x in truth], 10) or 0.0)
            mean = sum(recalls) / len(recalls)
            check("the graph finds most of the true neighbours at ef=200",
                  mean > 0.9,
                  f"mean recall {mean:.3f} — if this is near 0, the labels "
                  f"passed to add_items are probably not 0..n-1")
    except Exception as e:
        check("build_hnsw runs", False, f"{type(e).__name__}: {e}")

    rule("module 12 — your index against the reference")
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
