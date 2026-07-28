#!/usr/bin/env python3
"""Check that module 1's observations reproduced on your machine.

    python exercises/01-what-is-a-file/verify.py

Each check names what it expects and why. A failure here is not a broken
exercise — it usually means your filesystem does something different, and the
module page's troubleshooting note says which.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import read_measurements, rule   # noqa: E402

SLUG = "01-what-is-a-file"


def main() -> int:
    m = read_measurements(SLUG)
    if not m:
        print("no measurements yet — run investigate.py first")
        return 1

    checks = []

    def check(name, ok, detail):
        checks.append((name, ok, detail))

    three = m["three_char"]
    check("a 3-byte file reserves more than 3 bytes",
          three["allocated"] > three["size"],
          f"{three['size']} bytes of content, {three['allocated']} reserved")

    check("the reservation is a whole number of blocks",
          three["allocated"] % m["alloc_block_size"] == 0,
          f"{three['allocated']} / {m['alloc_block_size']} = "
          f"{three['allocated'] // m['alloc_block_size']} block(s)")

    check("one byte past a full block takes a second block",
          m["boundary"]["doubles_at_plus_1"],
          f"{m['boundary']['at_block']['size']} B reserves "
          f"{m['boundary']['at_block']['allocated']} B; "
          f"{m['boundary']['at_block_plus_1']['size']} B reserves "
          f"{m['boundary']['at_block_plus_1']['allocated']} B")

    check("appending one character did not move the reservation",
          m["allocation_unchanged_on_append"],
          f"{three['allocated']} before and after")

    check("two names shared one record number",
          m["hardlink"]["same_inode"],
          f"inode {m['hardlink']['inode_a']} for both names")

    check("the record counted both names",
          m["hardlink"]["link_count"] == 2,
          f"link count {m['hardlink']['link_count']}")

    check("deleting one name left the bytes readable",
          m["after_unlink"]["content"] == "abcd",
          f"surviving name still reads {m['after_unlink']['content']!r}")

    if "sparse" in m:
        check("a claimed gigabyte occupied almost no disk",
              m["sparse"]["allocated"] < m["sparse"]["apparent"] / 100,
              f"{m['sparse']['apparent']:,} claimed, "
              f"{m['sparse']['allocated']:,} reserved")

    check("`file` identified a renamed PNG from its bytes",
          "PNG" in m["rename"]["after"],
          m["rename"]["after"].strip())

    rule("module 1 — do the observations hold?")
    failed = 0
    for name, ok, detail in checks:
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {name}")
        print(f"         {detail}")
        failed += 0 if ok else 1

    print()
    if failed:
        print(f"{failed} of {len(checks)} checks did not hold — see the "
              f"troubleshooting note on the module page.")
    else:
        print(f"all {len(checks)} checks hold.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
