#!/usr/bin/env python3
"""Generate the difficult PDFs that are hard to find on demand.

Downloaded papers and tax forms cover most of the hard cases. Four more have
to be made here, because module 13 needs matched pairs — two documents that
look identical on screen and behave completely differently under a parser —
and you cannot download a matched pair.

Run through data/fetch.py, or directly:

    python data/make_hard_pdfs.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# 1. a clean text PDF, and the same page printed to pictures
# --------------------------------------------------------------------------

ARTICLE_TITLE = "Block Devices and the Cost of Small Reads"

ARTICLE_BODY = [
    "A storage device presents one interface to the software above it: a long "
    "row of numbered blocks, each of a fixed size. A common size is 4096 "
    "bytes. The device will not hand back less than a block, and it will not "
    "write less than a block. Every abstraction above it — files, folders, "
    "databases, indexes — is built out of that one operation.",

    "The consequence shows up immediately in measurement. Reading ten "
    "thousand small files costs far more than reading one file of the same "
    "total size, because each file carries a fixed overhead that has nothing "
    "to do with how many bytes it holds. The overhead is per request, not per "
    "byte, so a workload made of many small requests pays it many times.",

    "Storage engines are largely a response to this fact. They batch writes "
    "so that many logical updates become one physical transfer. They keep "
    "their own bookkeeping instead of using the filesystem's, because the "
    "filesystem's bookkeeping is optimised for a different access pattern. "
    "They arrange records so that a query touches contiguous blocks rather "
    "than scattered ones.",

    "The same reasoning governs index construction. An index is an "
    "arrangement chosen so that a question becomes cheap to answer. The work "
    "does not disappear; it moves from query time to build time, and is paid "
    "for in memory, in build duration, and in the cost of keeping the "
    "arrangement current as data changes.",

    "None of this is visible from the top of the stack. A call that loads a "
    "document returns a string, and the string does not record how many "
    "requests crossed into the operating system to produce it, nor how many "
    "blocks were read and discarded on the way.",
]

TABLE_ROWS = [
    ("strategy", "requests", "bytes moved", "relative cost"),
    ("file at a time", "10,000", "41.2 MB", "14.2"),
    ("line at a time", "4,118", "41.2 MB", "3.2"),
    ("one buffered read", "37", "41.2 MB", "1.0"),
    ("memory mapped", "12", "41.2 MB", "0.9"),
]


def _styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Times-Roman",
                          fontSize=9.5, leading=12.5, alignment=TA_JUSTIFY,
                          spaceAfter=6)
    title = ParagraphStyle("title", parent=ss["Title"], fontName="Times-Bold",
                           fontSize=15, leading=18, spaceAfter=10)
    head = ParagraphStyle("head", parent=ss["Heading2"], fontName="Times-Bold",
                          fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=4)
    return title, head, body


def _table(rows):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    t = Table(rows, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def make_clean_single_column(path: Path) -> None:
    """The easy case. Every parser agrees about this document."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch

    title, head, body = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                            leftMargin=1.1 * inch, rightMargin=1.1 * inch,
                            topMargin=1 * inch, bottomMargin=1 * inch,
                            title=ARTICLE_TITLE)
    flow = [Paragraph(ARTICLE_TITLE, title),
            Paragraph("R. Ackon &middot; Beneath the Pipeline", body),
            Spacer(1, 8)]
    for i, para in enumerate(ARTICLE_BODY):
        if i == 3:
            flow += [Paragraph("Measured cost of four read strategies", head),
                     _table(TABLE_ROWS), Spacer(1, 8)]
        flow.append(Paragraph(para, body))
    doc.build(flow)


