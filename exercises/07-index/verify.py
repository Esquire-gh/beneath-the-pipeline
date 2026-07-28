#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/07-index/verify.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

DOCS = [
    (0, "The block device hands back 4096 bytes."),
    (1, "A BLOCK is the smallest unit; blockchain is a different word."),
    (2, "Reading many small files costs more than one large file."),
    (3, "The index moves work from query time to build time."),
    (4, "Manhattan is an island. The Manhattan Project was not."),
]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    yours, ref = load("starter"), load("solution")
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    # ---- TODO 1 ----------------------------------------------------------
    try:
        got = yours.tokenize("The Block device, and 4096 BYTES.")
        want = ref.tokenize("The Block device, and 4096 BYTES.")
        check("tokenize lowercases and splits on non-alphanumerics",
              got == want, f"yours {got!r}, expected {want!r}")
        check("tokenize keeps duplicates in order",
              yours.tokenize("a a b") == ["a", "a", "b"],
              f"got {yours.tokenize('a a b')!r}")
    except Exception as e:
        check("tokenize runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 2 ----------------------------------------------------------
    try:
        for word, expected in (("block", [0, 1]), ("manhattan", [4]),
                               ("zyzzyva", [])):
            got = yours.scan(DOCS, word)
            check(f"scan finds {word!r} in {expected}", list(got) == expected,
                  f"yours {list(got)!r}")
        check("scan matches whole tokens, not substrings",
              1 in yours.scan(DOCS, "block")
              and yours.scan(DOCS, "blockchain") == [1],
              "searching for 'block' must not be the same as 'blockchain'")
    except Exception as e:
        check("scan runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 3 ----------------------------------------------------------
    try:
        got = yours.build_inverted_index(DOCS)
        want = ref.build_inverted_index(DOCS)
        check("build_inverted_index returns a dict", isinstance(got, dict),
              f"got {type(got).__name__}")
        if isinstance(got, dict):
            check("the vocabulary matches", set(got) == set(want),
                  f"{len(set(got) ^ set(want))} words differ")
            check("posting lists are sorted",
                  all(list(v) == sorted(v) for v in got.values()),
                  "at least one posting list is out of order")
            check("each document appears once per posting list",
                  all(len(v) == len(set(v)) for v in got.values()),
                  "a posting list contains a duplicate — index each document's "
                  "distinct tokens, not every occurrence")
            check("posting lists match the reference",
                  all(list(got[w]) == want[w] for w in want if w in got),
                  "a posting list differs from the reference")
    except Exception as e:
        check("build_inverted_index runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 4 ----------------------------------------------------------
    try:
        import numpy as np
        rng = np.random.default_rng(3)
        vecs = rng.normal(size=(500, 32)).astype("float32")
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        q = vecs[7]
        got = list(yours.brute_force_topk(vecs, q, k=5))
        want = list(ref.brute_force_topk(vecs, q, k=5))
        check("brute_force_topk returns k results", len(got) == 5,
              f"got {len(got)}")
        check("the nearest vector to itself is itself",
              got and int(got[0]) == 7, f"first result is {got[0] if got else None}")
        check("brute_force_topk matches the reference",
              [int(x) for x in got] == [int(x) for x in want],
              f"yours {got}, expected {want}")
        check("results are ordered best first",
              all((vecs @ q)[int(got[i])] >= (vecs @ q)[int(got[i + 1])]
                  for i in range(len(got) - 1)),
              "scores are not decreasing — check the argsort direction")
    except Exception as e:
        check("brute_force_topk runs", False, f"{type(e).__name__}: {e}")

    rule("module 7 — your index against the reference")
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
