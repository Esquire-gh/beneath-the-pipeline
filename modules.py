"""The site's spine: what the modules are, and which pipeline stage each one
touches.

Everything structural — the strip, the table of contents, the map, the
previous/next links — is computed from this one list, so the navigation can't
drift out of step with the pages.
"""
from __future__ import annotations

# The six stages of the Part 0 pipeline, in pipeline order. The strip is these.
STAGES = ["load", "parse", "chunk", "embed", "index", "retrieve"]

PART_TITLES = {
    0: "Part 0 · the frame",
    1: "Part I · the floor",
    2: "Part II · the pipeline, one line at a time",
    3: "Part III · when reality arrives",
}


class Module:
    def __init__(self, num, slug, title, part, desc, *, builds=(), stresses=(),
                 lane2=False, kind="build", deps=()):
        self.num = num                # 0 for the index page
        self.slug = slug              # also the exercises/ directory name
        self.title = title
        self.part = part
        self.desc = desc              # one line, for the table of contents
        self.builds = list(builds)    # Part II: stages this module constructs
        self.stresses = list(stresses)  # Part III: stages this module breaks
        self.lane2 = lane2            # module 14 draws the structured lane
        self.kind = kind              # "build" | "investigate" | "frame"
        self.deps = list(deps)        # pip packages this module's exercise needs

    @property
    def nn(self) -> str:
        return f"{self.num:02d}"

    @property
    def href(self) -> str:
        return "../index.html" if self.num == 0 else f"{self.slug}.html"

    @property
    def href_from_root(self) -> str:
        return "index.html" if self.num == 0 else f"modules/{self.slug}.html"


MODULES = [
    Module(0, "00-pipeline", "The pipeline, working", 0,
           "Thirty lines that work, and the list of everything they assume.",
           kind="frame", deps=("pymupdf", "sentence-transformers", "chromadb")),

    # ---- Part I -----------------------------------------------------------
    Module(1, "01-what-is-a-file", "What is a file, actually?", 1,
           "A file of three characters occupies 4096 bytes. Where did the rest go?",
           kind="investigate"),
    Module(2, "02-bytes-text", "How text becomes bytes", 1,
           "Eight bytes. Word, number, colour, or four notes of audio?",
           kind="investigate"),
    Module(3, "03-bytes-numbers", "How numbers become bytes", 1,
           "0.1 + 0.2 is not 0.3, and one integer takes 1, 4, or 8 bytes.",
           deps=()),

    # ---- Part II ----------------------------------------------------------
    Module(4, "04-load", "Load — what reading a file costs", 2,
           "Same bytes, ten thousand files instead of one, wildly different cost.",
           builds=["load"]),
    Module(5, "05-parse", "Parse — how a PDF becomes text", 2,
           "Two libraries, one PDF, two different texts.",
           builds=["parse"], deps=("pymupdf", "pdfplumber")),
    Module(6, "06-chunk-embed", "Chunk & Embed — how text becomes vectors", 2,
           "Two sentences share no words, and the pipeline calls them similar.",
           builds=["chunk", "embed"], deps=("sentence-transformers", "numpy")),
    Module(7, "07-index", "Index — how search gets fast", 2,
           "Seconds with a loop, microseconds with an index. What was precomputed?",
           builds=["index"], deps=("numpy",)),
    Module(8, "08-retrieve", "Retrieve — how results get ranked", 2,
           "Four thousand passages match. The pipeline returns four. Which four?",
           builds=["retrieve"], deps=("numpy",)),

    # ---- Part III ---------------------------------------------------------
    Module(9, "09-index-that-doesnt-fit", "When the index doesn't fit in memory", 3,
           "Module 7's index at 1M passages, and the memory curve heading off the page.",
           stresses=["load", "index"], deps=("numpy",)),
    Module(10, "10-ingestion-vs-query", "Keeping the index fresh as documents arrive", 3,
           "New documents arrive. Rebuilding takes hours; appending is worse.",
           stresses=["index"]),
    Module(11, "11-retrieval-at-scale", "How ranking stays fast at scale", 3,
           "Most documents you score cannot possibly reach the top ten.",
           stresses=["retrieve"], deps=("numpy",)),
    Module(12, "12-vector-search-at-scale", "How vector search scales", 3,
           "HNSW is a hundred times faster and quietly stops being right.",
           stresses=["embed", "index"], deps=("hnswlib", "numpy", "sentence-transformers")),
    Module(13, "13-why-parsing-is-hard", "Why parsing is a hard problem", 3,
           "Two identical-looking PDFs. One parses perfectly, one returns nothing.",
           stresses=["parse"], deps=("pymupdf", "pdfplumber", "pytesseract")),
    Module(14, "14-what-vectors-cant-answer", "What vectors can't answer", 3,
           "Every number is in the corpus. The total is still not attempted.",
           stresses=["retrieve"], lane2=True, deps=("pymupdf", "sentence-transformers")),
    Module(15, "15-rebuilt-and-measured", "The pipeline, rebuilt and measured", 3,
           "Your own parts, fused and reranked, then run on documents that fight back.",
           stresses=STAGES, lane2=True,
           deps=("pymupdf", "pdfplumber", "sentence-transformers", "hnswlib", "numpy")),
]

BY_NUM = {m.num: m for m in MODULES}
BY_SLUG = {m.slug: m for m in MODULES}


def stage_modules(stage: str) -> dict:
    """Which module builds this stage, and which ones later break it."""
    builder = next((m for m in MODULES if stage in m.builds), None)
    breakers = [m for m in MODULES if stage in m.stresses and m.num != 15]
    return {"builder": builder, "breakers": breakers}
