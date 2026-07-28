"""Hand-rolled inline SVG. No charting library, on purpose.

Every chart is a function that takes the measurements dict — keyed by module
slug — and returns a string of SVG. Registered by name; pages reference them
as {{chart:name}} and build.py substitutes the markup.

The rule the whole site runs on applies here too: these functions read
numbers, they never invent them. A chart whose measurements are missing
raises, and the build stops.
"""
from __future__ import annotations

import math
from html import escape

REGISTRY: dict[str, callable] = {}


def chart(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


class MissingMeasurement(KeyError):
    pass


def dig(M: dict, path: str):
    """Look up 'slug.a.b.c' in the measurements dict, loudly."""
    slug, _, rest = path.partition(".")
    node = M.get(slug)
    if node is None:
        raise MissingMeasurement(
            f"no measurements for module '{slug}' — run its exercise first")
    for part in rest.split("."):
        if not part:
            continue
        if isinstance(node, list):
            node = node[int(part)]
        elif part in node:
            node = node[part]
        else:
            raise MissingMeasurement(
                f"{path}: '{part}' missing. have: {sorted(node)[:14]}")
    return node


# --------------------------------------------------------------------------
# formatting shared with build.py
# --------------------------------------------------------------------------

def fmt_time(s: float) -> str:
    if s < 1e-3:
        return f"{s * 1e6:.0f}µs"
    if s < 1:
        return f"{s * 1e3:.1f}ms"
    if s < 90:
        return f"{s:.2f}s"
    return f"{s / 60:.1f}min"


def fmt_bytes(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def fmt_count(n: float) -> str:
    n = float(n)
    if n >= 1e9:
        return f"{n / 1e9:.1f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}k"
    return f"{n:.0f}"


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------

def _open(w: int, h: int, label: str) -> str:
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" '
            f'preserveAspectRatio="xMinYMin meet" role="img" '
            f'aria-label="{escape(label)}">')


def hbar(rows, *, label, width=560, row_h=26, gutter=132, value_fmt=fmt_time,
         highlight_best=True, lower_is_better=True, unit_note=None):
    """Horizontal bars. rows = [(name, value, kind)] where kind is
    '', 'alt' (magenta) or 'mute' (grey)."""
    if not rows:
        raise MissingMeasurement(f"chart '{label}' got no rows")
    values = [r[1] for r in rows]
    best = min(values) if lower_is_better else max(values)
    top, bottom = 8, 26 if unit_note else 10
    h = top + row_h * len(rows) + bottom
    bar_max = width - gutter - 74

    out = [_open(width, h, label)]
    for i, row in enumerate(rows):
        name, value = row[0], row[1]
        kind = row[2] if len(row) > 2 else ""
        if highlight_best and value == best and not kind:
            kind = ""
        y = top + i * row_h
        w = max(1.5, bar_max * (value / max(values))) if max(values) else 1.5
        cls = ("bar " + kind).strip()
        out.append(f'<text class="lbl" x="0" y="{y + 13}">{escape(str(name))}</text>')
        out.append(f'<rect class="{cls}" x="{gutter}" y="{y + 3}" '
                   f'width="{w:.1f}" height="14"></rect>')
        out.append(f'<text x="{gutter + w + 6:.1f}" y="{y + 14}">'
                   f'{escape(value_fmt(value))}</text>')
    out.append(f'<line class="base" x1="{gutter}" y1="{top}" '
               f'x2="{gutter}" y2="{top + row_h * len(rows)}"></line>')
    if unit_note:
        out.append(f'<text class="axis-title" x="{gutter}" y="{h - 6}">'
                   f'{escape(unit_note)}</text>')
    out.append("</svg>")
    return "".join(out)


def _nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    span = hi - lo
    step = 10 ** math.floor(math.log10(span / n))
    for mult in (1, 2, 2.5, 5, 10):
        if span / (step * mult) <= n:
            step *= mult
            break
    start = math.floor(lo / step) * step
    ticks = []
    v = start
    while v <= hi + step * 0.5:
        if v >= lo - step * 0.001:
            ticks.append(round(v, 10))
        v += step
    return ticks


def xy(series, *, label, x_title, y_title, width=560, height=250,
       x_fmt=str, y_fmt=str, x_log=False, y_log=False, point_labels=None,
       pad_left=54, pad_bottom=40):
    """Line chart. series = [{'name':…, 'points':[(x,y),…], 'kind':''|'alt'}]"""
    pad_top, pad_right = 14, 16
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    xs = [p[0] for s in series for p in s["points"]]
    ys = [p[1] for s in series for p in s["points"]]
    if not xs:
        raise MissingMeasurement(f"chart '{label}' got no points")

    def tx(v):
        lo, hi = (min(xs), max(xs))
        if x_log:
            v, lo, hi = math.log10(max(v, 1e-9)), math.log10(max(lo, 1e-9)), math.log10(max(hi, 1e-9))
        return pad_left + (0 if hi == lo else plot_w * (v - lo) / (hi - lo))

    def ty(v):
        lo, hi = (min(0, min(ys)), max(ys))
        if y_log:
            lo, hi = math.log10(max(min(ys), 1e-9)), math.log10(max(hi, 1e-9))
            v = math.log10(max(v, 1e-9))
        return pad_top + plot_h - (0 if hi == lo else plot_h * (v - lo) / (hi - lo))

    out = [_open(width, height, label)]

    y_lo = min(ys) if y_log else min(0, min(ys))
    for t in (_log_ticks(min(ys), max(ys)) if y_log else _nice_ticks(y_lo, max(ys))):
        y = ty(t)
        if not (pad_top - 1 <= y <= pad_top + plot_h + 1):
            continue
        out.append(f'<line class="grid" x1="{pad_left}" y1="{y:.1f}" '
                   f'x2="{pad_left + plot_w}" y2="{y:.1f}"></line>')
        out.append(f'<text x="{pad_left - 6}" y="{y + 3.5:.1f}" '
                   f'text-anchor="end">{escape(y_fmt(t))}</text>')

    for t in (_log_ticks(min(xs), max(xs)) if x_log else _nice_ticks(min(xs), max(xs))):
        x = tx(t)
        if not (pad_left - 1 <= x <= pad_left + plot_w + 1):
            continue
        out.append(f'<text x="{x:.1f}" y="{pad_top + plot_h + 16}" '
                   f'text-anchor="middle">{escape(x_fmt(t))}</text>')

    out.append(f'<line class="base" x1="{pad_left}" y1="{pad_top + plot_h}" '
               f'x2="{pad_left + plot_w}" y2="{pad_top + plot_h}"></line>')

    for s in series:
        kind = s.get("kind", "")
        pts = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in s["points"])
        out.append(f'<polyline class="line {kind}" points="{pts}"></polyline>')
        for x, y in s["points"]:
            out.append(f'<circle class="dot {kind}" cx="{tx(x):.1f}" '
                       f'cy="{ty(y):.1f}" r="2.6"></circle>')
        if s.get("name"):
            lx, ly = s["points"][-1]
            out.append(f'<text class="lbl" x="{tx(lx) - 4:.1f}" '
                       f'y="{ty(ly) - 9:.1f}" text-anchor="end">'
                       f'{escape(s["name"])}</text>')

    for x, y, text in (point_labels or []):
        out.append(f'<text x="{tx(x):.1f}" y="{ty(y) - 9:.1f}" '
                   f'text-anchor="middle">{escape(text)}</text>')

    out.append(f'<text class="axis-title" x="{pad_left}" y="{height - 6}">'
               f'{escape(x_title)}</text>')
    out.append(f'<text class="axis-title" x="{pad_left}" y="{pad_top - 3}">'
               f'{escape(y_title)}</text>')
    out.append("</svg>")
    return "".join(out)


