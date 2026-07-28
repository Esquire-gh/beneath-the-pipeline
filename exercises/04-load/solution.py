#!/usr/bin/env python3
"""Module 4 — worked solution, and the source of the module page's numbers.

    python exercises/04-load/solution.py
    python exercises/04-load/solution.py --cold     # macOS: bypass the page cache

Read this after you have written your own.
"""
import argparse
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import human_bytes, human_time, rule, write_measurements  # noqa: E402

SLUG = "04-load"
CORPUS = REPO / "data" / "corpus_small"

F_NOCACHE = 48          # macOS fcntl: do not keep this data in the page cache


class Crossings:
    def __init__(self, nocache: bool = False):
        self.opens = self.reads = self.closes = 0
        self.nocache = nocache

    def open(self, path):
        self.opens += 1
        fd = os.open(path, os.O_RDONLY)
        if self.nocache and sys.platform == "darwin":
            import fcntl
            fcntl.fcntl(fd, F_NOCACHE, 1)
        return fd

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


def read_file_by_file(paths, c: Crossings, chunk: int = 1 << 16) -> int:
    total = 0
    for path in paths:
        fd = c.open(path)
        while True:
            data = c.read(fd, chunk)
            if not data:
                break
            total += len(data)
        c.close(fd)
    return total


def read_small_buffer(path, c: Crossings, chunk: int = 4096) -> int:
    total = 0
    fd = c.open(path)
    while True:
        data = c.read(fd, chunk)
        if not data:
            break
        total += len(data)
    c.close(fd)
    return total


def read_large_buffer(path, c: Crossings, chunk: int = 1 << 22) -> int:
    total = 0
    fd = c.open(path)
    while True:
        data = c.read(fd, chunk)
        if not data:
            break
        total += len(data)
    c.close(fd)
    return total


def read_files_large_buffer(paths, c: Crossings) -> int:
    """The same 10,000 files, with the big buffer. Isolates what the buffer
    can and cannot fix."""
    return read_file_by_file(paths, c, chunk=1 << 22)


def time_it(fn, runs=3):
    best, result = None, None
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        result = fn()
        dt = time.perf_counter() - t0
        times.append(dt)
        best = dt if best is None else min(best, dt)
    return best, times, result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cold", action="store_true",
                    help="ask the OS not to cache these reads (macOS only)")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    files = sorted((CORPUS / "files").glob("*.txt"))
    single = CORPUS / "all.txt"
    if not files or not single.exists():
        sys.exit("missing corpus — run: python data/fetch.py --only corpus")

    c = Crossings(nocache=args.cold)
    corpus_bytes = single.stat().st_size
    allocated = sum(f.stat().st_blocks * 512 for f in files)

    m = {
        "n_files": len(files),
        "corpus_bytes": corpus_bytes,
        "files_allocated_bytes": allocated,
        "mean_file_bytes": corpus_bytes / len(files),
        "cold": args.cold,
        "runs": args.runs,
        "strategies": {},
    }

    strategies = [
        ("file_by_file", "file by file, 64 KB buffer",
         lambda: read_file_by_file(files, c.reset())),
        ("files_large_buffer", "file by file, 4 MB buffer",
         lambda: read_files_large_buffer(files, c.reset())),
        ("small_buffer", "one file, 4 KB buffer",
         lambda: read_small_buffer(single, c.reset())),
        ("large_buffer", "one file, 4 MB buffer",
         lambda: read_large_buffer(single, c.reset())),
    ]

    print(f"{len(files):,} small files ({human_bytes(corpus_bytes)} of text, "
          f"{human_bytes(allocated)} reserved on disk),")
    print(f"and one file of {human_bytes(corpus_bytes)} holding the same bytes.")
    print(f"page cache: {'bypassed (F_NOCACHE)' if args.cold else 'warm'}\n")

    for key, label, fn in strategies:
        seconds, times, total = time_it(fn, args.runs)
        m["strategies"][key] = {
            "label": label,
            "seconds": seconds,
            "all_seconds": times,
            "bytes": total,
            "opens": c.opens,
            "reads": c.reads,
            "closes": c.closes,
            "crossings": c.total,
            "throughput_bytes_per_second": total / seconds if seconds else None,
        }
        rule(label)
        print(f"  bytes read   {human_bytes(total)}")
        print(f"  crossings    {c.total:,}  ({c.opens:,} open, "
              f"{c.reads:,} read, {c.closes:,} close)")
        print(f"  best of {args.runs}    {human_time(seconds)}")

    s = m["strategies"]
    best_key = min(s, key=lambda k: s[k]["seconds"])
    worst_key = max(s, key=lambda k: s[k]["seconds"])
    for key in s:
        s[key]["vs_best"] = s[key]["seconds"] / s[best_key]["seconds"]
        s[key]["microseconds_per_crossing"] = (
            s[key]["seconds"] / s[key]["crossings"] * 1e6)

    m["best"] = best_key
    m["worst"] = worst_key
    m["worst_vs_best"] = s[worst_key]["seconds"] / s[best_key]["seconds"]
    m["crossings_worst_vs_best"] = (s[worst_key]["crossings"]
                                    / s[best_key]["crossings"])
    # >1 means the bigger buffer helped; <1 means it made things worse.
    m["big_buffer_speedup_one_file"] = (s["small_buffer"]["seconds"]
                                        / s["large_buffer"]["seconds"])
    m["big_buffer_speedup_many_files"] = (s["file_by_file"]["seconds"]
                                          / s["files_large_buffer"]["seconds"])
    m["big_buffer_cost_many_files"] = (s["files_large_buffer"]["seconds"]
                                       / s["file_by_file"]["seconds"])

    rule("the ratios — these are what travel to other machines")
    print(f"  slowest / fastest, time:      {m['worst_vs_best']:.1f}x")
    print(f"  slowest / fastest, crossings: {m['crossings_worst_vs_best']:.0f}x")
    print(f"  bigger buffer on ONE file:    "
          f"{m['big_buffer_speedup_one_file']:.1f}x faster")
    print(f"  bigger buffer on 10k FILES:   "
          f"{m['big_buffer_cost_many_files']:.2f}x SLOWER"
          f"   <- the buffer cannot fix this, and costs to allocate")

    if not args.no_write:
        # A cold run is recorded alongside the warm one rather than replacing
        # it. The page shows both, because the comparison is the finding.
        path = write_measurements(SLUG, {"cold_run": m} if args.cold else m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
