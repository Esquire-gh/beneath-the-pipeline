#!/usr/bin/env python3
"""Generate module 15's evaluation document set.

Module 15 asks how much the choice of PDF extractor changes retrieval quality.
Answering that needs documents whose true text is known — otherwise "the
extraction is wrong" has nothing to be wrong against.

So these documents are written here, then drawn in four different layouts, and
half of them are then printed to images. The ground truth is what was written;
the input to the pipeline is only ever the PDF.

    python data/make_eval_docs.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "eval_docs"

# Twenty subjects, each with vocabulary that appears in no other document, so
# a query built from one document cannot accidentally match another.
TOPICS = [
    ("thermal-throttling", "Thermal Throttling in Sustained Index Builds",
     "sustained index construction raises die temperature until the scheduler "
     "reduces clock frequency", "throttling", "die temperature", "clock frequency"),
    ("bloom-filters", "Bloom Filters Ahead of Posting Lists",
     "a probabilistic membership structure answers 'definitely absent' cheaply "
     "and 'possibly present' with a tunable false positive rate",
     "bloom filter", "false positive rate", "membership"),
    ("write-barriers", "Write Barriers and Durability Claims",
     "a barrier instruction forces pending writes to reach stable storage "
     "before later writes are allowed to proceed",
     "write barrier", "durability", "stable storage"),
    ("cache-lines", "Cache Line Sharing Between Posting Cursors",
     "two cursors writing to addresses inside the same cache line force the "
     "hardware to pass ownership back and forth",
     "cache line", "ownership", "false sharing"),
    ("zone-maps", "Zone Maps for Columnar Range Pruning",
     "a zone map stores the minimum and maximum value in each block so a range "
     "predicate can skip blocks without reading them",
     "zone map", "range predicate", "columnar"),
    ("tombstones", "Tombstone Accumulation in Append-Only Stores",
     "a deletion recorded as a marker rather than a removal accumulates until "
     "compaction reclaims the space",
     "tombstone", "compaction", "append-only"),
    ("quantisation", "Product Quantisation of Dense Vectors",
     "splitting a vector into subspaces and replacing each with a centroid "
     "index trades recall for a large reduction in memory",
     "product quantisation", "centroid", "subspace"),
    ("shingling", "Shingling for Near-Duplicate Detection",
     "overlapping token windows hashed into a sketch let two documents be "
     "compared for near-duplication without comparing their text",
     "shingling", "sketch", "near-duplicate"),
    ("backpressure", "Backpressure in Ingestion Queues",
     "when consumers fall behind, an ingestion queue must either drop work, "
     "grow without bound, or refuse new writes",
     "backpressure", "ingestion queue", "consumer lag"),
    ("checksums", "Checksums Over Index Segments",
     "a checksum recorded beside each segment turns silent corruption into a "
     "loud failure at read time",
     "checksum", "silent corruption", "segment"),
    ("term-dictionaries", "Term Dictionary Layout and Prefix Compression",
     "storing only the differing suffix of each term against its predecessor "
     "shrinks a dictionary that is mostly shared prefixes",
     "term dictionary", "prefix compression", "suffix"),
    ("readahead", "Readahead Heuristics for Sequential Scans",
     "the operating system predicts sequential access and fetches blocks "
     "before they are requested, which helps scans and hurts random reads",
     "readahead", "sequential scan", "prediction"),
    ("shard-routing", "Shard Routing Without a Coordinator",
     "hashing a document key to a shard removes the need for a lookup, and "
     "removes the ability to move one document",
     "shard routing", "hashing", "coordinator"),
    ("negative-sampling", "Negative Sampling for Retrieval Training",
     "which documents are shown to a model as wrong answers determines what "
     "the model learns to distinguish",
     "negative sampling", "hard negatives", "training"),
    ("clock-skew", "Clock Skew and Ordering of Index Updates",
     "two machines disagreeing about the time cannot agree about which update "
     "happened last without an external ordering",
     "clock skew", "ordering", "external ordering"),
    ("mmap-tradeoffs", "Memory Mapping an Index File",
     "mapping a file into the address space moves paging decisions to the "
     "kernel and makes latency spikes invisible to the profiler",
     "memory mapping", "paging", "latency spike"),
    ("field-boosting", "Field Boosting and Score Calibration",
     "multiplying a field's contribution changes the ranking but also breaks "
     "any calibration between the score and a probability",
     "field boosting", "calibration", "contribution"),
    ("stop-list", "Stop Lists Against Inverse Document Frequency",
     "a fixed stop list and a rarity weight solve overlapping problems, and "
     "using both discards information twice",
     "stop list", "rarity weight", "overlapping"),
    ("snapshot-isolation", "Snapshot Isolation for Long-Running Queries",
     "a query that runs for minutes must see one consistent version of the "
     "index while ingestion continues around it",
     "snapshot isolation", "consistent version", "long-running"),
    ("cold-start", "Cold Start After a Segment Merge",
     "a freshly merged segment has none of its pages resident, so the first "
     "queries after a merge are the slowest ones",
     "cold start", "resident pages", "freshly merged"),
]

FILLER = [
    "The measurement matters more than the argument, because an argument that "
    "predicts the wrong number is simply wrong.",
    "Every structure described here moves work from one moment to another; "
    "none of them makes work disappear.",
    "The cost shows up in three places: time paid once, memory paid "
    "continuously, and correctness paid on every change.",
    "A system that cannot be measured cannot be tuned, and a system tuned "
    "without measurement is tuned by anecdote.",
]


def build_text(topic) -> tuple[str, list[str], list[str]]:
    key, title, thesis, *terms = topic
    rng = random.Random(hash(key) & 0xFFFF)
    paras = [
        f"{title}. {thesis.capitalize()}. This document is part of the "
        f"evaluation set for module 15 and its contents are known exactly.",
        f"The mechanism is direct. When {terms[0]} is in play, the system must "
        f"decide what to do about {terms[1]}, and that decision is visible in "
        f"the measurements rather than in the source. {rng.choice(FILLER)}",
        f"Consider {terms[2]}. Practitioners reach for it when the simple "
        f"approach stops holding, and the reason it works is the same reason "
        f"it costs something: {thesis}.",
        f"In summary, {terms[0]} and {terms[1]} are two views of one decision. "
        f"{rng.choice(FILLER)} The remainder of this page is filler so that "
        f"the document has a realistic length and a realistic layout.",
    ]
    # three queries per document, each using vocabulary unique to it
    queries = [
        f"what is {terms[0]}",
        f"how does {terms[1]} affect the system",
        f"explain {terms[2]}",
    ]
    return "\n\n".join(paras), queries, list(terms)


def numbers_table(seed: int):
    rng = random.Random(seed)
    rows = [("stage", "documents", "index MB", "build s", "p50 ms")]
    n = rng.randrange(1000, 9000)
    for i in range(6):
        rows.append((f"stage {i + 1}", f"{n:,}", f"{n / 900:.1f}",
                     f"{n / 7000:.2f}", f"{0.3 + i * 0.17:.2f}"))
        n *= 2
    return rows


def render(path: Path, title: str, text: str, layout: str, seed: int) -> None:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                    Paragraph, SimpleDocTemplate, Spacer,
                                    FrameBreak, Table, TableStyle)
    from reportlab.lib import colors
    import sys
    sys.path.insert(0, str(HERE))
    from make_hard_pdfs import _styles

    title_s, head_s, body_s = _styles()
    paras = text.split("\n\n")

    def table_flowable(grid: bool):
        t = Table(numbers_table(seed), hAlign="LEFT")
        style = [("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                 ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
                 ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                 ("ALIGN", (1, 0), (-1, -1), "RIGHT")]
        if grid:
            style.append(("GRID", (0, 0), (-1, -1), 0.5, colors.black))
        else:
            style += [("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
                      ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                      ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.black)]
        t.setStyle(TableStyle(style))
        return t

    if layout == "two_column":
        w, h = LETTER
        m, gut = 0.85 * inch, 0.3 * inch
        col_w = (w - 2 * m - gut) / 2
        doc = BaseDocTemplate(str(path), pagesize=LETTER, title=title,
                              leftMargin=m, rightMargin=m,
                              topMargin=m, bottomMargin=m)
        header = Frame(m, h - m - 0.9 * inch, w - 2 * m, 0.9 * inch, id="h",
                       leftPadding=0, rightPadding=0)
        left = Frame(m, m, col_w, h - 2 * m - 0.9 * inch, id="L",
                     leftPadding=0, rightPadding=0)
        right = Frame(m + col_w + gut, m, col_w, h - 2 * m - 0.9 * inch, id="R",
                      leftPadding=0, rightPadding=0)
        doc.addPageTemplates([PageTemplate(id="two", frames=[header, left, right])])
        flow = [Paragraph(title, title_s), FrameBreak()]
        flow += [Paragraph(p, body_s) for p in paras[:2]]
        flow.append(FrameBreak())
        flow += [Paragraph(p, body_s) for p in paras[2:]]
        doc.build(flow)
        return

    doc = SimpleDocTemplate(str(path), pagesize=LETTER, title=title,
                            leftMargin=1.0 * inch, rightMargin=1.0 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch)
    flow = [Paragraph(title, title_s)]
    for i, p in enumerate(paras):
        flow.append(Paragraph(p, body_s))
        if layout in ("table_ruled", "table_plain") and i == 1:
            flow += [Spacer(1, 6),
                     Paragraph("Measured stages", head_s),
                     table_flowable(grid=(layout == "table_ruled")),
                     Spacer(1, 8)]
    doc.build(flow)


def scan(source: Path, dest: Path, dpi: int = 150) -> None:
    import fitz
    src = fitz.open(source)
    out = fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi)
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, stream=pix.tobytes("png"))
    out.save(dest)
    out.close()
    src.close()


LAYOUTS = ["single_column", "two_column", "table_ruled", "table_plain"]


def generate(out_dir: Path = OUT) -> dict:
    pdf_dir = out_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    truth = {"documents": {}, "queries": []}

    for i, topic in enumerate(TOPICS):
        key, title = topic[0], topic[1]
        text, queries, terms = build_text(topic)
        layout = LAYOUTS[i % len(LAYOUTS)]
        scanned = i >= len(TOPICS) // 2          # half the corpus is scanned

        text_pdf = pdf_dir / f"{key}.pdf"
        render(text_pdf, title, text, layout, seed=i)
        if scanned:
            scanned_pdf = pdf_dir / f"{key}-scan.pdf"
            scan(text_pdf, scanned_pdf)
            text_pdf.unlink()                    # only the scan reaches the pipeline
            final = scanned_pdf
        else:
            final = text_pdf

        truth["documents"][key] = {
            "file": final.name,
            "title": title,
            "layout": layout,
            "scanned": scanned,
            "text": text,
            "distinctive_terms": terms,
        }
        for q in queries:
            truth["queries"].append({"query": q, "answer": key,
                                     "scanned": scanned, "layout": layout})

    (out_dir / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    n_scanned = sum(1 for d in truth["documents"].values() if d["scanned"])
    print(f"  {len(truth['documents'])} documents "
          f"({n_scanned} scanned, {len(truth['documents']) - n_scanned} text), "
          f"{len(truth['queries'])} queries")
    print(f"  layouts: " + ", ".join(
        f"{l}={sum(1 for d in truth['documents'].values() if d['layout'] == l)}"
        for l in LAYOUTS))
    return truth


if __name__ == "__main__":
    generate()