def _log_ticks(lo, hi):
    lo = max(lo, 1e-9)
    ticks = []
    e = math.floor(math.log10(lo))
    while 10 ** e <= hi * 1.001:
        for m in (1, 3):
            v = m * 10 ** e
            if lo * 0.999 <= v <= hi * 1.001:
                ticks.append(v)
        e += 1
    return ticks or [lo, hi]


def grouped_bars(groups, series_names, *, label, width=560, height=230,
                 value_fmt=lambda v: f"{v:.3f}", y_title=""):
    """groups = [(group_label, [v_series0, v_series1, ...]), ...]"""
    pad_left, pad_right, pad_top, pad_bottom = 46, 12, 22, 46
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    all_v = [v for _, vs in groups for v in vs]
    hi = max(all_v) if all_v else 1
    if hi <= 0:
        hi = 1

    gw = plot_w / max(len(groups), 1)
    bw = min(26, (gw - 12) / max(len(series_names), 1))
    kinds = ["", "alt", "mute", ""]

    out = [_open(width, height, label)]
    for t in _nice_ticks(0, hi):
        y = pad_top + plot_h - plot_h * (t / hi)
        out.append(f'<line class="grid" x1="{pad_left}" y1="{y:.1f}" '
                   f'x2="{pad_left + plot_w}" y2="{y:.1f}"></line>')
        out.append(f'<text x="{pad_left - 6}" y="{y + 3.5:.1f}" '
                   f'text-anchor="end">{escape(value_fmt(t))}</text>')

    for gi, (glabel, values) in enumerate(groups):
        gx = pad_left + gi * gw
        for si, v in enumerate(values):
            h = plot_h * (v / hi)
            x = gx + (gw - bw * len(values)) / 2 + si * bw
            out.append(f'<rect class="bar {kinds[si % len(kinds)]}" x="{x:.1f}" '
                       f'y="{pad_top + plot_h - h:.1f}" width="{bw - 2:.1f}" '
                       f'height="{max(h, 0.8):.1f}"></rect>')
        out.append(f'<text class="lbl" x="{gx + gw / 2:.1f}" '
                   f'y="{pad_top + plot_h + 15}" text-anchor="middle">'
                   f'{escape(glabel)}</text>')

    lx = pad_left
    for si, name in enumerate(series_names):
        out.append(f'<rect class="bar {kinds[si % len(kinds)]}" x="{lx}" '
                   f'y="{height - 12}" width="9" height="9"></rect>')
        out.append(f'<text x="{lx + 13}" y="{height - 4}">{escape(name)}</text>')
        lx += 16 + 7 * len(name)

    if y_title:
        out.append(f'<text class="axis-title" x="{pad_left}" y="{pad_top - 8}">'
                   f'{escape(y_title)}</text>')
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------
# the map — Part 0c. Drawn from modules.py, so it cannot disagree with the
# navigation or with the pages themselves.
# --------------------------------------------------------------------------

