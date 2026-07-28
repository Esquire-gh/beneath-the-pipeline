#!/usr/bin/env python3
"""Module 1 — what is a file, actually?

You can run every one of these by hand; the README lists the commands. This
script runs them for you, prints what came back, and records the numbers so
the module page reports your machine's answers rather than someone else's.

Standard library only. Nothing to install.

    python exercises/01-what-is-a-file/investigate.py
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import human_bytes, rule, write_measurements   # noqa: E402

SLUG = "01-what-is-a-file"
IS_MAC = sys.platform == "darwin"

# A complete, valid PNG of one transparent pixel. Written out byte for byte so
# module 1 needs nothing installed. Module 2 reads this signature properly.
ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def sh(cmd: str, cwd: Path) -> str:
    """Run a shell command and show it the way the reader would see it."""
    out = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                         text=True)
    text = (out.stdout + out.stderr).rstrip()
    print(f"  $ {cmd}")
    for line in text.splitlines():
        print(f"    {line}")
    return text


def stat_of(path: Path) -> dict:
    """The record the filesystem keeps about one file.

    st_blocks counts 512-byte units on both macOS and Linux, whatever the
    filesystem's own block size is. Multiply to get bytes actually reserved.
    """
    st = path.stat()
    return {
        "size": st.st_size,
        "blocks_512": st.st_blocks,
        "allocated": st.st_blocks * 512,
        "inode": st.st_ino,
        "links": st.st_nlink,
    }


def main() -> None:
    m = {"platform": platform.system(), "is_mac": IS_MAC}
    tmp = Path(tempfile.mkdtemp(prefix="btp-module1-"))
    print(f"working in {tmp}\n")

    # ---- how big is a block on this filesystem? --------------------------
    #
    # Do not trust statvfs for this. f_bsize is the size the OS would *prefer*
    # you read in — 1 MB on APFS — which is a different question from how much
    # disk one small file takes. Measure the allocation unit instead: write one
    # byte and see how much gets reserved.
    rule("0 · the smallest amount of disk this filesystem hands out")
    vfs = os.statvfs(tmp)
    probe = tmp / "one-byte"
    probe.write_bytes(b"x")
    alloc_unit = probe.stat().st_blocks * 512
    probe.unlink()

    m["alloc_block_size"] = alloc_unit
    m["statvfs_bsize"] = vfs.f_bsize
    m["statvfs_frsize"] = vfs.f_frsize
    print(f"  one byte on disk reserves: {alloc_unit} bytes  <- the block")
    print(f"  statvfs f_bsize (preferred read size, a different question): "
          f"{vfs.f_bsize}")
    sh("stat -f %k ." if IS_MAC else "stat -f -c %s .", tmp)

    # ---- a file of three characters --------------------------------------
    rule("1 · a file holding three characters")
    three = tmp / "three.txt"
    three.write_text("abc")
    s = stat_of(three)
    m["three_char"] = s
    print(f"  size      {s['size']} bytes")
    print(f"  allocated {s['allocated']} bytes "
          f"({s['blocks_512']} × 512-byte units)")
    print(f"  the gap   {s['allocated'] - s['size']} bytes you cannot use")
    sh("stat -x three.txt" if IS_MAC else "stat three.txt", tmp)

    # ---- append one character --------------------------------------------
    rule("2 · append one character")
    with three.open("a") as f:
        f.write("d")
    s2 = stat_of(three)
    m["four_char"] = s2
    print(f"  size      {s['size']} -> {s2['size']}")
    print(f"  allocated {s['allocated']} -> {s2['allocated']}"
          f"{'   (unchanged)' if s2['allocated'] == s['allocated'] else ''}")
    m["allocation_unchanged_on_append"] = s2["allocated"] == s["allocated"]

    # Exactly where does the reservation move? Test the boundary itself rather
    # than stepping towards it, so the page can name the byte.
    grow = tmp / "grow.txt"
    edge = {}
    for n in (alloc_unit - 1, alloc_unit, alloc_unit + 1):
        grow.write_bytes(b"x" * n)
        edge[n] = grow.stat().st_blocks * 512
    m["boundary"] = {
        "at_block_minus_1": {"size": alloc_unit - 1, "allocated": edge[alloc_unit - 1]},
        "at_block": {"size": alloc_unit, "allocated": edge[alloc_unit]},
        "at_block_plus_1": {"size": alloc_unit + 1, "allocated": edge[alloc_unit + 1]},
        "doubles_at_plus_1": edge[alloc_unit + 1] > edge[alloc_unit],
    }
    for n in sorted(edge):
        print(f"  {n:>7,} bytes of content reserves {edge[n]:>7,} bytes of disk")

    # ---- two names, one file ---------------------------------------------
    rule("3 · two names for the same bytes")
    sh("ls -i three.txt", tmp)
    sh("ln three.txt also-three.txt", tmp)
    a, b = stat_of(three), stat_of(tmp / "also-three.txt")
    m["hardlink"] = {"inode_a": a["inode"], "inode_b": b["inode"],
                     "same_inode": a["inode"] == b["inode"],
                     "link_count": b["links"]}
    sh("ls -li three.txt also-three.txt", tmp)
    print(f"  same record number: {a['inode'] == b['inode']}")
    print(f"  that record now says {b['links']} names point at it")

    rule("4 · delete one name")
    sh("rm three.txt", tmp)
    survivor = tmp / "also-three.txt"
    still_there = survivor.read_text()
    m["after_unlink"] = {"content": still_there,
                         "links": stat_of(survivor)["links"]}
    print(f"  also-three.txt still reads: {still_there!r}")
    print(f"  link count is now {stat_of(survivor)['links']}")

    # ---- a file that claims a gigabyte -----------------------------------
    rule("5 · a file that says it is 1 GB")
    big = tmp / "big.img"
    sh("truncate -s 1G big.img 2>/dev/null || mkfile -n 1g big.img", tmp)
    if big.exists():
        st = stat_of(big)
        du = sh("du -h big.img", tmp)
        m["sparse"] = {"apparent": st["size"], "allocated": st["allocated"],
                       "du": du.split()[0] if du else None}
        print(f"  ls -l  says {human_bytes(st['size'])}")
        print(f"  actually on disk: {human_bytes(st['allocated'])}")

    # ---- the disk has no opinion about names -----------------------------
    rule("6 · rename a PNG to .txt")
    png = tmp / "icon.png"
    png.write_bytes(ONE_PIXEL_PNG)
    before = sh("file icon.png", tmp)
    sh("mv icon.png notes.txt", tmp)
    after = sh("file notes.txt", tmp)
    head = sh("head -c 8 notes.txt | xxd" if shutil.which("xxd")
              else "head -c 8 notes.txt | hexdump -C", tmp)
    m["rename"] = {"before": before, "after": after, "first_bytes": head}
    print("  the name changed. the bytes did not, and `file` reads the bytes.")

    # ---- a folder is a file too ------------------------------------------
    rule("7 · a folder is a file whose contents are a list")
    d = tmp / "folder"
    d.mkdir()
    for i in range(4):
        (d / f"item{i}.txt").write_text("x")
    ds = stat_of(d)
    m["directory"] = ds
    print(f"  the folder itself has record number {ds['inode']}, "
          f"size {ds['size']}, and {ds['allocated']} bytes reserved")
    print("  its contents are names paired with record numbers — nothing else")

    # ---- the real corpus, which pays this cost 10,000 times --------------
    corpus = REPO / "data" / "corpus_small" / "files"
    if corpus.exists():
        rule("8 · the same arithmetic, 10,000 times over")
        files = sorted(corpus.glob("*.txt"))
        total_size = sum(f.stat().st_size for f in files)
        total_alloc = sum(f.stat().st_blocks * 512 for f in files)
        m["corpus"] = {
            "files": len(files),
            "size": total_size,
            "allocated": total_alloc,
            "waste": total_alloc - total_size,
            "waste_ratio": total_alloc / total_size if total_size else None,
            "mean_file_size": total_size / len(files) if files else None,
        }
        print(f"  {len(files):,} files hold {human_bytes(total_size)} of text")
        print(f"  and reserve {human_bytes(total_alloc)} of disk")
        print(f"  overhead: {human_bytes(total_alloc - total_size)} "
              f"({total_alloc / total_size:.2f}× the text)")

    shutil.rmtree(tmp, ignore_errors=True)
    path = write_measurements(SLUG, m)
    print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
