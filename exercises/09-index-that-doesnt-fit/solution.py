#!/usr/bin/env python3
"""Module 9 — worked solution, and the source of the module page's numbers.

    python exercises/09-index-that-doesnt-fit/solution.py --scale part2
    python exercises/09-index-that-doesnt-fit/solution.py --scale big

The memory curve is the point. Rather than crashing a process — which depends
entirely on how much RAM you happen to have — this measures peak memory at a
series of corpus sizes for both strategies and lets you read where the
in-memory line leaves your machine.
"""
import heapq
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (eval_corpus, human_bytes, human_time, peak_rss_bytes,   # noqa: E402
                    resolve_n, rule, scale_parser, write_measurements)

SLUG = "09-index-that-doesnt-fit"
TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# --------------------------------------------------------------------------
# 1 & 2 · making the numbers smaller
# --------------------------------------------------------------------------

def to_gaps(postings: list[int]) -> list[int]:
    out, previous = [], 0
    for pid in postings:
        out.append(pid - previous)
        previous = pid
    return out


def from_gaps(gaps: list[int]) -> list[int]:
    out, running = [], 0
    for gap in gaps:
        running += gap
        out.append(running)
    return out


def varbyte_encode(numbers: list[int]) -> bytes:
    out = bytearray()
    for number in numbers:
        while True:
            seven = number & 0x7F
            number >>= 7
            if number:
                out.append(seven)          # more to come
            else:
                out.append(seven | 0x80)   # last byte of this number
                break
    return bytes(out)


def varbyte_decode(data: bytes) -> list[int]:
    out, value, shift = [], 0, 0
    for byte in data:
        value |= (byte & 0x7F) << shift
        if byte & 0x80:
            out.append(value)
            value, shift = 0, 0
        else:
            shift += 7
    return out


# --------------------------------------------------------------------------
# 3 & 4 · SPIMI
# --------------------------------------------------------------------------