def make_two_column(path: Path) -> None:
    """Same words, two columns, plus a table that spans both.

    A parser reading in coordinate order marches straight across the gutter
    and interleaves the columns. That is module 13c.
    """
    from reportlab.lib.pagesizes import LETTER
    from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                    Paragraph, Spacer, FrameBreak)
    from reportlab.lib.units import inch

    title, head, body = _styles()
    w, h = LETTER
    m, gutter = 0.85 * inch, 0.3 * inch
    col_w = (w - 2 * m - gutter) / 2

    doc = BaseDocTemplate(str(path), pagesize=LETTER, title=ARTICLE_TITLE,
                          leftMargin=m, rightMargin=m, topMargin=m, bottomMargin=m)
    header = Frame(m, h - m - 1.0 * inch, w - 2 * m, 1.0 * inch, id="hdr",
                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    left = Frame(m, m, col_w, h - 2 * m - 1.0 * inch, id="L",
                 leftPadding=0, rightPadding=0)
    right = Frame(m + col_w + gutter, m, col_w, h - 2 * m - 1.0 * inch, id="R",
                  leftPadding=0, rightPadding=0)
    doc.addPageTemplates([PageTemplate(id="two", frames=[header, left, right])])

    flow = [Paragraph(ARTICLE_TITLE, title),
            Paragraph("R. Ackon &middot; Beneath the Pipeline", body),
            FrameBreak()]
    half = len(ARTICLE_BODY) // 2 + 1
    for para in ARTICLE_BODY[:half]:
        flow.append(Paragraph(para, body))
    flow.append(FrameBreak())
    for para in ARTICLE_BODY[half:]:
        flow.append(Paragraph(para, body))
    flow += [Spacer(1, 6),
             Paragraph("Measured cost of four read strategies", head),
             _table(TABLE_ROWS)]
    doc.build(flow)


def make_table_heavy(path: Path) -> None:
    """Numbers in a grid with ruling lines. A table is lines drawn near text.

    Nothing in the file says 'this is a table' — module 5's whole point.
    """
    from reportlab.lib.pagesizes import LETTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch

    title, head, body = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, title="Index cost tables",
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch)
    flow = [Paragraph("Index Cost Tables", title)]
    for block in range(4):
        rows = [("passages", "postings", "index MB", "build s", "p50 ms", "p99 ms")]
        n = 50_000
        for i in range(9):
            rows.append((f"{n:,}", f"{n * 47:,}", f"{n / 5400:.1f}",
                         f"{n / 41000:.2f}", f"{0.4 + i * 0.11:.2f}",
                         f"{1.9 + i * 0.63:.2f}"))
            n *= 2
        flow += [Paragraph(f"Table {block + 1}. Scaling run {block + 1}", head),
                 _table(rows), Spacer(1, 10)]
    doc.build(flow)


def make_table_heavy_ruled(path: Path) -> None:
    """The same tables, drawn with a full grid.

    Visually this is barely different from make_table_heavy's output — a human
    reads both as tables. A parser that finds tables by looking for ruling
    lines can only see this one. That difference is module 13c.
    """
    from reportlab.lib.pagesizes import LETTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors

    title, head, body = _styles()
    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                            title="Index cost tables, fully ruled",
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch)
    flow = [Paragraph("Index Cost Tables (ruled)", title)]
    for block in range(4):
        rows = [("passages", "postings", "index MB", "build s", "p50 ms", "p99 ms")]
        n = 50_000
        for i in range(9):
            rows.append((f"{n:,}", f"{n * 47:,}", f"{n / 5400:.1f}",
                         f"{n / 41000:.2f}", f"{0.4 + i * 0.11:.2f}",
                         f"{1.9 + i * 0.63:.2f}"))
            n *= 2
        t = Table(rows, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        flow += [Paragraph(f"Table {block + 1}. Scaling run {block + 1}", head),
                 t, Spacer(1, 10)]
    doc.build(flow)


def make_rotated(path: Path) -> None:
    """A landscape table rotated inside a portrait page, plus vertical labels.

    Rotation is where OCR error rates spike and where coordinate-based layout
    heuristics stop meaning anything.
    """
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch

    w, h = LETTER
    c = canvas.Canvas(str(path), pagesize=LETTER)
    c.setTitle("Rotated appendix")

    c.setFont("Times-Bold", 15)
    c.drawString(1 * inch, h - 1 * inch, "Appendix C: Rotated Measurement Table")
    c.setFont("Times-Roman", 9.5)
    c.drawString(1 * inch, h - 1.3 * inch,
                 "The table below is set sideways to fit the page width.")

    c.saveState()
    c.translate(w - 1.0 * inch, 1.2 * inch)
    c.rotate(90)
    c.setFont("Times-Bold", 10)
    c.drawString(0, 0, "posting list decode cost by compression scheme")
    c.setFont("Times-Roman", 9)
    rows = [
        ("scheme", "bytes/posting", "decode ns", "ratio"),
        ("raw int32", "4.00", "0.9", "1.00"),
        ("gap + varbyte", "1.21", "2.4", "3.31"),
        ("gap + simple9", "1.04", "1.7", "3.85"),
        ("gap + pfor", "0.88", "1.3", "4.55"),
    ]
    y = -20
    for r, row in enumerate(rows):
        if r == 0:
            c.setFont("Times-Bold", 9)
        else:
            c.setFont("Times-Roman", 9)
        x = 0
        for cell in row:
            c.drawString(x, y, cell)
            x += 110
        if r == 0:
            c.line(0, y - 4, 430, y - 4)
        y -= 15
    c.line(0, y + 9, 430, y + 9)
    c.restoreState()

    c.saveState()
    c.translate(0.6 * inch, h / 2)
    c.rotate(90)
    c.setFont("Times-Italic", 8)
    c.drawCentredString(0, 0, "confidential draft — do not circulate")
    c.restoreState()

    c.showPage()
    c.save()


def make_scanned(source: Path, dest: Path, dpi: int = 150) -> None:
    """Print a text PDF to pictures and wrap them back into a PDF.

    This is what every office scanner produces, and what module 13a turns on.
    The output looks identical on screen. It contains no text at all.
    """
    import fitz

    src = fitz.open(source)
    out = fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi)
        img_page = out.new_page(width=page.rect.width, height=page.rect.height)
        img_page.insert_image(img_page.rect, stream=pix.tobytes("png"))
    out.save(dest)
    out.close()
    src.close()