@chart("site-map")
def site_map(M: dict) -> str:
    from modules import STAGES, stage_modules, BY_NUM

    code_line = {
        "load":     "loader.load()",
        "parse":    "parse()",
        "chunk":    "split()",
        "embed":    "embed()",
        "index":    "db.add()",
        "retrieve": "retrieve()",
    }

    box_w, box_h, gap = 118, 44, 18
    rail = 104                      # left margin holding the row labels
    left, top = rail + 8, 34
    width = left + len(STAGES) * box_w + (len(STAGES) - 1) * gap + 8
    height = 234

    out = [f'<svg viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="the pipeline, and the modules that build and break each stage">']

    for y, text in ((top + 26, "the pipeline"),
                    (top + box_h + 26, "part ii — you build it"),
                    (top + box_h + 56, "part iii — it breaks")):
        out.append(f'<text class="m-sub" x="{rail}" y="{y}" '
                   f'text-anchor="end">{escape(text)}</text>')

    for i, stage in enumerate(STAGES):
        x = left + i * (box_w + gap)
        info = stage_modules(stage)
        builder, breakers = info["builder"], info["breakers"]
        href = f'modules/{builder.slug}.html' if builder else "#"

        out.append(f'<a href="{href}">')
        out.append(f'<rect class="m-stage" x="{x}" y="{top}" width="{box_w}" '
                   f'height="{box_h}" rx="1"></rect>')
        out.append(f'<text class="m-label" x="{x + box_w / 2}" y="{top + 19}" '
                   f'text-anchor="middle">{stage}</text>')
        out.append(f'<text class="m-sub" x="{x + box_w / 2}" y="{top + 33}" '
                   f'text-anchor="middle">{escape(code_line[stage])}</text>')
        out.append('</a>')

        if builder:
            out.append(f'<line class="m-flow" x1="{x + box_w / 2}" '
                       f'y1="{top + box_h}" x2="{x + box_w / 2}" '
                       f'y2="{top + box_h + 14}"></line>')
            out.append(f'<a href="modules/{builder.slug}.html">'
                       f'<text class="m-mod" x="{x + box_w / 2}" '
                       f'y="{top + box_h + 26}" text-anchor="middle">'
                       f'module {builder.nn}</text></a>')

        if breakers:
            labels = " · ".join(b.nn for b in breakers)
            out.append(f'<line class="m-flow" x1="{x + box_w / 2}" '
                       f'y1="{top + box_h + 32}" x2="{x + box_w / 2}" '
                       f'y2="{top + box_h + 44}"></line>')
            out.append(f'<text class="m-mod iii" x="{x + box_w / 2}" '
                       f'y="{top + box_h + 56}" text-anchor="middle">'
                       f'{escape(labels)}</text>')

        if i < len(STAGES) - 1:
            ax = x + box_w
            out.append(f'<path class="m-flow" d="M{ax} {top + box_h / 2} '
                       f'h{gap - 5}"></path>')
            out.append(f'<path class="m-flow" d="M{ax + gap - 9} '
                       f'{top + box_h / 2 - 3.5} l4 3.5 l-4 3.5"></path>')

    # module 14 hangs a second lane under retrieve(): the structured path
    rx = left + (len(STAGES) - 1) * (box_w + gap)
    ly = top + box_h + 74
    m14 = BY_NUM[14]
    out.append(f'<path class="m-flow" d="M{rx + box_w / 2} {top + box_h + 62} '
               f'V{ly + 12}"></path>')
    out.append(f'<a href="modules/{m14.slug}.html">')
    out.append(f'<rect class="m-stage" x="{rx}" y="{ly + 12}" width="{box_w}" '
               f'height="{box_h - 8}" rx="1" stroke-dasharray="3 2"></rect>')
    out.append(f'<text class="m-label" x="{rx + box_w / 2}" y="{ly + 30}" '
               f'text-anchor="middle">structured</text>')
    out.append(f'<text class="m-sub" x="{rx + box_w / 2}" y="{ly + 42}" '
               f'text-anchor="middle">SELECT SUM(...)</text>')
    out.append('</a>')
    out.append(f'<text class="m-sub" x="{rail}" y="{ly + 34}" '
               f'text-anchor="end">a second lane · module {m14.nn}</text>')

    out.append(f'<text class="m-sub" x="{rail}" y="{height - 8}" '
               f'text-anchor="end">part i · modules 01 · 02 · 03</text>')
    out.append(f'<text class="m-sub" x="{left}" y="{height - 8}">'
               f'sit underneath all of it</text>')
    out.append('</svg>')
    return "".join(out)


# --------------------------------------------------------------------------
# module 4 — load
# --------------------------------------------------------------------------

_LOAD_ORDER = ["file_by_file", "files_large_buffer", "small_buffer", "large_buffer"]
_LOAD_LABEL = {
    "file_by_file":       "10k files, 64KB",
    "files_large_buffer": "10k files, 4MB",
    "small_buffer":       "1 file, 4KB",
    "large_buffer":       "1 file, 4MB",
}


