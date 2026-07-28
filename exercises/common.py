"""Shared plumbing for every exercise.

Nothing in here is the point of any module. It exists so the exercises can
spend their lines on the idea instead of on argument parsing and path
juggling. Read it if you're curious; you never have to edit it.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
EXERCISES = REPO / "exercises"
SITE_DATA = REPO / "site" / "assets" / "data"


# --------------------------------------------------------------------------
# measurements
# --------------------------------------------------------------------------

def measurements_path(slug: str) -> Path:
    return EXERCISES / slug / "measurements.json"


def write_measurements(slug: str, values: dict, *, merge: bool = True) -> Path:
    """Write measurements for one module.

    Every number printed on the site comes from one of these files. The build
    script reads them; prose never hard-codes a figure.
    """
    path = measurements_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {}
    if merge and path.exists():
        try:
            out = json.loads(path.read_text())
        except json.JSONDecodeError:
            out = {}
    out.update(values)
    out["_machine"] = machine()
    out["_generated_unix"] = int(time.time())
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return path


def read_measurements(slug: str) -> dict:
    path = measurements_path(slug)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# --------------------------------------------------------------------------
# machine description — printed once in Part 0, stamped into every file
# --------------------------------------------------------------------------

def _sysctl(key: str) -> str | None:
    try:
        return subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=5
        ).stdout.strip() or None
    except Exception:
        return None


def _linux_cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def _linux_mem_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except Exception:
        pass
    return None


def gpu() -> dict:
    """What accelerator, if any, is available to PyTorch on this machine."""
    try:
        import torch
    except ImportError:
        return {"kind": "none", "name": None, "detail": "pytorch not installed"}
    if torch.cuda.is_available():
        return {"kind": "cuda", "name": torch.cuda.get_device_name(0),
                "detail": f"torch {torch.__version__}"}
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return {"kind": "mps", "name": "Apple Silicon GPU (Metal)",
                "detail": f"torch {torch.__version__}"}
    return {"kind": "cpu", "name": None, "detail": f"torch {torch.__version__}"}


def machine() -> dict:
    system = platform.system()
    if system == "Darwin":
        cpu_name = _sysctl("machdep.cpu.brand_string")
        mem = _sysctl("hw.memsize")
        mem_bytes = int(mem) if mem else None
        cores = os.cpu_count()
        try:
            info = subprocess.run(["diskutil", "info", "/"], capture_output=True,
                                  text=True, timeout=8).stdout
            ssd = "Yes" in next((l for l in info.splitlines()
                                 if "Solid State" in l), "")
            disk = "SSD" if ssd else "spinning disk"
        except Exception:
            disk = "unknown"
        os_name = f"macOS {platform.mac_ver()[0]}"
    elif system == "Linux":
        cpu_name = _linux_cpu_model()
        mem_bytes = _linux_mem_bytes()
        cores = os.cpu_count()
        disk = "unknown"
        try:
            rot = Path("/sys/block/sda/queue/rotational")
            if rot.exists():
                disk = "spinning disk" if rot.read_text().strip() == "1" else "SSD"
        except Exception:
            pass
        os_name = f"{platform.system()} {platform.release()}"
    else:
        cpu_name, mem_bytes, cores, disk = None, None, os.cpu_count(), "unknown"
        os_name = f"{platform.system()} {platform.release()}"

    return {
        "cpu": cpu_name or platform.processor() or "unknown",
        "cores": cores,
        "ram_bytes": mem_bytes,
        "ram_human": human_bytes(mem_bytes) if mem_bytes else "unknown",
        "disk": disk,
        "os": os_name,
        "python": platform.python_version(),
        "gpu": gpu(),
    }


# --------------------------------------------------------------------------
# timing and memory
# --------------------------------------------------------------------------

@contextmanager
def timed(label: str, *, quiet: bool = False):
    """Time a block. Yields a dict that gets a 'seconds' key on exit."""
    out = {"label": label}
    t0 = time.perf_counter()
    try:
        yield out
    finally:
        out["seconds"] = time.perf_counter() - t0
        if not quiet:
            print(f"  {label:<38} {out['seconds']:>8.3f} s")


def best_of(fn, runs: int = 3):
    """Run fn several times, return (best_seconds, all_seconds, result).

    Best-of, not mean: the fastest run is the one least polluted by whatever
    else your machine was doing. Ratios between best-of runs reproduce; means
    do not.
    """
    times, result = [], None
    for _ in range(runs):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return min(times), times, result


def peak_rss_bytes() -> int:
    """Largest amount of physical memory this process has held.

    ru_maxrss is bytes on macOS and kilobytes on Linux. Yes, really.
    """
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw if sys.platform == "darwin" else raw * 1024


def current_rss_bytes() -> int | None:
    """Memory held right now, if the platform will tell us cheaply."""
    if sys.platform == "linux":
        try:
            for line in Path("/proc/self/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
        except Exception:
            return None
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.strip()) * 1024
    except Exception:
        return None


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------

def human_bytes(n: float | None) -> str:
    if n is None:
        return "unknown"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_time(seconds: float) -> str:
    if seconds < 1e-3:
        return f"{seconds * 1e6:.0f} µs"
    if seconds < 1:
        return f"{seconds * 1e3:.1f} ms"
    if seconds < 90:
        return f"{seconds:.2f} s"
    return f"{seconds / 60:.1f} min"


def rule(title: str = "") -> None:
    width = min(shutil.get_terminal_size((78, 20)).columns, 78)
    if title:
        print(f"\n── {title} " + "─" * max(0, width - len(title) - 4))
    else:
        print("─" * width)


# --------------------------------------------------------------------------
# scale — so this runs on a laptop, not only on the machine that wrote the site
# --------------------------------------------------------------------------

SCALES = {
    "tiny":  10_000,
    "small": 50_000,
    "part2": 100_000,
    "big":   1_000_000,
}


def scale_parser(description: str, default: str = "small") -> argparse.ArgumentParser:
    """Every exercise takes --scale.

    The site's own numbers were produced at the scale each page names. The
    default here is deliberately modest so the exercise finishes on a laptop
    without swapping. Ratios hold across scales; absolutes do not.
    """
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--scale", choices=sorted(SCALES), default=default,
                   help=f"corpus size to run against (default: {default})")
    p.add_argument("--limit", type=int, default=None,
                   help="exact number of passages, overrides --scale")
    p.add_argument("--no-write", action="store_true",
                   help="skip writing measurements.json")
    return p


def resolve_n(args) -> int:
    return args.limit if args.limit else SCALES[args.scale]


# --------------------------------------------------------------------------
# corpus access
# --------------------------------------------------------------------------

def corpus_file(name: str) -> Path:
    path = DATA / name
    if not path.exists():
        sys.exit(
            f"missing {path}\n"
            f"run:  python data/fetch.py\n"
            f"(it is resumable — safe to re-run if it was interrupted)"
        )
    return path


def iter_passages(limit: int | None = None):
    """Yield (pid, text) from the MS MARCO passage collection, streaming.

    Streaming, not loading. Module 9 makes an argument out of this; the rest
    of the exercises get it for free.
    """
    path = corpus_file("msmarco/collection.tsv")
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                return
            pid, _, text = line.partition("\t")
            yield int(pid), text.rstrip("\n")


def load_passages(limit: int) -> list[tuple[int, str]]:
    return list(iter_passages(limit))


# --------------------------------------------------------------------------
# the evaluation corpus
# --------------------------------------------------------------------------
#
# MS MARCO's dev judgments point at passages scattered through all 8.8 million.
# Take the first 100,000 lines and only 32 of the 6,980 judged queries have
# their answer in the subset — not enough to measure anything with.
#
# So the corpus every retrieval module works on is built deliberately: every
# judged passage, plus a random sample of the rest up to the requested size.
# This is the standard re-ranking pool, and the module pages say so out loud.
# It keeps the scale honest and gives the evaluation something to find.

def load_qrels() -> dict[int, set[int]]:
    """{query id: set of passage ids somebody judged relevant}"""
    out: dict[int, set[int]] = {}
    for line in corpus_file("msmarco/qrels.dev.small.tsv").read_text().splitlines():
        qid, _, pid, _label = line.split("\t")
        out.setdefault(int(qid), set()).add(int(pid))
    return out


def load_queries() -> dict[int, str]:
    out = {}
    for line in corpus_file("msmarco/queries.dev.small.tsv").read_text().splitlines():
        qid, _, text = line.partition("\t")
        out[int(qid)] = text.strip()
    return out


def eval_corpus_pids(n: int, seed: int = 20260728) -> list[int]:
    """Which passage ids the corpus of size n contains, in sorted order."""
    import random

    cache = DATA / "msmarco" / f"eval_pids_{n}.txt"
    if cache.exists():
        return [int(x) for x in cache.read_text().split()]

    judged = sorted({p for pids in load_qrels().values() for p in pids})
    total = count_collection_lines()
    if n < len(judged):
        raise SystemExit(f"n={n} is smaller than the {len(judged):,} judged "
                         f"passages — use --scale small or larger")

    rng = random.Random(seed)
    judged_set = set(judged)
    fill: set[int] = set()
    need = n - len(judged)
    while len(fill) < need:
        candidate = rng.randrange(total)
        if candidate not in judged_set:
            fill.add(candidate)
    pids = sorted(judged_set | fill)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("\n".join(str(p) for p in pids) + "\n")
    return pids


def count_collection_lines() -> int:
    manifest = DATA / "msmarco" / "manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text())["passages"]
    path = corpus_file("msmarco/collection.tsv")
    n = 0
    with path.open("rb") as f:
        while chunk := f.read(1 << 22):
            n += chunk.count(b"\n")
    return n


def eval_corpus(n: int, *, quiet: bool = False) -> list[tuple[int, str]]:
    """[(passage id, text)] — every judged passage, plus a random sample."""
    wanted = set(eval_corpus_pids(n))
    cache = DATA / "msmarco" / f"eval_corpus_{n}.tsv"
    if cache.exists():
        out = []
        with cache.open(encoding="utf-8") as f:
            for line in f:
                pid, _, text = line.partition("\t")
                out.append((int(pid), text.rstrip("\n")))
        return out

    if not quiet:
        print(f"  building the {n:,}-passage evaluation corpus "
              f"(one pass over collection.tsv)")
    out = []
    path = corpus_file("msmarco/collection.tsv")
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i in wanted:
                pid, _, text = line.partition("\t")
                out.append((int(pid), text.rstrip("\n")))
    with cache.open("w", encoding="utf-8") as f:
        for pid, text in out:
            f.write(f"{pid}\t{text}\n")
    return out


def iter_eval_corpus(n: int):
    """Stream (pid, text) from the evaluation corpus, one line at a time.

    The list-returning `eval_corpus` is convenient and holds the whole corpus
    in memory. Module 9 is about the point where you cannot do that, so it
    uses this instead. Requires the cache to exist — call eval_corpus(n) once
    first, or run data/fetch.py.
    """
    cache = DATA / "msmarco" / f"eval_corpus_{n}.tsv"
    if not cache.exists():
        eval_corpus(n, quiet=True)
    with cache.open(encoding="utf-8") as f:
        for line in f:
            pid, _, text = line.partition("\t")
            yield int(pid), text.rstrip("\n")


def usable_queries(pids: set[int]) -> dict[int, set[int]]:
    """Queries whose judged passages are all present in this corpus."""
    return {qid: rel for qid, rel in load_qrels().items() if rel <= pids}


# --------------------------------------------------------------------------
# embeddings, cached
# --------------------------------------------------------------------------
#
# Modules 7, 8, 12 and 15 all need the same vectors. Embedding a corpus is the
# slowest step in the whole site, so it happens once and is kept on disk. The
# cache is plain .npy — module 3's floats, written down.

VECTOR_DIR = DATA / "vectors"
DEFAULT_MODEL = "all-MiniLM-L6-v2"


def vector_cache_path(n: int, model_name: str = DEFAULT_MODEL) -> Path:
    return VECTOR_DIR / f"{model_name.replace('/', '_')}-eval-{n}.npy"


def embed_corpus(n: int, model_name: str = DEFAULT_MODEL, *,
                 batch_size: int = 256, quiet: bool = False):
    """Return an (n, dims) float32 array, row i being eval_corpus(n)[i].

    Cached. The first call for a given size pays the whole cost; every call
    after it is a file read.
    """
    import numpy as np

    path = vector_cache_path(n, model_name)
    if path.exists():
        vecs = np.load(path)
        if len(vecs) == n:
            if not quiet:
                print(f"  vectors: cached {path.name} "
                      f"({len(vecs):,} x {vecs.shape[1]})")
            return vecs

    from sentence_transformers import SentenceTransformer
    if not quiet:
        print(f"  vectors: embedding {n:,} passages "
              f"(cached afterwards at {path.name})")
    texts = [t for _, t in eval_corpus(n, quiet=quiet)]
    model = SentenceTransformer(model_name)
    vecs = model.encode(texts, batch_size=batch_size,
                        show_progress_bar=not quiet).astype("float32")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, vecs)
    return vecs


def embed_queries(texts: list[str], model_name: str = DEFAULT_MODEL,
                  *, quiet: bool = True):
    from sentence_transformers import SentenceTransformer
    import numpy as np
    model = SentenceTransformer(model_name)
    return model.encode(texts, batch_size=128,
                        show_progress_bar=not quiet).astype("float32")


def normalized(vecs):
    """Unit-length vectors, so a dot product IS the cosine similarity.

    Module 6 computed cosine the long way. Once every vector has length 1 the
    two divisions are always by 1, so the dot product alone is the answer —
    which is why every vector database stores normalised vectors.
    """
    import numpy as np
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vecs / norms).astype("float32")
