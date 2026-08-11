#!/usr/bin/env python3
"""Fetch and build every corpus the site needs.

Idempotent and resumable. Interrupt it, run it again, it picks up where it
stopped. Nothing here is a step in any module — it is setup, done once.

    python data/fetch.py                 # everything
    python data/fetch.py --small         # 100k passages instead of 8.8M
    python data/fetch.py --only pdfs     # just the difficult documents

What it produces, and roughly what it costs:

    data/msmarco/collection.tsv          3.2 GB   8.8M passages
    data/msmarco/queries.dev.small.tsv   0.3 MB   6,980 queries
    data/msmarco/qrels.dev.small.tsv     0.1 MB   relevance judgments
    data/hard_pdfs/                       ~25 MB   ~20 documents that fight back
    data/invoices/                        ~8 MB   300 invoices + ground truth
    data/corpus_small/                    ~4 MB   10k text files (module 4)

--small stops after 100,000 passages, which is what Part II needs. Part III
wants the full collection; you can re-run without --small later and it will
only fetch what is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

MSMARCO_DIR = HERE / "msmarco"
PDF_DIR = HERE / "hard_pdfs"
INVOICE_DIR = HERE / "invoices"
SMALL_CORPUS_DIR = HERE / "corpus_small"
SMALL_CORPUS_ZIP = HERE / "corpus_small.zip"   # shipped with the repo

COLLECTION_URL = (
    "https://msmarco.z22.web.core.windows.net/msmarcoranking/"
    "collectionandqueries.tar.gz"
)
COLLECTION_BYTES = 1_057_717_952

USER_AGENT = "beneath-the-pipeline/1.0 (tutorial corpus fetcher)"


# --------------------------------------------------------------------------
# resumable download
# --------------------------------------------------------------------------

def _fmt(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def download(url: str, dest: Path, *, expected_bytes: int | None = None,
             quiet: bool = False) -> Path:
    """Download url to dest, resuming a partial file if one is there.

    The partial lives at dest.part until it is complete, so a half-finished
    download is never mistaken for a finished one.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if expected_bytes is None or dest.stat().st_size == expected_bytes:
            if not quiet:
                print(f"  have  {dest.name} ({_fmt(dest.stat().st_size)})")
            return dest
        print(f"  size mismatch on {dest.name}, refetching")
        dest.unlink()

    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0

    headers = {"User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
        print(f"  resume {dest.name} at {_fmt(have)}")
    else:
        print(f"  get   {dest.name}")

    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416 and have:          # already complete
            part.rename(dest)
            return dest
        raise

    # A server that ignores Range replies 200 and sends the whole thing.
    if have and resp.status == 200:
        have = 0
        part.unlink(missing_ok=True)

    total = have + int(resp.headers.get("Content-Length") or 0)
    mode = "ab" if have else "wb"
    # Only draw a progress bar for a human. Redirected to a log, the carriage
    # returns turn into one enormous line.
    quiet = quiet or not sys.stdout.isatty()
    t0, last = time.time(), 0.0
    with part.open(mode) as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            have += len(chunk)
            now = time.time()
            if not quiet and now - last > 0.5:
                pct = f"{100 * have / total:5.1f}%" if total else "     "
                rate = have / max(now - t0, 1e-6)
                sys.stdout.write(
                    f"\r        {pct}  {_fmt(have)}  ({_fmt(rate)}/s)   ")
                sys.stdout.flush()
                last = now
    if not quiet:
        sys.stdout.write("\r" + " " * 60 + "\r")
    part.rename(dest)
    print(f"  done  {dest.name} ({_fmt(dest.stat().st_size)})")
    return dest


# --------------------------------------------------------------------------
# MS MARCO
# --------------------------------------------------------------------------

WANTED_MEMBERS = {
    "collection.tsv",
    "queries.dev.small.tsv",
    "qrels.dev.small.tsv",
}


def fetch_msmarco(small: bool) -> None:
    """The passage collection, dev queries, and relevance judgments.

    The judgments are the reason this corpus and not a prettier one: module 8
    cannot measure ranking quality without somebody having said, for a set of
    real queries, which passages actually answer them.
    """
    print("\nMS MARCO passages")
    MSMARCO_DIR.mkdir(parents=True, exist_ok=True)

    collection = MSMARCO_DIR / "collection.tsv"
    queries = MSMARCO_DIR / "queries.dev.small.tsv"
    qrels = MSMARCO_DIR / "qrels.dev.small.tsv"

    if collection.exists() and queries.exists() and qrels.exists():
        n = count_lines(collection)
        if small or n > 1_000_000:
            print(f"  have  collection.tsv ({n:,} passages)")
            _write_manifest(n)
            return

    archive = MSMARCO_DIR / "collectionandqueries.tar.gz"
    download(COLLECTION_URL, archive, expected_bytes=COLLECTION_BYTES)

    print("  extract collection.tsv, queries.dev.small.tsv, qrels.dev.small.tsv")
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = Path(member.name).name
            if name not in WANTED_MEMBERS:
                continue
            out = MSMARCO_DIR / name
            if out.exists() and out.stat().st_size > 0 and name != "collection.tsv":
                continue
            src = tar.extractfile(member)
            if src is None:
                continue
            if name == "collection.tsv" and small:
                _extract_head(src, out, 100_000)
            else:
                with out.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1 << 22)
            print(f"    {name}  ({_fmt(out.stat().st_size)})")

    n = count_lines(collection)
    print(f"  collection.tsv holds {n:,} passages")
    _write_manifest(n)

    if not small:
        # The archive is 1 GB and we are done with it. Keep it only if the
        # user asked for --small, where they may want the rest later.
        archive.unlink(missing_ok=True)