@chart("load-time")
def load_time(M):
    s = dig(M, "04-load.strategies")
    best = min(s[k]["seconds"] for k in s)
    rows = [(_LOAD_LABEL[k], s[k]["seconds"],
             "alt" if s[k]["seconds"] > best * 10 else "")
            for k in _LOAD_ORDER]
    return hbar(rows, label="wall time by read strategy", gutter=118,
                value_fmt=fmt_time,
                unit_note="best of 3, page cache warm — lower is better")


@chart("load-crossings")
def load_crossings(M):
    s = dig(M, "04-load.strategies")
    rows = [(_LOAD_LABEL[k], s[k]["crossings"],
             "alt" if s[k]["crossings"] > 1000 else "")
            for k in _LOAD_ORDER]
    return hbar(rows, label="syscalls by read strategy", gutter=118,
                value_fmt=lambda v: f"{int(v):,}",
                unit_note="open + read + close, counted exactly")


@chart("load-cold-warm")
def load_cold_warm(M):
    warm = dig(M, "04-load.strategies")
    cold = dig(M, "04-load.cold_run.strategies")
    groups = [(_LOAD_LABEL[k], [warm[k]["seconds"] * 1000,
                                cold[k]["seconds"] * 1000])
              for k in _LOAD_ORDER]
    return grouped_bars(groups, ["page cache warm", "page cache bypassed"],
                        label="warm against cold, by strategy",
                        value_fmt=lambda v: f"{v:.0f}",
                        y_title="milliseconds")


# --------------------------------------------------------------------------
# module 5 — parse
# --------------------------------------------------------------------------

_PARSE_LABEL = {
    "gen-clean-1col": "clean, 1 column",
    "gen-2col":       "2 columns",
    "gen-tables":     "ruled tables",
    "acl-2col-01":    "real paper, 2 col",
    "irs-1040":       "real tax form",
}


@chart("parse-agreement")
def parse_agreement(M):
    ex = dig(M, "05-parse.extractions")
    rows = []
    for key, label in _PARSE_LABEL.items():
        if key not in ex:
            continue
        r = ex[key]["char_ratio"]
        rows.append((label, r, "" if r > 0.9 else "alt"))
    return hbar(rows, label="how far two PDF libraries agree, by document",
                gutter=124, value_fmt=lambda v: f"{v:.3f}",
                lower_is_better=False,
                unit_note="character similarity, 1.000 = identical — higher is better")


@chart("parse-words")
def parse_words(M):
    ex = dig(M, "05-parse.extractions")
    groups = []
    for key, label in _PARSE_LABEL.items():
        if key not in ex:
            continue
        groups.append((label, [ex[key]["words_a"], ex[key]["words_b"]]))
    return grouped_bars(groups, ["PyMuPDF", "pdfplumber"],
                        label="words extracted from the same file, by library",
                        value_fmt=lambda v: f"{v:,.0f}",
                        y_title="words extracted", height=250)


# --------------------------------------------------------------------------
# module 6 — chunk & embed
# --------------------------------------------------------------------------

@chart("similarity-pairs")
def similarity_pairs(M):
    s = dig(M, "06-chunk-embed.similarity")
    rows = [
        ("cat / feline",       s["cat_feline"], ""),
        ("cat / negation",     s["cat_contradiction"], "alt"),
        ("cat / unrelated",    s["cat_unrelated"], "mute"),
        ("feline / unrelated", s["feline_unrelated"], "mute"),
    ]
    return hbar(rows, label="cosine similarity between sentence pairs",
                gutter=124, value_fmt=lambda v: f"{v:+.3f}",
                lower_is_better=False,
                unit_note="cosine similarity — the negation scores highest")


@chart("chunk-damage")
def chunk_damage(M):
    c = dig(M, "06-chunk-embed.chunking")
    rows = [
        ("fixed 500/100", c["fixed_broken_words"], "alt"),
        ("sentence bounds", c["sentence_broken_words"], ""),
    ]
    return hbar(rows, label="chunk boundaries landing inside a word",
                gutter=124, row_h=28,
                value_fmt=lambda v: f"{int(v):,}",
                unit_note=f"out of {c['fixed_chunks']:,} and "
                          f"{c['sentence_chunks']:,} chunks — lower is better")


def log_hbar(rows, *, label, width=560, row_h=26, gutter=140, value_fmt=fmt_time,
             unit_note=None):
    """Bars on a log scale, for quantities that differ by a million times.

    A linear bar chart cannot show 600ms next to 23ns — the second bar is a
    fraction of a pixel. The axis note says the scale is logarithmic, because
    a chart that hides that is lying.
    """
    values = [r[1] for r in rows if r[1] > 0]
    if not values:
        raise MissingMeasurement(f"chart '{label}' has no positive values")
    lo, hi = min(values), max(values)
    span = math.log10(hi / lo) if hi > lo else 1.0
    bar_max = width - gutter - 78
    top = 8
    h = top + row_h * len(rows) + (26 if unit_note else 10)

    out = [_open(width, h, label)]
    for i, row in enumerate(rows):
        name, value = row[0], row[1]
        kind = row[2] if len(row) > 2 else ""
        y = top + i * row_h
        frac = (math.log10(value / lo) / span) if value > 0 and span else 0
        w = max(2.0, bar_max * (0.06 + 0.94 * frac))
        out.append(f'<text class="lbl" x="0" y="{y + 13}">{escape(str(name))}</text>')
        out.append(f'<rect class="bar {kind}" x="{gutter}" y="{y + 3}" '
                   f'width="{w:.1f}" height="14"></rect>')
        out.append(f'<text x="{gutter + w + 6:.1f}" y="{y + 14}">'
                   f'{escape(value_fmt(value))}</text>')
    out.append(f'<line class="base" x1="{gutter}" y1="{top}" x2="{gutter}" '
               f'y2="{top + row_h * len(rows)}"></line>')
    if unit_note:
        out.append(f'<text class="axis-title" x="{gutter}" y="{h - 6}">'
                   f'{escape(unit_note)}</text>')
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------
# module 7 — index
# --------------------------------------------------------------------------

