#!/usr/bin/env python3
"""Check your starter.py against the reference.

    python exercises/11-retrieval-at-scale/verify.py

The important check is not that your code is fast. It is that all three
strategies return the SAME answer.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402

DOCS = [
    "the block device hands back four thousand bytes at a time",
    "a storage engine batches writes to stay off the boundary",
    "block block block and another block for good measure",
    "reading many small files costs more than one large file",
    "the index moves work from query time to build time",
    "posting lists are sorted so you can skip through them",
    "an upper bound lets you refuse to score a document",
    "the device returns whole blocks and nothing smaller",
] * 40

QUERIES = ["block device", "storage engine writes", "index build time",
           "the block", "posting lists skip", "small files cost"]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    yours, ref = load("starter"), load("solution")
    index_y = yours.ScaleIndex(DOCS, skip_stride=8)
    index_r = ref.ScaleIndex(DOCS, skip_stride=8)
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    # ---- TODO 2, checked first because the others use it -----------------
    try:
        stats = {"touched": 0, "skips": 0}
        ids = index_r.postings["block"][0]
        c = yours.Cursor("block", ids, index_r.postings["block"][2],
                         index_r.upper["block"], stats)
        target = int(ids[len(ids) // 2])
        c.advance_skipping(target, 8)
        check("advance_skipping lands on the first id >= target",
              c.doc == target, f"landed on {c.doc}, expected {target}")
        check("advance_skipping counted the postings it moved over",
              stats["touched"] > 0, "touched is still 0 — count every look")

        stats2 = {"touched": 0, "skips": 0}
        c2 = yours.Cursor("block", ids, index_r.postings["block"][2],
                          index_r.upper["block"], stats2)
        c2.advance_linear(target)
        check("skipping touches fewer postings than stepping",
              stats["touched"] < stats2["touched"],
              f"skipping touched {stats['touched']}, "
              f"stepping touched {stats2['touched']}")
    except Exception as e:
        check("advance_skipping runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 1 and 3, against the reference -----------------------------
    for name in ("daat", "wand"):
        try:
            for q in QUERIES:
                got, _ = getattr(yours, name)(index_y, q)
                want, _ = getattr(ref, name)(index_r, q)
                ok = [d for d, _ in got] == [d for d, _ in want]
                check(f"{name}({q!r}) matches the reference", ok,
                      f"yours {[d for d, _ in got]}, "
                      f"reference {[d for d, _ in want]}")
                if not ok:
                    break
        except Exception as e:
            check(f"{name} runs", False, f"{type(e).__name__}: {e}")

    # ---- the check the module is actually about --------------------------
    try:
        disagreements = []
        for q in QUERIES:
            a, _ = yours.taat(index_y, q)
            b, _ = yours.daat(index_y, q)
            c, sc = yours.wand(index_y, q)
            ranks = ([d for d, _ in a], [d for d, _ in b], [d for d, _ in c])
            if not (ranks[0] == ranks[1] == ranks[2]):
                disagreements.append((q, ranks))
        check("all three strategies return the same top 10",
              not disagreements,
              "\n         ".join(
                  f"{q!r}: taat={r[0]} daat={r[1]} wand={r[2]}"
                  for q, r in disagreements[:2]))
    except Exception as e:
        check("the three strategies agree", False, f"{type(e).__name__}: {e}")

    # ---- and that WAND actually prunes -----------------------------------
    try:
        _, s_daat = yours.daat(index_y, "the block")
        _, s_wand = yours.wand(index_y, "the block")
        check("WAND scores fewer documents than document-at-a-time",
              s_wand["scored"] < s_daat["scored"],
              f"WAND scored {s_wand['scored']}, daat scored "
              f"{s_daat['scored']} — if they match, the threshold is probably "
              f"never being updated")
    except Exception as e:
        check("WAND prunes", False, f"{type(e).__name__}: {e}")

    rule("module 11 — your query processing against the reference")
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
