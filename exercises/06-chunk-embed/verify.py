#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/06-chunk-embed/verify.py
"""
import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

SAMPLE = ("Storage devices hand out blocks. A block is the smallest unit. "
          "Reading many small files costs more than reading one large file! "
          "Why? The overhead is per request, not per byte. "
          "Index construction moves work from query time to build time.")


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
        got = yours.chunk_fixed(SAMPLE, size=60, overlap=10)
        want = ref.chunk_fixed(SAMPLE, size=60, overlap=10)
        check("chunk_fixed returns a list of dicts",
              isinstance(got, list) and got and isinstance(got[0], dict),
              f"got {type(got).__name__}")
        if got and isinstance(got[0], dict):
            check("chunk_fixed reports start, end and text",
                  {"start", "end", "text"} <= set(got[0]),
                  f"keys: {sorted(got[0])}")
            check("chunk_fixed produced the same number of chunks",
                  len(got) == len(want), f"{len(got)}, expected {len(want)}")
            check("chunk_fixed steps by size - overlap",
                  len(got) > 1 and got[1]["start"] - got[0]["start"] == 50,
                  f"first step is "
                  f"{got[1]['start'] - got[0]['start'] if len(got) > 1 else '?'}, "
                  f"expected 50")
            check("chunk_fixed's text matches its offsets",
                  all(c["text"] == SAMPLE[c["start"]:c["end"]] for c in got),
                  "a chunk's text does not match SAMPLE[start:end]")
    except Exception as e:
        check("chunk_fixed runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 2 ----------------------------------------------------------
    try:
        got = yours.chunk_sentences(SAMPLE, max_chars=120)
        check("chunk_sentences returns a list of dicts",
              isinstance(got, list) and got and isinstance(got[0], dict),
              f"got {type(got).__name__}")
        if got and isinstance(got[0], dict):
            joined = " ".join(c["text"] for c in got)
            check("chunk_sentences keeps every word",
                  sorted(joined.split()) == sorted(SAMPLE.split()),
                  "words were lost or duplicated")
            check("chunk_sentences never ends a chunk mid-sentence",
                  all(c["text"].rstrip()[-1] in ".!?" for c in got),
                  "a chunk ends somewhere that is not . ! or ?")
            check("chunk_sentences respects max_chars",
                  all(len(c["text"]) <= 200 for c in got),
                  f"longest chunk is {max(len(c['text']) for c in got)}")
    except Exception as e:
        check("chunk_sentences runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 3 ----------------------------------------------------------
    try:
        cases = [
            ([1.0, 0.0], [1.0, 0.0], 1.0),
            ([1.0, 0.0], [0.0, 1.0], 0.0),
            ([1.0, 0.0], [-1.0, 0.0], -1.0),
            ([3.0, 4.0], [6.0, 8.0], 1.0),
        ]
        for a, b, want in cases:
            got = yours.cosine(a, b)
            check(f"cosine({a}, {b}) == {want}",
                  got is not None and abs(float(got) - want) < 1e-9,
                  f"got {got!r}")
        import numpy as np
        rng = np.random.default_rng(7)
        a, b = rng.normal(size=384), rng.normal(size=384)
        want = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        got = yours.cosine(a, b)
        check("cosine agrees with numpy on 384 dimensions",
              got is not None and abs(float(got) - want) < 1e-6,
              f"yours {got!r}, numpy {want!r}")
    except Exception as e:
        check("cosine runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 4 ----------------------------------------------------------
    try:
        chunks = ref.chunk_fixed(SAMPLE, size=60, overlap=10)
        got = yours.straddling_chunks(SAMPLE, chunks)
        want = ref.straddling_chunks(SAMPLE, chunks)
        check("straddling_chunks returns a list", isinstance(got, list),
              f"got {type(got).__name__}")
        if isinstance(got, list):
            check("straddling_chunks found the same boundaries",
                  [c["start"] for c in got] == [c["start"] for c in want],
                  f"yours {[c['start'] for c in got]}, "
                  f"expected {[c['start'] for c in want]}")
            check("straddling_chunks reassembles the broken word",
                  all(c.get("broken_word") for c in got)
                  and [c["broken_word"] for c in got]
                      == [c["broken_word"] for c in want],
                  f"yours {[c.get('broken_word') for c in got]}, "
                  f"expected {[c['broken_word'] for c in want]}")
    except Exception as e:
        check("straddling_chunks runs", False, f"{type(e).__name__}: {e}")

    rule("module 6 — your chunking and similarity against the reference")
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