@chart("index-scan-vs-lookup")
def index_scan_vs_lookup(M):
    scan = dig(M, "07-index.scan")
    sub = dig(M, "07-index.scan_substring")
    look = dig(M, "07-index.lookup")
    word = "block"
    rows = [
        ("scan, tokenized", scan[word]["seconds"], "alt"),
        ("scan, substring", sub[word]["seconds"], "alt"),
        ("index lookup", look[word]["seconds"], ""),
    ]
    return log_hbar(rows, label="finding one word three ways",
                    unit_note="LOGARITHMIC scale — the bars are not to scale "
                              "with each other")


@chart("index-size")
def index_size(M):
    corpus = dig(M, "07-index.corpus_bytes")
    inv = dig(M, "07-index.inverted.size_bytes")
    vec = dig(M, "07-index.vectors.bytes")
    rows = [
        ("corpus text", corpus, "mute"),
        ("inverted index", inv, ""),
        ("vectors", vec, "alt"),
    ]
    return hbar(rows, label="what each structure costs in memory",
                gutter=126, value_fmt=fmt_bytes, lower_is_better=False,
                unit_note="memory held, for the same 100,000 passages")


def diverging_hbar(rows, *, label, width=560, row_h=26, gutter=200,
                   value_fmt=lambda v: f"{v:+.4f}", unit_note=None):
    """Bars either side of a zero line, for changes that can go both ways."""
    values = [r[1] for r in rows]
    span = max(abs(v) for v in values) or 1.0
    half = (width - gutter - 68) / 2
    zero = gutter + half
    top = 8
    h = top + row_h * len(rows) + (26 if unit_note else 10)

    out = [_open(width, h, label)]
    for i, (name, value) in enumerate([(r[0], r[1]) for r in rows]):
        y = top + i * row_h
        w = max(1.5, half * abs(value) / span)
        x = zero if value >= 0 else zero - w
        cls = "bar" if value >= 0 else "bar alt"
        out.append(f'<text class="lbl" x="0" y="{y + 13}">{escape(str(name))}</text>')
        out.append(f'<rect class="{cls}" x="{x:.1f}" y="{y + 3}" '
                   f'width="{w:.1f}" height="14"></rect>')
        tx = (x + w + 6) if value >= 0 else (x - 6)
        anchor = "start" if value >= 0 else "end"
        out.append(f'<text x="{tx:.1f}" y="{y + 14}" text-anchor="{anchor}">'
                   f'{escape(value_fmt(value))}</text>')
    out.append(f'<line class="base" x1="{zero}" y1="{top}" x2="{zero}" '
               f'y2="{top + row_h * len(rows)}"></line>')
    if unit_note:
        out.append(f'<text class="axis-title" x="0" y="{h - 6}">'
                   f'{escape(unit_note)}</text>')
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------
# module 8 — retrieve
# --------------------------------------------------------------------------

@chart("retrieve-scorers")
def retrieve_scorers(M):
    runs = dig(M, "08-retrieve.runs")
    order = [("term_counts", "term counts", "alt"),
             ("tfidf", "tf-idf", ""),
             ("bm25", "BM25", ""),
             ("dense", "dense vectors", "")]
    rows = [(label, runs[key]["ndcg_at_10"], kind)
            for key, label, kind in order if key in runs]
    return hbar(rows, label="NDCG@10 by scorer", gutter=118,
                value_fmt=lambda v: f"{v:.4f}", lower_is_better=False,
                unit_note="NDCG@10 over 1,000 judged queries — higher is better")


@chart("retrieve-tuning")
def retrieve_tuning(M):
    tuning = dig(M, "08-retrieve.tuning")
    short = {
        "drop_stopwords": "drop stopwords",
        "k1_high": "k1 1.2 → 2.5",
        "b_zero": "b 0.75 → 0",
        "b_one": "b 0.75 → 1",
    }
    rows = [(short.get(k, k), v["delta_ndcg"]) for k, v in tuning.items()]
    rows.sort(key=lambda r: -r[1])
    return diverging_hbar(rows, label="change in NDCG@10 from four plausible tweaks",
                          gutter=150,
                          unit_note="change in NDCG@10 against the BM25 baseline")


