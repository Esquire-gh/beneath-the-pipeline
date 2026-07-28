#!/usr/bin/env python3
"""Module 10 — worked solution, and the source of the module page's numbers.

    python exercises/10-ingestion-vs-query/solution.py --scale part2

Two halves. First: what a merge policy costs, swept across fan-out values, so
the trade between ingestion speed and query speed is a curve rather than an
opinion. Second: a versioned binary format, and the four ways an old reader
and new data can meet.
"""
import os
import re
import shutil
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import (human_bytes, human_time, iter_eval_corpus, resolve_n,   # noqa: E402
                    rule, scale_parser, write_measurements)

SLUG = "10-ingestion-vs-query"
TOKEN = re.compile(r"[a-z0-9]+")

MAGIC = b"BTP1"
VERSION = 1
PROBE_TERMS = ["block", "manhattan", "the", "photosynthesis", "engine"]


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# --------------------------------------------------------------------------
# segments
# --------------------------------------------------------------------------

class Segment:
    def __init__(self, docs: dict[int, str] | None = None):
        self.postings: dict[str, list[int]] = {}
        self.doc_ids: list[int] = []
        if docs:
            for doc_id, text in docs.items():
                self.doc_ids.append(doc_id)
                for token in set(tokenize(text)):
                    self.postings.setdefault(token, []).append(doc_id)
            for plist in self.postings.values():
                plist.sort()

    @classmethod
    def from_postings(cls, postings, doc_ids):
        seg = cls()
        seg.postings = postings
        seg.doc_ids = doc_ids
        return seg

    @property
    def n_docs(self) -> int:
        return len(self.doc_ids)

    @property
    def n_postings(self) -> int:
        return sum(len(p) for p in self.postings.values())

    def search(self, term: str) -> list[int]:
        return self.postings.get(term, [])


def search_all(segments: list[Segment], term: str) -> tuple[list[int], int]:
    found: set[int] = set()
    for seg in segments:
        found.update(seg.search(term))
    return sorted(found), len(segments)


def merge_segments(a: Segment, b: Segment) -> Segment:
    postings: dict[str, list[int]] = {}
    for source in (a.postings, b.postings):
        for term, plist in source.items():
            if term in postings:
                postings[term] = sorted(set(postings[term]) | set(plist))
            else:
                postings[term] = list(plist)
    return Segment.from_postings(postings, a.doc_ids + b.doc_ids)


def apply_merge_policy(segments: list[Segment],
                       fan: int = 4) -> tuple[list[Segment], int]:
    """Fold `fan` same-sized segments into one, repeatedly.

    Small segments get promoted a tier at a time, so most merges are cheap and
    the expensive ones are rare. This is the shape every log-structured store
    uses.
    """
    import math

    rewritten = 0
    changed = True
    while changed:
        changed = False
        tiers: dict[int, list[Segment]] = {}
        for seg in segments:
            tier = int(math.log(max(seg.n_docs, 1), fan))
            tiers.setdefault(tier, []).append(seg)
        for tier, members in sorted(tiers.items()):
            if len(members) < fan:
                continue
            group = members[:fan]
            merged = group[0]
            for other in group[1:]:
                merged = merge_segments(merged, other)
            rewritten += sum(s.n_docs for s in group)
            segments = [s for s in segments if s not in group] + [merged]
            changed = True
            break
    return segments, rewritten


# --------------------------------------------------------------------------
# a segment that lives on disk, which is where the fanout cost actually is
# --------------------------------------------------------------------------
#
# An in-memory dict of segments barely notices how many segments there are:
# the total number of postings is the same however you slice it, and one extra
# dict lookup per segment costs nothing. Measured that way, fanout looks free,
# and the conclusion would be wrong.
#
# Real segments are files. Every segment a query touches is a seek and a read
# — module 4's border crossing, once per segment per term. That is the cost a
# merge policy exists to control, so measure it where it lives.

class DiskSegment:
    """One segment, written in the module's own format, queried by seeking.

    The term dictionary (term -> where its postings are) stays in memory; the
    postings themselves are read from the file on demand. That split is what
    every production index does.
    """

    def __init__(self, path: Path):
        self.path = path
        data = path.read_bytes()
        self.terms: dict[str, tuple[int, int]] = {}
        _version, _flags, n_terms = struct.unpack_from("<HHI", data, 4)
        offset = 12
        for _ in range(n_terms):
            (term_len,) = struct.unpack_from("<H", data, offset)
            offset += 2
            term = data[offset:offset + term_len].decode("utf-8")
            offset += term_len
            (count,) = struct.unpack_from("<I", data, offset)
            offset += 4
            self.terms[term] = (offset, count)
            offset += 4 * count
        self.fd = os.open(path, os.O_RDONLY)
        self.n_docs_stored = 0

    def search(self, term: str, counter=None) -> list[int]:
        entry = self.terms.get(term)
        if entry is None:
            return []
        offset, count = entry
        if counter is not None:
            counter[0] += 1                       # one crossing into the OS
        raw = os.pread(self.fd, 4 * count, offset)
        return list(struct.unpack(f"<{count}I", raw))

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass


def search_all_disk(segments, term: str, counter=None) -> list[int]:
    found: set[int] = set()
    for seg in segments:
        found.update(seg.search(term, counter))
    return sorted(found)


def persist_segments(segments: list[Segment], out_dir: Path) -> list[DiskSegment]:
    out_dir.mkdir(parents=True, exist_ok=True)
    disk = []
    for i, seg in enumerate(segments):
        path = out_dir / f"segment-{i:04d}.btp"
        path.write_bytes(write_index(seg))
        ds = DiskSegment(path)
        ds.n_docs_stored = seg.n_docs
        disk.append(ds)
    return disk


def split_into(texts: list[str], parts: int) -> list[Segment]:
    """The SAME corpus, cut into `parts` segments. Only the slicing changes."""
    size = -(-len(texts) // parts)
    out = []
    for start in range(0, len(texts), size):
        out.append(Segment({i: texts[i]
                            for i in range(start, min(start + size, len(texts)))}))
    return out


# --------------------------------------------------------------------------
# a format of your own design
# --------------------------------------------------------------------------

def write_index(segment: Segment, version: int = VERSION,
                flags: int = 0) -> bytes:
    out = bytearray()
    out += MAGIC
    out += struct.pack("<HHI", version, flags, len(segment.postings))
    for term in sorted(segment.postings):
        postings = segment.postings[term]
        encoded = term.encode("utf-8")
        out += struct.pack("<H", len(encoded))
        out += encoded
        out += struct.pack("<I", len(postings))
        out += struct.pack(f"<{len(postings)}I", *postings)
    return bytes(out)


def read_index(data: bytes) -> tuple[dict, dict[str, list[int]]]:
    if data[:4] != MAGIC:
        raise ValueError(f"not a BTP index: starts with {data[:4]!r}")
    version, flags, n_terms = struct.unpack_from("<HHI", data, 4)
    if version > VERSION:
        raise ValueError(
            f"index was written by version {version}; this reader "
            f"understands up to {VERSION}. Refusing to guess.")
    header = {"version": version, "flags": flags, "terms": n_terms}
    postings, offset = {}, 12
    for _ in range(n_terms):
        (term_len,) = struct.unpack_from("<H", data, offset)
        offset += 2
        term = data[offset:offset + term_len].decode("utf-8")
        offset += term_len
        (count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        postings[term] = list(struct.unpack_from(f"<{count}I", data, offset))
        offset += 4 * count
    return header, postings


# ---- version 2 adds a field, and both readers have to behave -------------

VERSION_2 = 2
FLAG_HAS_DOC_LENGTHS = 1


def write_index_v2(segment: Segment, doc_lengths: dict[int, int]) -> bytes:
    """Version 2 appends document lengths after the postings.

    The flag says the extra section is present. A version-1 reader that
    ignores flags would read the postings correctly and stop — which is only
    safe because the new section was APPENDED rather than inserted.
    """
    body = write_index(segment, version=VERSION_2, flags=FLAG_HAS_DOC_LENGTHS)
    extra = bytearray(struct.pack("<I", len(doc_lengths)))
    for doc_id, length in sorted(doc_lengths.items()):
        extra += struct.pack("<II", doc_id, length)
    return bytes(body) + bytes(extra)


def read_index_v2(data: bytes):
    header, postings = read_index_permissive(data)
    lengths = {}
    if header["flags"] & FLAG_HAS_DOC_LENGTHS:
        offset = header["_end_of_postings"]
        (count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        for _ in range(count):
            doc_id, length = struct.unpack_from("<II", data, offset)
            lengths[doc_id] = length
            offset += 8
    return header, postings, lengths


def read_index_permissive(data: bytes):
    """A version-2 reader: accepts version 1 and 2, and reports where the
    postings section ended so a later section can be found."""
    if data[:4] != MAGIC:
        raise ValueError(f"not a BTP index: starts with {data[:4]!r}")
    version, flags, n_terms = struct.unpack_from("<HHI", data, 4)
    if version > VERSION_2:
        raise ValueError(f"version {version} is newer than this reader")
    postings, offset = {}, 12
    for _ in range(n_terms):
        (term_len,) = struct.unpack_from("<H", data, offset)
        offset += 2
        term = data[offset:offset + term_len].decode("utf-8")
        offset += term_len
        (count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        postings[term] = list(struct.unpack_from(f"<{count}I", data, offset))
        offset += 4 * count
    return ({"version": version, "flags": flags, "terms": n_terms,
             "_end_of_postings": offset}, postings)


# --------------------------------------------------------------------------

def main() -> None:
    ap = scale_parser(__doc__, default="part2")
    ap.add_argument("--batch", type=int, default=5_000)
    args = ap.parse_args()
    n = resolve_n(args)

    m = {"n_passages": n, "batch_size": args.batch}

    # ---- build one segment per batch, as documents arrive ---------------
    rule("1 · documents arrive in batches")
    texts = [t for _, t in iter_eval_corpus(n)]
    t0 = time.perf_counter()
    fresh_segments = []
    for start in range(0, len(texts), args.batch):
        docs = {i: texts[i] for i in range(start, min(start + args.batch, len(texts)))}
        fresh_segments.append(Segment(docs))
    build_seconds = time.perf_counter() - t0
    m["segments_built"] = len(fresh_segments)
    m["build_seconds"] = build_seconds
    print(f"  {len(fresh_segments)} segments of {args.batch:,} documents "
          f"in {human_time(build_seconds)}")

    # ---- what a rebuild would have cost ---------------------------------
    t0 = time.perf_counter()
    Segment({i: t for i, t in enumerate(texts)})
    rebuild_seconds = time.perf_counter() - t0
    m["full_rebuild_seconds"] = rebuild_seconds
    m["rebuild_vs_one_batch"] = rebuild_seconds / (build_seconds / len(fresh_segments))
    print(f"  rebuilding the whole index instead: {human_time(rebuild_seconds)}")
    print(f"  that is {m['rebuild_vs_one_batch']:.0f}x the cost of indexing "
          f"one batch — and you would pay it on every batch")

    # ---- query fanout, with the corpus held constant --------------------
    rule("2 · what unmerged segments cost a query")
    print("  the SAME 50,000 documents, cut into different numbers of "
          "segments on disk")
    scratch = Path(__file__).parent / "_segments"
    if scratch.exists():
        shutil.rmtree(scratch)

    m["fanout"] = []
    for parts in (1, 2, 5, 10, 25, 50):
        segs = split_into(texts, parts)
        disk = persist_segments(segs, scratch / f"p{parts}")
        counter = [0]
        best = None
        for _ in range(20):
            counter[0] = 0
            t0 = time.perf_counter()
            for term in PROBE_TERMS:
                search_all_disk(disk, term, counter)
            dt = (time.perf_counter() - t0) / len(PROBE_TERMS)
            best = dt if best is None else min(best, dt)
        crossings = counter[0] / len(PROBE_TERMS)
        total_bytes = sum(d.path.stat().st_size for d in disk)
        for d in disk:
            d.close()
        m["fanout"].append({
            "segments": parts, "seconds": best,
            "reads_per_query": crossings,
            "index_bytes": total_bytes,
            "docs": sum(s.n_docs for s in segs),
        })
        print(f"  {parts:>3} segment(s): {best * 1e6:>8.1f} µs per query, "
              f"{crossings:>5.1f} reads, {human_bytes(total_bytes)} on disk")

    base = m["fanout"][0]["seconds"]
    for row in m["fanout"]:
        row["vs_one_segment"] = row["seconds"] / base
    m["fanout_penalty"] = m["fanout"][-1]["vs_one_segment"]
    m["fanout_size_growth"] = (m["fanout"][-1]["index_bytes"]
                               / m["fanout"][0]["index_bytes"])
    print(f"  {m['fanout'][-1]['segments']} segments cost "
          f"{m['fanout_penalty']:.1f}x a single segment for the same corpus, "
          f"and take {m['fanout_size_growth']:.2f}x the disk")
    shutil.rmtree(scratch, ignore_errors=True)

    # ---- the trade, swept -----------------------------------------------
    rule("3 · the merge policy, swept")
    print(f"  {'fan':>4}  {'segments left':>14}  {'docs rewritten':>15}  "
          f"{'query':>10}  {'merge time':>11}")
    m["policies"] = []
    policy_dir = Path(__file__).parent / "_policy"
    if policy_dir.exists():
        shutil.rmtree(policy_dir)
    many = split_into(texts, 50)          # 50 batches have arrived
    for fan in (2, 3, 4, 8, 16, 10_000):
        segs = list(many)
        t0 = time.perf_counter()
        segs, rewritten = apply_merge_policy(segs, fan=fan) if fan < 10_000 \
            else (segs, 0)
        merge_seconds = time.perf_counter() - t0

        disk = persist_segments(segs, policy_dir / f"f{fan}")
        best = None
        for _ in range(20):
            t0 = time.perf_counter()
            for term in PROBE_TERMS:
                search_all_disk(disk, term)
            dt = (time.perf_counter() - t0) / len(PROBE_TERMS)
            best = dt if best is None else min(best, dt)
        for d in disk:
            d.close()

        row = {"fan": fan if fan < 10_000 else None,
               "label": f"fan={fan}" if fan < 10_000 else "never merge",
               "segments": len(segs), "rewritten": rewritten,
               "query_seconds": best, "merge_seconds": merge_seconds}
        m["policies"].append(row)
        print(f"  {row['label']:>11}  {len(segs):>6}  {rewritten:>15,}  "
              f"{best * 1e6:>8.1f} µs  {human_time(merge_seconds):>11}")

    shutil.rmtree(policy_dir, ignore_errors=True)
    fastest_query = min(m["policies"], key=lambda r: r["query_seconds"])
    cheapest_write = min(m["policies"], key=lambda r: r["rewritten"])
    m["trade"] = {
        "fastest_query": fastest_query["label"],
        "cheapest_write": cheapest_write["label"],
        "they_differ": fastest_query["label"] != cheapest_write["label"],
        "query_spread": (max(r["query_seconds"] for r in m["policies"])
                         / min(r["query_seconds"] for r in m["policies"])),
    }
    print(f"\n  fastest queries: {fastest_query['label']}   "
          f"cheapest ingestion: {cheapest_write['label']}")
    print(f"  they are not the same policy. that is the whole trade.")

    # ---- persistence ----------------------------------------------------
    rule("4 · writing the index down")
    seg = fresh_segments[0]
    blob = write_index(seg)
    header, postings = read_index(blob)
    m["format"] = {
        "postings": seg.n_postings,
        "terms": len(seg.postings),
        "bytes": len(blob),
        "bytes_per_posting": len(blob) / seg.n_postings,
        "round_trip_ok": postings == {k: sorted(v) for k, v in seg.postings.items()},
        "header": header,
    }
    print(f"  {seg.n_postings:,} postings -> {human_bytes(len(blob))} "
          f"({len(blob) / seg.n_postings:.2f} bytes/posting)")
    print(f"  round trip ok: {m['format']['round_trip_ok']}")

    rule("5 · the compatibility matrix")
    doc_lengths = {d: len(tokenize(texts[d])) for d in seg.doc_ids[:200]}
    blob_v2 = write_index_v2(seg, doc_lengths)
    matrix = {}

    # old reader, old data
    try:
        read_index(blob)
        matrix["v1_reader_v1_data"] = "reads it"
    except Exception as e:
        matrix["v1_reader_v1_data"] = f"{type(e).__name__}: {e}"

    # old reader, new data — must refuse rather than guess
    try:
        read_index(blob_v2)
        matrix["v1_reader_v2_data"] = "reads it (WRONG — it should refuse)"
    except ValueError as e:
        matrix["v1_reader_v2_data"] = f"refuses: {e}"

    # new reader, old data — must still work
    try:
        h, p, lengths = read_index_v2(blob)
        matrix["v2_reader_v1_data"] = (
            f"reads it, {len(lengths)} document lengths (none, correctly)")
    except Exception as e:
        matrix["v2_reader_v1_data"] = f"{type(e).__name__}: {e}"

    # new reader, new data
    try:
        h, p, lengths = read_index_v2(blob_v2)
        matrix["v2_reader_v2_data"] = f"reads it, {len(lengths)} document lengths"
    except Exception as e:
        matrix["v2_reader_v2_data"] = f"{type(e).__name__}: {e}"

    m["compatibility"] = matrix
    m["v2_bytes"] = len(blob_v2)
    m["v2_overhead_bytes"] = len(blob_v2) - len(blob)
    for k, v in matrix.items():
        print(f"  {k:<22} {v}")

    # and what pickle does instead
    import pickle
    pkl = pickle.dumps(seg)
    m["pickle"] = {
        "bytes": len(pkl),
        "vs_own_format": len(pkl) / len(blob),
        "note": ("pickle stores the class path. Rename or move the Segment "
                 "class and every saved index becomes unreadable, with no "
                 "version number to tell you why."),
    }
    print(f"\n  pickle of the same segment: {human_bytes(len(pkl))} "
          f"({len(pkl) / len(blob):.2f}x your format)")
    print(f"  {m['pickle']['note']}")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
