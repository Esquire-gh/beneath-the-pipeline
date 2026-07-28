#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/10-ingestion-vs-query/verify.py
"""
import importlib.util
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

BATCH_A = {0: "the block device", 1: "a storage engine batches writes"}
BATCH_B = {2: "block and index", 3: "reading many small files"}
BATCH_C = {4: "the index moves work", 5: "block device again"}


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

    segs_y = [yours.Segment(b) for b in (BATCH_A, BATCH_B, BATCH_C)]
    segs_r = [ref.Segment(b) for b in (BATCH_A, BATCH_B, BATCH_C)]

    # ---- TODO 1 ----------------------------------------------------------
    try:
        got = yours.search_all(segs_y, "block")
        check("search_all returns (ids, segments touched)",
              isinstance(got, tuple) and len(got) == 2, f"got {got!r}")
        if isinstance(got, tuple) and len(got) == 2:
            ids, fanout = got
            check("search_all found every matching document",
                  list(ids) == [0, 2, 5], f"got {list(ids)}, expected [0, 2, 5]")
            check("search_all reports the fanout", fanout == 3,
                  f"got {fanout}, expected 3")
            check("search_all removes duplicates",
                  len(list(ids)) == len(set(ids)), f"got {list(ids)}")
        empty = yours.search_all(segs_y, "zyzzyva")
        check("search_all handles a term nothing has",
              empty and list(empty[0]) == [], f"got {empty!r}")
    except Exception as e:
        check("search_all runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 2 ----------------------------------------------------------
    try:
        merged = yours.merge_segments(segs_y[0], segs_y[1])
        want = ref.merge_segments(segs_r[0], segs_r[1])
        check("merge_segments returns a Segment-like object",
              hasattr(merged, "postings") and hasattr(merged, "doc_ids"),
              f"got {type(merged).__name__}")
        if hasattr(merged, "postings"):
            check("the merged vocabulary is the union",
                  set(merged.postings) == set(want.postings),
                  f"{len(set(merged.postings) ^ set(want.postings))} terms differ")
            check("merged posting lists are sorted",
                  all(list(v) == sorted(v) for v in merged.postings.values()),
                  "at least one merged posting list is out of order")
            check("merged posting lists match the reference",
                  all(list(merged.postings[t]) == want.postings[t]
                      for t in want.postings if t in merged.postings),
                  "a merged posting list differs")
            check("the merged segment knows about every document",
                  sorted(merged.doc_ids) == [0, 1, 2, 3],
                  f"got {sorted(merged.doc_ids)}")
    except Exception as e:
        check("merge_segments runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 3 ----------------------------------------------------------
    try:
        many = [yours.Segment({i: "block device index"}) for i in range(16)]
        got = yours.apply_merge_policy(many, fan=4)
        check("apply_merge_policy returns (segments, rewritten)",
              isinstance(got, tuple) and len(got) == 2, f"got {got!r}")
        if isinstance(got, tuple) and len(got) == 2:
            segs, rewritten = got
            check("merging reduced the segment count",
                  len(segs) < 16, f"{len(segs)} segments left, started with 16")
            check("rewritten counts the documents the merges moved",
                  rewritten > 0, f"got {rewritten}")
            check("no documents were lost",
                  sum(s.n_docs for s in segs) == 16,
                  f"{sum(s.n_docs for s in segs)} documents across the segments, "
                  f"expected 16")
        untouched = yours.apply_merge_policy([yours.Segment({0: "one"})], fan=4)
        check("a single segment is left alone",
              untouched and len(untouched[0]) == 1 and untouched[1] == 0,
              f"got {untouched!r}")
    except Exception as e:
        check("apply_merge_policy runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 4 ----------------------------------------------------------
    try:
        blob = yours.write_index(segs_y[0])
        check("write_index returns bytes", isinstance(blob, (bytes, bytearray)),
              f"got {type(blob).__name__}")
        if isinstance(blob, (bytes, bytearray)):
            check("the file starts with the magic bytes",
                  bytes(blob[:4]) == yours.MAGIC,
                  f"starts with {bytes(blob[:4])!r}, expected {yours.MAGIC!r}")
            version, flags, n_terms = struct.unpack_from("<HHI", blob, 4)
            check("the version field is where the header says",
                  version == yours.VERSION,
                  f"read version {version}, expected {yours.VERSION}")
            check("the term count is right", n_terms == len(segs_y[0].postings),
                  f"header says {n_terms}, segment has "
                  f"{len(segs_y[0].postings)}")
            header, postings = yours.read_index(bytes(blob))
            check("the index round trips",
                  postings == {k: sorted(v)
                               for k, v in segs_y[0].postings.items()},
                  "read_index did not return what write_index was given")
            check("your bytes match the reference implementation",
                  bytes(blob) == ref.write_index(segs_r[0]),
                  "same data, different bytes — check field order and widths")
    except Exception as e:
        check("write_index runs", False, f"{type(e).__name__}: {e}")

    rule("module 10 — your segments and format against the reference")
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