@chart("retrieve-latency")
def retrieve_latency(M):
    runs = dig(M, "08-retrieve.runs")
    order = [("bm25", "BM25"), ("dense", "dense vectors"),
             ("tfidf", "tf-idf"), ("term_counts", "term counts")]
    rows = [(label, runs[key]["median_seconds"], "")
            for key, label in order if key in runs]
    return hbar(rows, label="median time per query by scorer", gutter=118,
                unit_note="median seconds per query at 100,000 passages")


# --------------------------------------------------------------------------
# module 9 — the index that doesn't fit
# --------------------------------------------------------------------------

@chart("memory-curve")
def memory_curve(M):
    curve = dig(M, "09-index-that-doesnt-fit.curve")
    sizes = curve["sizes"]
    mem = [(s, r["index_bytes"]) for s, r in zip(sizes, curve["in_memory"])
           if not r.get("failed")]
    build = [(s, r["build_index_bytes"]) for s, r in zip(sizes, curve["spimi"])
             if not r.get("failed")]
    total = [(s, r["index_bytes"]) for s, r in zip(sizes, curve["spimi"])
             if not r.get("failed")]
    return xy([{"name": "all in memory", "points": mem, "kind": "alt"},
               {"name": "SPIMI, merge included", "points": total, "kind": ""},
               {"name": "SPIMI, building blocks", "points": build, "kind": ""}],
              label="peak memory against corpus size",
              x_title="passages indexed", y_title="peak memory held",
              x_fmt=fmt_count, y_fmt=fmt_bytes, x_log=True,
              width=560, height=270, pad_left=62)


@chart("compression-sizes")
def compression_sizes(M):
    c = dig(M, "09-index-that-doesnt-fit.compression")
    rows = [
        ("raw 32-bit ids", c["raw_int32_bytes"], "alt"),
        ("gaps, still 32-bit", c["gaps_int32_bytes"], "alt"),
        ("gaps + varbyte", c["gaps_varbyte_bytes"], ""),
    ]
    return hbar(rows, label="posting list size under three encodings",
                gutter=134, value_fmt=fmt_bytes,
                unit_note=f"{c['postings']:,} postings — lower is better")


# --------------------------------------------------------------------------
# module 10 — ingestion vs query
# --------------------------------------------------------------------------

@chart("fanout-cost")
def fanout_cost(M):
    rows = dig(M, "10-ingestion-vs-query.fanout")
    return xy([{"name": "query time",
                "points": [(r["segments"], r["seconds"] * 1e6) for r in rows]}],
              label="query time against segment count, same corpus",
              x_title="segments the query must consult",
              y_title="microseconds per query",
              x_fmt=lambda v: f"{v:.0f}", y_fmt=lambda v: f"{v:.0f}",
              width=560, height=240)


@chart("fanout-size")
def fanout_size(M):
    rows = dig(M, "10-ingestion-vs-query.fanout")
    return xy([{"name": "index size", "points":
                [(r["segments"], r["index_bytes"]) for r in rows], "kind": "alt"}],
              label="index size against segment count, same corpus",
              x_title="segments", y_title="bytes on disk",
              x_fmt=lambda v: f"{v:.0f}", y_fmt=fmt_bytes,
              width=560, height=240, pad_left=62)


@chart("merge-trade")
def merge_trade(M):
    rows = dig(M, "10-ingestion-vs-query.policies")
    groups = [(r["label"].replace("fan=", "f="),
               [r["query_seconds"] * 1e6, r["rewritten"] / 5000.0])
              for r in rows]
    return grouped_bars(groups,
                        ["query µs", "documents rewritten (thousands × 5)"],
                        label="query cost against ingestion cost, by merge policy",
                        value_fmt=lambda v: f"{v:.0f}",
                        y_title="the two costs, pulling against each other",
                        height=250)


# --------------------------------------------------------------------------
# module 11 — retrieval at scale
# --------------------------------------------------------------------------

_STRAT_ORDER = ["taat", "daat", "wand_linear", "wand"]
_STRAT_LABEL = {
    "taat": "term at a time",
    "daat": "document at a time",
    "wand_linear": "WAND, no skips",
    "wand": "WAND + skips",
}


@chart("scoring-work")
def scoring_work(M):
    s = dig(M, "11-retrieval-at-scale.strategies")
    rows = [(_STRAT_LABEL[k], s[k]["documents_scored_per_query"],
             "alt" if k in ("taat", "daat") else "")
            for k in _STRAT_ORDER if k in s]
    return hbar(rows, label="documents fully scored per query", gutter=124,
                value_fmt=lambda v: f"{v:,.0f}",
                unit_note="documents scored per query — lower is better")


@chart("postings-touched")
def postings_touched(M):
    s = dig(M, "11-retrieval-at-scale.strategies")
    rows = [(_STRAT_LABEL[k], s[k]["postings_touched_per_query"],
             "alt" if k in ("taat", "daat") else "")
            for k in _STRAT_ORDER if k in s]
    return hbar(rows, label="postings touched per query", gutter=124,
                value_fmt=lambda v: f"{v:,.0f}",
                unit_note="postings stepped over per query — lower is better")


@chart("latency-tail")
def latency_tail(M):
    tail = dig(M, "11-retrieval-at-scale.tail")
    groups = [(_STRAT_LABEL[k], [tail[k]["median_ms"], tail[k]["p99_ms"]])
              for k in _STRAT_ORDER if k in tail]
    return grouped_bars(groups, ["median", "p99"],
                        label="median against p99 latency, by strategy",
                        value_fmt=lambda v: f"{v:.0f}",
                        y_title="milliseconds per query", height=250)