def _extract_head(src, out: Path, lines: int) -> None:
    written, buf = 0, b""
    with out.open("wb") as dst:
        while written < lines:
            chunk = src.read(1 << 22)
            if not chunk:
                break
            buf += chunk
            *ready, buf = buf.split(b"\n")
            for line in ready:
                dst.write(line + b"\n")
                written += 1
                if written >= lines:
                    return


def count_lines(path: Path) -> int:
    n = 0
    with path.open("rb") as f:
        while chunk := f.read(1 << 22):
            n += chunk.count(b"\n")
    return n


def _write_manifest(n_passages: int) -> None:
    (MSMARCO_DIR / "manifest.json").write_text(json.dumps({
        "passages": n_passages,
        "source": COLLECTION_URL,
        "fetched_unix": int(time.time()),
    }, indent=2) + "\n")


# --------------------------------------------------------------------------
# difficult PDFs
# --------------------------------------------------------------------------

# Real documents, chosen because each one breaks a different assumption.
# Every entry says what makes it hard — that is the reason it is in the list.
REAL_PDFS = [
    ("acl-2col-01.pdf", "https://aclanthology.org/P19-1285.pdf",
     "two-column conference paper, footnotes, inline citations"),
    ("acl-2col-02.pdf", "https://aclanthology.org/N19-1423.pdf",
     "two-column paper with wide result tables spanning both columns"),
    ("acl-2col-03.pdf", "https://aclanthology.org/D19-1410.pdf",
     "two-column paper, dense math, subscripted notation"),
    ("arxiv-transformer.pdf", "https://arxiv.org/pdf/1706.03762",
     "single column, figures with embedded captions, tables of numbers"),
    ("arxiv-resnet.pdf", "https://arxiv.org/pdf/1512.03385",
     "two-column, very large tables, figures interleaved with body text"),
    ("arxiv-bert.pdf", "https://arxiv.org/pdf/1810.04805",
     "two-column, ablation tables, appendix with different layout"),
    ("arxiv-adam.pdf", "https://arxiv.org/pdf/1412.6980",
     "algorithm blocks — pseudocode that linearises into nonsense"),
    ("arxiv-doclaynet.pdf", "https://arxiv.org/pdf/2206.01062",
     "the layout-analysis dataset paper, itself a hard layout"),
    ("irs-w9.pdf", "https://www.irs.gov/pub/irs-pdf/fw9.pdf",
     "government form: field boxes, checkboxes, instructions in a sidebar"),
    ("irs-1040.pdf", "https://www.irs.gov/pub/irs-pdf/f1040.pdf",
     "tax form: a grid of labelled boxes with no reading order at all"),
    ("irs-1099misc.pdf", "https://www.irs.gov/pub/irs-pdf/f1099msc.pdf",
     "multi-copy form, repeated layout, colour-dependent structure"),
    ("irs-schedule-c.pdf", "https://www.irs.gov/pub/irs-pdf/f1040sc.pdf",
     "form with a table of numbered line items and running totals"),
]


def fetch_pdfs() -> None:
    print("\nDifficult PDFs")
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    notes = {}
    got = 0
    for name, url, why in REAL_PDFS:
        dest = PDF_DIR / name
        try:
            download(url, dest, quiet=True)
            notes[name] = {"source": url, "difficulty": why, "origin": "downloaded"}
            got += 1
        except Exception as e:
            print(f"  SKIP  {name}: {e}")
    print(f"  {got}/{len(REAL_PDFS)} real documents")

    # Generated documents cover the cases that are hard to find on demand and
    # must be present for modules 5 and 13 to work at all.
    print("  generating the rest (scan, rotation, columns, tables)")
    from make_hard_pdfs import generate_hard_pdfs  # noqa: E402
    notes.update(generate_hard_pdfs(PDF_DIR))

    (PDF_DIR / "manifest.json").write_text(
        json.dumps(notes, indent=2, sort_keys=True) + "\n")
    print(f"  {len(notes)} documents in {PDF_DIR}")

    # Part 0's pipeline runs against a small, ordinary folder — the kind of
    # folder a tutorial would use. Nothing pathological in here.
    sample = REPO / "pipeline" / "sample_pdfs"
    sample.mkdir(parents=True, exist_ok=True)
    for name in ("gen-clean-1col.pdf", "gen-tables.pdf", "arxiv-transformer.pdf",
                 "arxiv-adam.pdf", "acl-2col-01.pdf"):
        src = PDF_DIR / name
        if src.exists() and not (sample / name).exists():
            shutil.copy2(src, sample / name)
    print(f"  {len(list(sample.glob('*.pdf')))} sample PDFs for the Part 0 pipeline")