def make_noisy_scan(source: Path, dest: Path, dpi: int = 120) -> None:
    """A worse scan: lower resolution, slight rotation, speckle.

    Real scans are not clean renders. This one is what OCR error rates are
    actually made of.
    """
    import io
    import random

    import fitz
    from PIL import Image, ImageFilter

    rng = random.Random(20260728)
    src = fitz.open(source)
    out = fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
        img = img.rotate(rng.uniform(-0.9, 0.9), resample=Image.BICUBIC,
                         fillcolor=255, expand=False)
        img = img.filter(ImageFilter.GaussianBlur(0.4))
        px = img.load()
        w, h = img.size
        for _ in range(int(w * h * 0.004)):
            x, y = rng.randrange(w), rng.randrange(h)
            px[x, y] = rng.choice((0, 0, 40, 210))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_page = out.new_page(width=page.rect.width, height=page.rect.height)
        img_page.insert_image(img_page.rect, stream=buf.getvalue())
    out.save(dest)
    out.close()
    src.close()


# --------------------------------------------------------------------------

def generate_hard_pdfs(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    notes: dict[str, dict] = {}

    def record(name: str, why: str):
        notes[name] = {"origin": "generated", "difficulty": why,
                       "source": "data/make_hard_pdfs.py"}

    clean = out_dir / "gen-clean-1col.pdf"
    make_clean_single_column(clean)
    record(clean.name, "the easy case — single column, real text, one flow")

    two = out_dir / "gen-2col.pdf"
    make_two_column(two)
    record(two.name, "same words in two columns; naive extraction interleaves them")

    tables = out_dir / "gen-tables.pdf"
    make_table_heavy(tables)
    record(tables.name, "four ruled tables; nothing in the bytes says 'table'")

    tables_ruled = out_dir / "gen-tables-ruled.pdf"
    make_table_heavy_ruled(tables_ruled)
    record(tables_ruled.name, "the same tables with a full grid — visually "
                              "near-identical, and the only one a line-based "
                              "table finder can see")

    rot = out_dir / "gen-rotated.pdf"
    make_rotated(rot)
    record(rot.name, "a 90-degree rotated table and a vertical margin note")

    scan = out_dir / "gen-clean-1col-scanned.pdf"
    make_scanned(clean, scan)
    record(scan.name, "gen-clean-1col.pdf printed to images — identical on "
                      "screen, zero extractable text")

    noisy = out_dir / "gen-2col-scanned-noisy.pdf"
    make_noisy_scan(two, noisy)
    record(noisy.name, "gen-2col.pdf scanned badly: 120 dpi, skewed, speckled")

    tables_scan = out_dir / "gen-tables-scanned.pdf"
    make_scanned(tables, tables_scan)
    record(tables_scan.name, "ruled tables as pixels — OCR's worst case")

    return notes


if __name__ == "__main__":
    n = generate_hard_pdfs(HERE / "hard_pdfs")
    print(json.dumps(n, indent=2))