# --------------------------------------------------------------------------
# module 12 — vector search at scale
# --------------------------------------------------------------------------

@chart("recall-latency")
def recall_latency(M):
    sweep = dig(M, "12-vector-search-at-scale.sweep")
    points = [(r["median_seconds"] * 1000, r["recall"]) for r in sweep]
    labels = [(r["median_seconds"] * 1000, r["recall"], f"ef={r['ef']}")
              for r in sweep if r["ef"] in (10, 32, 128, 512)]
    return xy([{"name": "HNSW", "points": points}],
              label="recall against latency as ef_search varies",
              x_title="median milliseconds per query",
              y_title="recall@10 against brute force",
              x_fmt=lambda v: f"{v:.2f}", y_fmt=lambda v: f"{v:.2f}",
              point_labels=labels, width=560, height=270)


@chart("recall-vs-speedup")
def recall_vs_speedup(M):
    sweep = dig(M, "12-vector-search-at-scale.sweep")
    rows = [(f"ef={r['ef']}", r["recall"],
             "" if r["recall"] >= 0.99 else "alt")
            for r in sweep if r["ef"] in (10, 24, 48, 96, 192, 512)]
    return hbar(rows, label="recall@10 by ef_search", gutter=90,
                value_fmt=lambda v: f"{v:.4f}", lower_is_better=False,
                unit_note="recall@10 against exact brute-force search")


@chart("filter-cliff")
def filter_cliff(M):
    rows = dig(M, "12-vector-search-at-scale.filter.post_filter")
    subset = dig(M, "12-vector-search-at-scale.filter.brute_force_subset")
    bars = [(f"graph, ef={r['ef']}", r["recall"], "alt") for r in rows]
    bars.append(("scan the matches", subset["recall"], ""))
    return hbar(bars, label="recall after filtering to 1% of documents",
                gutter=124, value_fmt=lambda v: f"{v:.3f}",
                lower_is_better=False,
                unit_note="recall@10 within the filtered subset — higher is better")


@chart("filter-cost")
def filter_cost(M):
    rows = dig(M, "12-vector-search-at-scale.filter.post_filter")
    subset = dig(M, "12-vector-search-at-scale.filter.brute_force_subset")
    bars = [(f"graph, ef={r['ef']}", r["median_seconds"], "alt") for r in rows]
    bars.append(("scan the matches", subset["median_seconds"], ""))
    return log_hbar(bars, label="time per filtered query", gutter=124,
                    unit_note="LOGARITHMIC — time per query, lower is better")


# --------------------------------------------------------------------------
# module 13 — why parsing is hard
# --------------------------------------------------------------------------

@chart("ocr-error-rates")
def ocr_error_rates(M):
    ocr = dig(M, "13-why-parsing-is-hard.ocr")
    order = ["clean_scan", "table_scan", "noisy_scan"]
    rows = [(ocr[k]["description"], ocr[k]["cer"],
             "alt" if ocr[k]["cer"] > 0.01 else "")
            for k in order if k in ocr]
    return hbar(rows, label="character error rate by document quality",
                gutter=190, value_fmt=lambda v: f"{v:.4f}",
                unit_note="character error rate — same OCR engine, same settings")


@chart("ocr-ladder")
def ocr_ladder(M):
    pair = dig(M, "13-why-parsing-is-hard.matched_pairs.clean_1col")
    ocr = dig(M, "13-why-parsing-is-hard.ocr")
    rows = [
        ("text PDF, extract", pair["text_chars"], ""),
        ("scanned, extract", pair["image_chars"], "alt"),
        ("scanned, then OCR", ocr["clean_scan"]["got_chars"], ""),
    ]
    return hbar(rows, label="characters recovered from the same page",
                gutter=150, value_fmt=lambda v: f"{int(v):,}",
                lower_is_better=False,
                unit_note="characters recovered — the middle bar is zero")


@chart("ocr-gpu")
def ocr_gpu(M):
    ml = dig(M, "13-why-parsing-is-hard.ml")
    devices = ml.get("trocr", {}).get("devices", {})
    rows = [("Tesseract, one page", ml["tesseract"]["seconds_per_page"], "")]
    for dev, v in devices.items():
        rows.append((f"TrOCR per line, {dev}",
                     v["seconds_per_line"], "alt" if dev == "cpu" else ""))
    return hbar(rows, label="time per unit of work, by engine and device",
                gutter=160, unit_note="lower is better — note the units differ "
                                      "between rows")


@chart("table-detection")
def table_detection(M):
    t = dig(M, "13-why-parsing-is-hard.tables")
    groups = []
    for key, label in (("rules_only", "horizontal rules only"),
                       ("full_grid", "full grid")):
        if key in t:
            groups.append((label, [t[key]["horizontal_lines"],
                                   t[key]["vertical_lines"],
                                   t[key]["rows_found"]]))
    return grouped_bars(groups, ["horizontal rules", "vertical rules",
                                 "table rows found"],
                        label="ruling lines against tables detected",
                        value_fmt=lambda v: f"{v:.0f}",
                        y_title="count", height=240)


