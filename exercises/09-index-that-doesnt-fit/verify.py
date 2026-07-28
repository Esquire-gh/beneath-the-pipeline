#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/09-index-that-doesnt-fit/verify.py
"""
import importlib.util
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

DOCS = [
    "the block device hands back bytes",
    "a storage engine batches writes",
    "block block and more block",
    "reading many small files costs more",
    "the index moves work to build time",
] * 6


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

    # ---- gaps ------------------------------------------------------------
    try:
        cases = [
            ([3, 17, 18, 92], [3, 14, 1, 74]),
            ([0, 1, 2], [0, 1, 1]),
            ([5], [5]),
            ([], []),
        ]
        for postings, want in cases:
            got = yours.to_gaps(postings)
            check(f"to_gaps({postings}) == {want}", list(got or []) == want,
                  f"got {got!r}")
        check("gaps round trip",
              yours.from_gaps(yours.to_gaps([3, 17, 18, 92])) == [3, 17, 18, 92],
              "to_gaps then from_gaps did not return the original ids")
    except Exception as e:
        check("to_gaps runs", False, f"{type(e).__name__}: {e}")

    # ---- varbyte ---------------------------------------------------------
    try:
        check("varbyte: a value under 128 takes one byte",
              len(yours.varbyte_encode([3]) or b"") == 1,
              f"got {len(yours.varbyte_encode([3]) or b'')} bytes for the value 3")
        check("varbyte: 200 takes two bytes",
              len(yours.varbyte_encode([200]) or b"") == 2,
              f"got {len(yours.varbyte_encode([200]) or b'')} bytes")
        check("varbyte matches the reference encoding",
              yours.varbyte_encode([3, 14, 1, 74, 323])
              == ref.varbyte_encode([3, 14, 1, 74, 323]),
              f"yours {yours.varbyte_encode([3, 14, 1, 74, 323])!r}, "
              f"reference {ref.varbyte_encode([3, 14, 1, 74, 323])!r}")
        big = [1, 127, 128, 129, 16383, 16384, 1_000_000]
        check("varbyte round trips across byte boundaries",
              yours.varbyte_decode(yours.varbyte_encode(big)) == big,
              f"got {yours.varbyte_decode(yours.varbyte_encode(big))}")
    except Exception as e:
        check("varbyte_encode runs", False, f"{type(e).__name__}: {e}")

    # ---- SPIMI -----------------------------------------------------------
    scratch = HERE / "_verify"
    if scratch.exists():
        shutil.rmtree(scratch)
    try:
        paths = yours.build_blocks(iter(DOCS), scratch / "yours", block_size=10)
        want_paths = ref.build_blocks(iter(DOCS), scratch / "ref", block_size=10)
        check("build_blocks returns a list of paths",
              isinstance(paths, list) and paths and all(Path(p).exists() for p in paths),
              f"got {paths!r}")
        if paths:
            check("build_blocks wrote the expected number of blocks",
                  len(paths) == len(want_paths),
                  f"{len(paths)} blocks, expected {len(want_paths)} "
                  f"for {len(DOCS)} documents at block_size=10")
            first = Path(paths[0]).read_text().splitlines()
            terms = [line.split("\t")[0] for line in first]
            check("each block file is sorted by term", terms == sorted(terms),
                  "the merge depends on this — sort before writing")
            check("the final partial block was not lost",
                  sum(len(Path(p).read_text().splitlines()) for p in paths)
                  == sum(len(Path(p).read_text().splitlines()) for p in want_paths),
                  "a partial last block is easy to drop; check after the loop")
    except Exception as e:
        check("build_blocks runs", False, f"{type(e).__name__}: {e}")

    try:
        out = scratch / "yours-merged.txt"
        terms = yours.merge_blocks(want_paths, out)
        want_terms = ref.merge_blocks(want_paths, scratch / "ref-merged.txt")
        check("merge_blocks returns the number of distinct terms",
              terms == want_terms, f"yours {terms}, expected {want_terms}")
        got_lines = out.read_text().splitlines()
        want_lines = (scratch / "ref-merged.txt").read_text().splitlines()
        check("the merged file matches the reference", got_lines == want_lines,
              f"{sum(1 for a, b in zip(got_lines, want_lines) if a != b)} "
              f"lines differ")
        merged_terms = [line.split("\t")[0] for line in got_lines]
        check("the merged file is sorted and has no repeated terms",
              merged_terms == sorted(set(merged_terms)),
              "a term appearing in several blocks must produce ONE merged line")
    except Exception as e:
        check("merge_blocks runs", False, f"{type(e).__name__}: {e}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    rule("module 9 — your streaming index against the reference")
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