# --------------------------------------------------------------------------
# invoices — module 14's structured corpus
# --------------------------------------------------------------------------

def fetch_invoices(n: int = 300) -> None:
    print("\nInvoice corpus (module 14)")
    truth = INVOICE_DIR / "ground_truth.json"
    if truth.exists():
        existing = json.loads(truth.read_text())
        if len(existing.get("invoices", [])) >= n:
            print(f"  have  {len(existing['invoices'])} invoices")
            return
    from make_invoices import generate_invoices  # noqa: E402
    generate_invoices(INVOICE_DIR, n=n)


# --------------------------------------------------------------------------
# small file corpus — module 4's ten thousand small files
# --------------------------------------------------------------------------

PER_FILE = 12          # passages per small file — about 4 KB each


def build_small_corpus(n_files: int = 10_000) -> None:
    """One corpus, written two ways: as many small files and as one big file.

    Module 4 reads both and compares. Building it here keeps the exercise
    about reading, not about generating. Each small file lands near 4 KB,
    which is also one filesystem block — module 1's number, showing up again.
    """
    print("\nSmall-file corpus (module 4)")
    marker = SMALL_CORPUS_DIR / ".complete"
    if marker.exists() and json.loads(marker.read_text())["files"] == n_files:
        print(f"  have  {n_files:,} files")
        return

    # The repo ships the corpus as one zip so cloning stays fast; the ten
    # thousand files only exist after this extraction.
    if SMALL_CORPUS_ZIP.exists() and n_files == 10_000:
        import zipfile
        print(f"  unpacking {SMALL_CORPUS_ZIP.name}")
        files_dir = SMALL_CORPUS_DIR / "files"
        if files_dir.exists():
            shutil.rmtree(files_dir)
        with zipfile.ZipFile(SMALL_CORPUS_ZIP) as z:
            shipped = json.loads(z.read("manifest.json"))
            z.extractall(SMALL_CORPUS_DIR)
        (SMALL_CORPUS_DIR / "manifest.json").unlink()
        with (SMALL_CORPUS_DIR / "all.txt").open("w", encoding="utf-8") as big:
            for f in sorted(files_dir.glob("*.txt")):
                big.write(f.read_text(encoding="utf-8"))
        marker.write_text(json.dumps(shipped, indent=2) + "\n")
        print(f"  {shipped['files']:,} files of ~{_fmt(shipped['bytes'] / shipped['files'])} "
              f"and one {_fmt(shipped['bytes'])} file, from {shipped['origin']}")
        return

    files_dir = SMALL_CORPUS_DIR / "files"
    if files_dir.exists():
        shutil.rmtree(files_dir)
    files_dir.mkdir(parents=True)

    need = n_files * PER_FILE
    passages = []
    try:
        from exercises.common import iter_passages
        passages = [t for _, t in iter_passages(need)]
    except SystemExit:
        pass

    if len(passages) < need:
        # No collection yet — synthesise text of a similar shape so module 4
        # still runs. Says so in the manifest; the site notes it too.
        import random
        rng = random.Random(20260728)
        words = ("index posting block offset buffer encode decode passage "
                 "vector token chunk stride segment merge scan").split()
        while len(passages) < need:
            passages.append(" ".join(rng.choices(words, k=rng.randint(40, 120))))
        origin = "synthetic"
    else:
        origin = "msmarco"

    total = 0
    single = SMALL_CORPUS_DIR / "all.txt"
    with single.open("w", encoding="utf-8") as big:
        for i in range(n_files):
            body = "\n".join(passages[i * PER_FILE:(i + 1) * PER_FILE]) + "\n"
            (files_dir / f"{i:05d}.txt").write_text(body, encoding="utf-8")
            big.write(body)
            total += len(body.encode())
    marker.write_text(json.dumps(
        {"files": n_files, "bytes": total, "passages_per_file": PER_FILE,
         "origin": origin}, indent=2) + "\n")
    print(f"  {n_files:,} files of ~{_fmt(total / n_files)} and one "
          f"{_fmt(total)} file, from {origin}")


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=["msmarco", "pdfs", "invoices", "corpus", "all"],
                    default="all")
    ap.add_argument("--small", action="store_true",
                    help="100k passages instead of the full 8.8M collection")
    ap.add_argument("--invoices", type=int, default=300)
    args = ap.parse_args()

    sys.path.insert(0, str(HERE))
    t0 = time.time()
    if args.only in ("msmarco", "all"):
        fetch_msmarco(args.small)
    if args.only in ("pdfs", "all"):
        fetch_pdfs()
    if args.only in ("invoices", "all"):
        fetch_invoices(args.invoices)
    if args.only in ("corpus", "all"):
        build_small_corpus()
    print(f"\nready in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