# --------------------------------------------------------------------------
# module 14 — what vectors can't answer
# --------------------------------------------------------------------------

@chart("two-query-sets")
def two_query_sets(M):
    d = dig(M, "14-what-vectors-cant-answer.descriptive")
    a = dig(M, "14-what-vectors-cant-answer.aggregate")
    groups = [
        ("descriptive", [d["retrieval"]["accuracy_at_k"], d["sql"]["accuracy_at_k"]]),
        ("aggregate", [0.0, a["sql"]["accuracy"]]),
    ]
    return grouped_bars(groups, ["similarity search", "SQL over records"],
                        label="accuracy by question type and store",
                        value_fmt=lambda v: f"{v:.1f}",
                        y_title="fraction answered correctly", height=240)


@chart("evidence-gap")
def evidence_gap(M):
    a = dig(M, "14-what-vectors-cant-answer.aggregate")
    rows = [
        ("documents needed", a["retrieval"]["median_documents_needed"], "alt"),
        ("documents retrieved", dig(M, "14-what-vectors-cant-answer.k"), ""),
    ]
    return hbar(rows, label="documents a median aggregate question needs",
                gutter=150, row_h=28, value_fmt=lambda v: f"{int(v)}",
                lower_is_better=False,
                unit_note="documents, for the median aggregate question")


@chart("router-result")
def router_result(M):
    e = dig(M, "14-what-vectors-cant-answer.end_to_end")
    rows = [
        ("similarity only", e["retrieval_only"], "alt"),
        ("SQL only", e["sql_only"], "alt"),
        ("routed", e["routed"], ""),
    ]
    return hbar(rows, label="all questions, three systems", gutter=130,
                value_fmt=lambda v: f"{v:.1%}", lower_is_better=False,
                unit_note="fraction of all questions answered correctly")


# --------------------------------------------------------------------------
# module 15 — rebuilt and measured
# --------------------------------------------------------------------------

_STAGE_ORDER = ["bm25", "dense", "fused", "reranked"]
_STAGE_LABEL = {"bm25": "BM25", "dense": "dense", "fused": "fused",
                "reranked": "fused + rerank"}


@chart("staged-gains")
def staged_gains(M):
    s = dig(M, "15-rebuilt-and-measured.stages")
    best = max(s[k]["ndcg_at_10"] for k in s)
    rows = [(_STAGE_LABEL[k], s[k]["ndcg_at_10"],
             "" if s[k]["ndcg_at_10"] == best else "")
            for k in _STAGE_ORDER if k in s]
    return hbar(rows, label="NDCG@10 by pipeline stage", gutter=120,
                value_fmt=lambda v: f"{v:.4f}", lower_is_better=False,
                unit_note="NDCG@10 on MS MARCO — note that fusion is not a gain")


@chart("staged-latency")
def staged_latency(M):
    s = dig(M, "15-rebuilt-and-measured.stages")
    rows = [(_STAGE_LABEL[k], s[k]["median_seconds"],
             "alt" if k == "reranked" else "")
            for k in _STAGE_ORDER if k in s]
    return hbar(rows, label="median query time by pipeline stage", gutter=120,
                unit_note="median seconds per query")


@chart("extraction-spread")
def extraction_spread(M):
    ex = dig(M, "15-rebuilt-and-measured.extractions")
    order = [("pymupdf", "PyMuPDF"), ("pdfplumber", "pdfplumber"),
             ("ocr_fallback", "PyMuPDF + OCR")]
    groups = []
    for key, label in order:
        if key not in ex:
            continue
        st = ex[key]["stages"]
        groups.append((label, [st[s]["ndcg_at_10"] for s in _STAGE_ORDER]))
    return grouped_bars(groups, ["BM25", "dense", "fused", "reranked"],
                        label="NDCG by extractor and retrieval architecture",
                        value_fmt=lambda v: f"{v:.1f}",
                        y_title="NDCG@10 — four architectures per extractor",
                        height=260)


@chart("the-finding")
def the_finding(M):
    sp = dig(M, "15-rebuilt-and-measured.spread")
    rows = [
        ("choice of extractor", sp["across_extractors"], "alt"),
        ("choice of architecture", sp["across_architectures_within_best_extractor"], ""),
    ]
    return hbar(rows, label="how much each choice moves retrieval quality",
                gutter=170, row_h=30, value_fmt=lambda v: f"{v:.4f}",
                lower_is_better=False,
                unit_note="NDCG@10 between the best and worst option in each case")


@chart("scanned-vs-text")
def scanned_vs_text(M):
    ex = dig(M, "15-rebuilt-and-measured.extractions")
    groups = []
    for key, label in (("pymupdf", "PyMuPDF"), ("pdfplumber", "pdfplumber"),
                       ("ocr_fallback", "PyMuPDF + OCR")):
        if key in ex:
            st = ex[key]["stages"]["reranked"]
            groups.append((label, [st["text_accuracy"], st["scanned_accuracy"]]))
    return grouped_bars(groups, ["text documents", "scanned documents"],
                        label="accuracy by document kind and extractor",
                        value_fmt=lambda v: f"{v:.1f}",
                        y_title="the right document in the top ten", height=240)