def write_block(block: dict[str, list[int]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for term in sorted(block):
            f.write(f"{term}\t{','.join(str(d) for d in block[term])}\n")


def build_blocks(docs, out_dir: Path, block_size: int = 10_000) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    block: dict[str, list[int]] = {}
    doc_id = 0
    for text in docs:
        for token in set(tokenize(text)):
            block.setdefault(token, []).append(doc_id)
        doc_id += 1
        if doc_id % block_size == 0:
            path = out_dir / f"block-{len(paths):04d}.txt"
            write_block(block, path)
            paths.append(path)
            block = {}                     # the memory goes back here
    if block:
        path = out_dir / f"block-{len(paths):04d}.txt"
        write_block(block, path)
        paths.append(path)
    return paths


def iter_block_lines(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            term, _, ids = line.rstrip("\n").partition("\t")
            yield term, [int(x) for x in ids.split(",") if x]


def merge_blocks(paths: list[Path], out_path: Path) -> int:
    streams = [iter_block_lines(p) for p in paths]
    terms = 0
    with out_path.open("w", encoding="utf-8") as out:
        current_term, current_ids = None, []
        for term, ids in heapq.merge(*streams, key=lambda pair: pair[0]):
            if term != current_term:
                if current_term is not None:
                    out.write(f"{current_term}\t"
                              f"{','.join(str(i) for i in current_ids)}\n")
                    terms += 1
                current_term, current_ids = term, list(ids)
            else:
                current_ids.extend(ids)
        if current_term is not None:
            out.write(f"{current_term}\t"
                      f"{','.join(str(i) for i in current_ids)}\n")
            terms += 1
    return terms


def build_in_memory(docs) -> dict[str, list[int]]:
    """Module 7's index, unchanged. The thing that does not scale."""
    index: dict[str, list[int]] = {}
    for doc_id, text in enumerate(docs):
        for token in set(tokenize(text)):
            index.setdefault(token, []).append(doc_id)
    return index


# --------------------------------------------------------------------------
# measuring peak memory honestly, in a child process
# --------------------------------------------------------------------------

CHILD = r'''
import json, re, sys, resource
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from common import iter_eval_corpus, peak_rss_bytes
import importlib.util
spec = importlib.util.spec_from_file_location("sol", sys.argv[2])
sol = importlib.util.module_from_spec(spec); spec.loader.exec_module(sol)

mode, n, block_size = sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
baseline = peak_rss_bytes()
import time
t0 = time.perf_counter()
extra = {}
if mode == "memory":
    index = sol.build_in_memory(t for _, t in iter_eval_corpus(n))
    size = len(index)
else:
    out = Path(sys.argv[6])
    paths = sol.build_blocks((t for _, t in iter_eval_corpus(n)),
                             out, block_size=block_size)
    # Peak so far is the block-building phase alone: bounded by block_size.
    extra["build_peak_rss"] = peak_rss_bytes()
    extra["blocks"] = len(paths)
    size = sol.merge_blocks(paths, out / "merged.txt")
seconds = time.perf_counter() - t0
print(json.dumps({"peak_rss": peak_rss_bytes(), "baseline_rss": baseline,
                  "terms": size, "seconds": seconds, **extra}))
'''


def measure_build(mode: str, n: int, block_size: int, scratch: Path) -> dict:
    """Run one build in a fresh process and report its peak memory.

    A child process is the only honest way to do this: peak memory is a
    high-water mark that never comes back down inside one process, so two
    builds in the same interpreter would report the same number.
    """
    child_py = scratch / "_child.py"
    child_py.parent.mkdir(parents=True, exist_ok=True)
    child_py.write_text(CHILD)
    out_dir = scratch / f"{mode}-{n}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [sys.executable, str(child_py), str(REPO / "exercises"),
         str(Path(__file__).resolve()), mode, str(n), str(block_size),
         str(out_dir)],
        capture_output=True, text=True)
    if result.returncode != 0:
        return {"failed": True, "stderr": result.stderr[-400:]}
    import json
    data = json.loads(result.stdout.strip().splitlines()[-1])
    if mode == "spimi":
        data["on_disk_bytes"] = sum(p.stat().st_size for p in out_dir.glob("*.txt"))
    shutil.rmtree(out_dir, ignore_errors=True)
    return data


# --------------------------------------------------------------------------

def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    ap.add_argument("--block-size", type=int, default=10_000)
    args = ap.parse_args()
    n = resolve_n(args)

    scratch = Path(__file__).parent / "_index"
    scratch.mkdir(exist_ok=True)
    m = {"block_size": args.block_size, "n_passages": n}

    # ---- compression ----------------------------------------------------
    rule("1 · gaps and variable-length bytes")
    corpus = eval_corpus(n)
    index = build_in_memory(t for _, t in corpus)

    raw_bytes = gap_bytes = vb_bytes = 0
    postings_total = 0
    for term, postings in index.items():
        postings_total += len(postings)
        raw_bytes += 4 * len(postings)
        gaps = to_gaps(postings)
        gap_bytes += 4 * len(gaps)
        vb_bytes += len(varbyte_encode(gaps))

    m["compression"] = {
        "postings": postings_total,
        "terms": len(index),
        "raw_int32_bytes": raw_bytes,
        "gaps_int32_bytes": gap_bytes,
        "gaps_varbyte_bytes": vb_bytes,
        "bytes_per_posting_raw": raw_bytes / postings_total,
        "bytes_per_posting_varbyte": vb_bytes / postings_total,
        "ratio": raw_bytes / vb_bytes,
    }
    print(f"  {postings_total:,} postings across {len(index):,} terms")
    print(f"  raw 32-bit ids        {human_bytes(raw_bytes)}  "
          f"({raw_bytes / postings_total:.2f} bytes/posting)")
    print(f"  gaps, still 32-bit    {human_bytes(gap_bytes)}  (no saving yet)")
    print(f"  gaps + varbyte        {human_bytes(vb_bytes)}  "
          f"({vb_bytes / postings_total:.2f} bytes/posting)")
    print(f"  {raw_bytes / vb_bytes:.2f}x smaller")

    # what compression charges you back
    sample_terms = sorted(index, key=lambda t: -len(index[t]))[:200]
    encoded = {t: varbyte_encode(to_gaps(index[t])) for t in sample_terms}

    t0 = time.perf_counter()
    for _ in range(20):
        for t in sample_terms:
            _ = list(index[t])
    plain_seconds = (time.perf_counter() - t0) / 20

    t0 = time.perf_counter()
    for _ in range(20):
        for t in sample_terms:
            _ = from_gaps(varbyte_decode(encoded[t]))
    decode_seconds = (time.perf_counter() - t0) / 20

    m["decode_cost"] = {
        "terms_sampled": len(sample_terms),
        "postings_sampled": sum(len(index[t]) for t in sample_terms),
        "plain_seconds": plain_seconds,
        "decode_seconds": decode_seconds,
        "slowdown": decode_seconds / plain_seconds,
    }
    print(f"  reading them back costs {decode_seconds / plain_seconds:.1f}x "
          f"more than reading a plain list — that is what compression charges")

    del index

    # ---- the memory curve -----------------------------------------------
    rule("2 · peak memory against corpus size")
    sizes = [s for s in (10_000, 25_000, 50_000, 100_000, 250_000, 500_000,
                         1_000_000) if s <= n]
    m["curve"] = {"sizes": sizes, "in_memory": [], "spimi": []}
    # Build every corpus cache first, so the timings measure indexing rather
    # than whichever run happened to pay for the corpus file.
    for size in sizes:
        eval_corpus(size, quiet=True)
    # Report the index's OWN memory: peak minus what the interpreter was
    # already holding before the build started. Otherwise ~25 MB of Python
    # sits in every row and flattens the comparison.
    print(f"  {'passages':>10}  {'in memory':>11}  {'SPIMI build':>12}  "
          f"{'SPIMI total':>12}  {'in-mem time':>12}  {'SPIMI time':>11}")
    for size in sizes:
        mem = measure_build("memory", size, args.block_size, scratch)
        spi = measure_build("spimi", size, args.block_size, scratch)
        m["curve"]["in_memory"].append(mem)
        m["curve"]["spimi"].append(spi)
        if mem.get("failed") or spi.get("failed"):
            print(f"  {size:>10,}  build failed: "
                  f"{mem.get('stderr') or spi.get('stderr')}")
            continue
        for r in (mem, spi):
            r["index_bytes"] = max(r["peak_rss"] - r["baseline_rss"], 0)
        spi["build_index_bytes"] = max(
            spi.get("build_peak_rss", spi["peak_rss"]) - spi["baseline_rss"], 0)
        print(f"  {size:>10,}  {human_bytes(mem['index_bytes']):>11}  "
              f"{human_bytes(spi['build_index_bytes']):>12}  "
              f"{human_bytes(spi['index_bytes']):>12}  "
              f"{human_time(mem['seconds']):>12}  "
              f"{human_time(spi['seconds']):>11}")

    ok_mem = [(s, r) for s, r in zip(sizes, m["curve"]["in_memory"])
              if not r.get("failed")]
    ok_spi = [(s, r) for s, r in zip(sizes, m["curve"]["spimi"])
              if not r.get("failed")]
    if len(ok_mem) >= 2:
        (s0, r0), (s1, r1) = ok_mem[0], ok_mem[-1]
        bytes_per_doc = (r1["index_bytes"] - r0["index_bytes"]) / (s1 - s0)
        m["in_memory_bytes_per_passage"] = bytes_per_doc
        m["in_memory_growth"] = r1["index_bytes"] / max(r0["index_bytes"], 1)
        from common import machine
        ram = machine()["ram_bytes"]
        m["ram_bytes"] = ram
        if bytes_per_doc > 0 and ram:
            m["passages_until_ram_full"] = (ram - r0["index_bytes"]) / bytes_per_doc
            print(f"\n  in-memory index grows by "
                  f"{human_bytes(bytes_per_doc)} per passage")
            print(f"  this machine has {human_bytes(ram)}, so the line reaches "
                  f"it at about "
                  f"{m['passages_until_ram_full'] / 1e6:.1f}M passages")
    if len(ok_spi) >= 2:
        peaks = [r["index_bytes"] for _, r in ok_spi]
        build_peaks = [r["build_index_bytes"] for _, r in ok_spi]
        mem_peaks = [r["index_bytes"] for _, r in ok_mem]
        span = ok_spi[-1][0] // ok_spi[0][0]
        m["corpus_span"] = span
        m["spimi_peak_spread"] = max(peaks) / min(peaks)
        m["spimi_build_spread"] = max(build_peaks) / min(build_peaks)
        m["in_memory_spread"] = max(mem_peaks) / min(mem_peaks)
        print(f"\n  across a {span}x range of corpus sizes:")
        print(f"    in-memory index peak grew "
              f"{m['in_memory_spread']:.2f}x")
        print(f"    SPIMI block-building peak grew "
              f"{m['spimi_build_spread']:.2f}x   <- bounded by block_size")
        print(f"    SPIMI including the merge grew "
              f"{m['spimi_peak_spread']:.2f}x   <- the merge holds one "
              f"complete posting list")

    shutil.rmtree(scratch, ignore_errors=True)
    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
