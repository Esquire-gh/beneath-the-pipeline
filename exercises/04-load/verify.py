#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/04-load/verify.py

Crossing counts are checked as well as byte totals, because a strategy that
returns the right bytes the wrong way is the thing this module is about.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

CORPUS = REPO / "data" / "corpus_small"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    files = sorted((CORPUS / "files").glob("*.txt"))
    single = CORPUS / "all.txt"
    if not files or not single.exists():
        print("missing corpus — run: python data/fetch.py --only corpus")
        return 1

    yours, ref = load("starter"), load("solution")
    sample = files[:200]          # 200 files is enough to check the shape
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    def run(mod, fn_name, *args, **kw):
        c = mod.Crossings()
        total = getattr(mod, fn_name)(*args, c, **kw)
        return total, c

    expected_bytes = sum(f.stat().st_size for f in sample)

    try:
        got, gc = run(yours, "read_file_by_file", sample)
        want, wc = run(ref, "read_file_by_file", sample)
        check("read_file_by_file returns the total bytes",
              got == want == expected_bytes,
              f"yours {got}, expected {expected_bytes}")
        check("read_file_by_file opens each file exactly once",
              gc.opens == len(sample),
              f"{gc.opens} opens for {len(sample)} files")
        check("read_file_by_file closes what it opens",
              gc.opens == gc.closes,
              f"{gc.opens} opens, {gc.closes} closes")
        check("read_file_by_file's crossings match the reference",
              gc.total == wc.total,
              f"yours {gc.total}, reference {wc.total} — a read loop that "
              f"stops before the empty read will differ here")
    except Exception as e:
        check("read_file_by_file runs", False, f"{type(e).__name__}: {e}")

    try:
        got, gc = run(yours, "read_small_buffer", single)
        want, wc = run(ref, "read_small_buffer", single)
        check("read_small_buffer returns the total bytes", got == want,
              f"yours {got}, expected {want}")
        check("read_small_buffer opens the file once", gc.opens == 1,
              f"{gc.opens} opens")
        check("read_small_buffer used the small buffer",
              gc.reads == wc.reads,
              f"{gc.reads} reads, reference {wc.reads} — check the chunk size "
              f"is being passed to os.read")
    except Exception as e:
        check("read_small_buffer runs", False, f"{type(e).__name__}: {e}")

    try:
        got, gc = run(yours, "read_large_buffer", single)
        want, wc = run(ref, "read_large_buffer", single)
        check("read_large_buffer returns the total bytes", got == want,
              f"yours {got}, expected {want}")
        check("read_large_buffer used far fewer crossings",
              gc.total == wc.total,
              f"yours {gc.total}, reference {wc.total}")
    except Exception as e:
        check("read_large_buffer runs", False, f"{type(e).__name__}: {e}")

    rule("module 4 — your reads against the reference")
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
