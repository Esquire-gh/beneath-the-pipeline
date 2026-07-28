#!/usr/bin/env python3
"""Module 4 — Load: from disk to memory.  YOUR WORK GOES HERE.

Three TODOs. You will read the same bytes three ways and count how many times
each way crosses into the operating system.

    python exercises/04-load/starter.py       # run yours
    python exercises/04-load/verify.py        # check it

Needs data/corpus_small — run `python data/fetch.py --only corpus` first.
Standard library only.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import human_bytes, human_time, rule   # noqa: E402

CORPUS = REPO / "data" / "corpus_small"


# ==========================================================================
# The counter. Read this first — it is how the whole module is measured.
# ==========================================================================
#
# Your program cannot touch the disk. It asks the operating system to, and
# every ask is a syscall: a function call with a border crossing inside it.
# `os.open`, `os.read` and `os.close` are those asks, almost unwrapped.
#
# Use THIS object's methods instead of the os module directly, so the crossings
# get counted. The methods do nothing else — look at the class if you doubt it.

class Crossings:
    """Wraps the three syscalls this module cares about, and counts them."""

    def __init__(self):
        self.opens = self.reads = self.closes = 0

    def open(self, path):
        self.opens += 1
        return os.open(path, os.O_RDONLY)

    def read(self, fd, n):
        self.reads += 1
        return os.read(fd, n)

    def close(self, fd):
        self.closes += 1
        return os.close(fd)

    @property
    def total(self):
        return self.opens + self.reads + self.closes

    def reset(self):
        self.opens = self.reads = self.closes = 0
        return self


# ==========================================================================
# TODO 1 — read the corpus one file at a time
# ==========================================================================
#
# `paths` is a list of 10,000 small files. Open each, read all of it, close it.
# Return the total number of bytes read.
#
# os.read(fd, n) returns AT MOST n bytes, and returns b"" at end of file — so
# reading a whole file means looping until you get b"".
#
# Use c.open / c.read / c.close, never os.* directly.

def read_file_by_file(paths, c: Crossings, chunk: int = 1 << 16) -> int:
    total = 0
    for path in paths:
        # TODO: open, read to the end, close. Add to total.
        ...
    return total


# ==========================================================================
# TODO 2 — read one large file in small pieces
# ==========================================================================
#
# Same bytes, one file, but asked for in small mouthfuls. This is what reading
# "line by line" costs underneath: a small buffer refilled over and over.
#
# Return the total bytes read.

def read_small_buffer(path, c: Crossings, chunk: int = 4096) -> int:
    total = 0
    # TODO: open once, read `chunk` bytes at a time until empty, close
    ...
    return total


# ==========================================================================
# TODO 3 — read the same file in as few asks as you can
# ==========================================================================
#
# Same bytes, same one file, a large buffer. Nothing else changes.
#
# Return the total bytes read.

def read_large_buffer(path, c: Crossings, chunk: int = 1 << 22) -> int:
    total = 0
    # TODO: open once, read `chunk` bytes at a time until empty, close
    ...
    return total


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def time_it(fn, runs=3):
    """Best of N. The fastest run is the one least polluted by whatever else
    your machine was doing; means drift, best-of reproduces."""
    import time
    best, result = None, None
    for _ in range(runs):
        t0 = time.perf_counter()
        result = fn()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    return best, result


def main() -> None:
    files = sorted((CORPUS / "files").glob("*.txt"))
    single = CORPUS / "all.txt"
    if not files or not single.exists():
        sys.exit("missing corpus — run: python data/fetch.py --only corpus")

    c = Crossings()
    print(f"{len(files):,} small files, and one file of "
          f"{human_bytes(single.stat().st_size)}, holding the same bytes\n")

    for label, fn in (
        ("file by file",           lambda: read_file_by_file(files, c.reset())),
        ("one file, 4 KB buffer",  lambda: read_small_buffer(single, c.reset())),
        ("one file, 4 MB buffer",  lambda: read_large_buffer(single, c.reset())),
    ):
        seconds, total = time_it(fn)
        rule(label)
        print(f"  bytes read   {human_bytes(total) if total else '(nothing — TODO?)'}")
        print(f"  crossings    {c.total:,}  "
              f"({c.opens:,} open, {c.reads:,} read, {c.closes:,} close)")
        print(f"  best of 3    {human_time(seconds)}")


if __name__ == "__main__":
    main()
