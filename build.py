#!/usr/bin/env python3
"""Assemble the site.

Authoring-time only. Readers never run this — the HTML committed under site/
is complete and opens from file:// with no server and no build step.

What it does:

  1. reads page bodies from content/
  2. substitutes {{ }} tokens from exercises/NN-slug/measurements.json
  3. wraps each body in the shared shell — masthead, sidebar, nav
  4. writes site/index.html, site/modules/*.html, site/reading-list.html

The point of step 2: no number on this site is typed by hand. If a page wants
to say how much slower one read strategy was, it names a measurement, and the
build fails if that measurement was never taken.

    python build.py            # build everything
    python build.py --check    # report missing measurements, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import charts                                        # noqa: E402
from charts import MissingMeasurement, dig           # noqa: E402
from modules import MODULES, BY_NUM, PART_TITLES  # noqa: E402

CONTENT = REPO / "content"
SITE = REPO / "site"
EXERCISES = REPO / "exercises"

TOKEN = re.compile(r"\{\{\s*(.+?)\s*\}\}", re.S)


# --------------------------------------------------------------------------
# measurements
# --------------------------------------------------------------------------

def load_measurements() -> dict:
    out = {}
    for path in sorted(EXERCISES.glob("*/measurements.json")):
        try:
            out[path.parent.name] = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            sys.exit(f"{path}: {e}")
    return out


def machine_specs(M: dict) -> dict:
    """The machine every number on this site was produced on.

    Taken from the measurement files themselves rather than probed at build
    time, so the specs describe the machine that ran the code.
    """
    for slug in sorted(M):
        spec = M[slug].get("_machine")
        if spec:
            return spec
    from exercises.common import machine
    return machine()


# --------------------------------------------------------------------------
# token substitution
# --------------------------------------------------------------------------

def fmt(value, spec: str) -> str:
    if spec in ("", "raw"):
        return escape(str(value))
    if spec == "int":
        return f"{round(float(value)):,}"
    if spec == "count":
        return charts.fmt_count(value)
    if spec == "time":
        return charts.fmt_time(float(value))
    if spec == "bytes":
        return charts.fmt_bytes(float(value))
    if spec == "x":                       # a ratio: 14.2×
        return f"{float(value):.1f}&times;"
    if spec == "x0":
        return f"{round(float(value)):,}&times;"
    if spec == "pct":
        return f"{float(value) * 100:.1f}%"
    if spec == "pct0":
        return f"{float(value) * 100:.0f}%"
    if spec == "money":
        return f"${float(value):,.2f}"
    if re.fullmatch(r"\d+f", spec):                # 1f, 2f, 3f …
        return f"{float(value):.{int(spec[:-1])}f}"
    if spec == "json":
        return escape(json.dumps(value))
    raise ValueError(f"unknown format '{spec}'")


PY_KEYWORDS = {
    "and", "as", "assert", "break", "class", "continue", "def", "del", "elif",
    "else", "except", "False", "finally", "for", "from", "global", "if",
    "import", "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass",
    "raise", "return", "True", "try", "while", "with", "yield",
}

PY_TOKEN = re.compile(r"""
      (?P<comment>\#[^\n]*)
    | (?P<string>'''.*?'''|\"\"\".*?\"\"\"|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
    | (?P<def>(?<=\bdef\s)\w+)
    | (?P<name>[A-Za-z_]\w*)
    | (?P<number>\b\d[\w.]*)
    | (?P<other>.)
""", re.X | re.S)


def highlight_python(src: str) -> str:
    """Enough highlighting to read by, and not one colour more."""
    out = []
    for m in PY_TOKEN.finditer(src):
        kind = m.lastgroup
        text = escape(m.group())
        if kind == "comment":
            cls = "c-todo" if "TODO" in m.group() else "c-cm"
            out.append(f'<span class="{cls}">{text}</span>')
        elif kind == "string":
            out.append(f'<span class="c-st">{text}</span>')
        elif kind == "def":
            out.append(f'<span class="c-fn">{text}</span>')
        elif kind == "name" and m.group() in PY_KEYWORDS:
            out.append(f'<span class="c-kw">{text}</span>')
        else:
            out.append(text)
    return "".join(out)


def inline_code(spec: str) -> str:
    """{{code:path#MARK}} — put the real file on the page.

    The site shows code that exists, not code that was retyped into prose.
    """
    path_part, _, mark = spec.partition("#")
    path = REPO / path_part.strip()
    if not path.exists():
        raise MissingMeasurement(f"no such file: {path_part}")
    src = path.read_text()
    if mark:
        lines = src.splitlines()
        try:
            a = next(i for i, l in enumerate(lines) if f"BEGIN {mark}" in l)
            b = next(i for i, l in enumerate(lines) if f"END {mark}" in l)
        except StopIteration:
            raise MissingMeasurement(f"{path_part}: no BEGIN/END {mark} markers")
        src = "\n".join(lines[a + 1:b]).strip("\n")
    body = highlight_python(src) if path.suffix == ".py" else escape(src)
    return f'<div class="code"><pre>{body}</pre></div>'


def hexdump_html(M: dict, path: str, highlight: str = "") -> str:
    """{{hex:slug.path.to.dump | 0-7}} — a real hex dump, from real bytes.

    The dump rows are recorded by the exercise. This only lays them out, so
    the bytes on the page are the bytes on disk.
    """
    rows = dig(M, path)
    lo, hi = -1, -1
    if highlight:
        a, _, b = highlight.partition("-")
        lo, hi = int(a), int(b or a)

    out = []
    for row in rows:
        cells = []
        for i, byte in enumerate(row["hex"]):
            off = row["offset"] + i
            gap = " " if i % 8 == 7 else ""
            if lo <= off <= hi:
                cells.append(f'<span class="hl">{byte}</span> {gap}')
            else:
                cells.append(f"{byte} {gap}")
        pad = "   " * (16 - len(row["hex"]))
        ascii_col = escape(row["ascii"])
        out.append(f'<span class="off">{row["offset"]:08x}</span>  '
                   f'{"".join(cells)}{pad} |{ascii_col}|')
    return '<div class="hex">' + "\n".join(out) + "</div>"


def substitute(text: str, M: dict, *, where: str) -> tuple[str, list[str]]:
    problems: list[str] = []
    specs = machine_specs(M)

    def one(match: re.Match) -> str:
        expr = match.group(1).strip()
        path, _, filt = (p.strip() for p in expr.partition("|"))

        try:
            if path.startswith("code:"):
                return inline_code(path[len("code:"):])
            if path.startswith("hex:"):
                return hexdump_html(M, path[len("hex:"):].strip(), filt)
            if path.startswith("chart:"):
                name = path[len("chart:"):].strip()
                fn = charts.REGISTRY.get(name)
                if fn is None:
                    raise MissingMeasurement(f"no chart named '{name}'")
                return fn(M)
            if path.startswith("machine."):
                node = specs
                for part in path[len("machine."):].split("."):
                    node = node[part]
                return fmt(node, filt)
            return fmt(dig(M, path), filt)
        except (MissingMeasurement, KeyError, IndexError, TypeError, ValueError) as e:
            problems.append(f"{where}: {{{{{expr}}}}} — {e}")
            return ('<span style="background:#f8e4ee;color:#a51f5c;'
                    'font-family:monospace;padding:0 .2em">?</span>')

    return TOKEN.sub(one, text), problems


# --------------------------------------------------------------------------
# shell
# --------------------------------------------------------------------------

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{assets}style.css">
</head>
<body>
"""

FOOT = """<script src="{assets}site.js"></script>
</body>
</html>
"""


def sitenav(mod, *, depth: int, page: str = "") -> str:
    """The site's real navigation: every page, by its title, grouped by part.

    The strip says which pipeline stages you have built. This says where you
    are and where you can go — two different jobs, which one control was
    doing badly.
    """
    base = "" if depth else "modules/"
    home = "index.html" if depth == 0 else "../index.html"
    rl = "reading-list.html" if depth == 0 else "../reading-list.html"

    out = ['<nav class="sitenav" aria-label="the modules">']
    out.append(
        f'<a class="nav-home{" current" if page == "index" and mod.num == 0 else ""}" '
        f'href="{home}"><span class="n">00</span>'
        '<span class="t">The pipeline, working</span></a>')

    for part in (1, 2, 3):
        out.append(f'<p class="nav-part">{escape(PART_TITLES[part])}</p>')
        out.append('<ul class="nav-list">')
        for m in MODULES:
            if m.part != part or m.num == 0:
                continue
            cur = " current" if (m.num == mod.num and not page) else ""
            aria = ' aria-current="page"' if cur else ""
            out.append(
                f'<li><a class="nav-item{cur}" href="{base}{m.slug}.html" '
                f'data-module="{m.slug}"{aria}>'
                f'<span class="n">{m.nn}</span>'
                f'<span class="t">{escape(m.title)}</span></a></li>')
        out.append("</ul>")

    out.append(
        f'<a class="nav-appendix{" current" if page == "reading-list" else ""}" '
        f'href="{rl}"><span class="n">··</span>'
        '<span class="t">The reading list</span></a>')
    out.append("</nav>")
    return "".join(out)


def masthead(mod, *, depth: int, page: str = "") -> str:
    """A slim bar: where you are, named. The page's own title is the header."""
    home = "index.html" if depth == 0 else "../index.html"
    part = PART_TITLES[mod.part]
    if page == "reading-list":
        num, here, part = "", "The reading list", "appendix"
    elif mod.num == 0:
        num, here = "", "The pipeline, working"
    else:
        num, here = mod.nn, mod.title
    # The number is kept separate so a phone can show it alone: "06" still says
    # where you are, where a title cut off after five letters does not.
    numbered = " numbered" if num else ""
    hn = f'<span class="hn">{num}</span>' if num else ""
    counter = (f'<span class="progress-label">{mod.nn} / 15</span>'
               if mod.num and not page else
               '<span class="progress-label" data-progress-count>0 / 15 complete</span>')
    return (
        '<header class="masthead"><div class="masthead-inner">'
        f'<a class="brand" href="{home}"><b>Beneath the Pipeline</b></a>'
        f'<span class="crumb{numbered}"><span class="part">{escape(part.lower())}</span>'
        f'<span class="here">{hn}<span class="ht">{escape(here)}</span></span></span>'
        f'{counter}'
        '<button class="nav-toggle" type="button" aria-expanded="false" '
        'aria-controls="sitenav-panel">menu</button>'
        '</div></header>'
    )


def modnav(mod, *, depth: int = 1) -> str:
    """Previous/next links. `depth` is 0 for the index page, which lives one
    directory up from the modules and needs a different prefix."""
    base = "" if depth else "modules/"
    prev_m = BY_NUM.get(mod.num - 1)
    next_m = BY_NUM.get(mod.num + 1)
    out = ['<nav class="modnav">']
    if prev_m is not None:
        href = "../index.html" if prev_m.num == 0 else f"{prev_m.slug}.html"
        out.append(f'<a class="prev" href="{href}"><span class="dir">previous</span>'
                   f'<span class="name">{prev_m.nn} · {escape(prev_m.title)}</span></a>')
    if next_m is not None:
        out.append(f'<a class="next" href="{base}{next_m.slug}.html">'
                   f'<span class="dir">{"begin" if mod.num == 0 else "next"}</span>'
                   f'<span class="name">{next_m.nn} · {escape(next_m.title)}</span></a>')
    else:
        out.append(f'<a class="next" href="{"reading-list.html" if depth == 0 else "../reading-list.html"}">'
                   '<span class="dir">appendix</span>'
                   '<span class="name">The reading list</span></a>')
    out.append("</nav>")
    return "".join(out)


def done_toggle(mod) -> str:
    return (f'<button class="done-toggle" type="button" aria-pressed="false" '
            f'data-module="{mod.slug}"><span class="box"></span>'
            f'<span class="label">mark this module complete</span></button>')


def render_page(mod, body: str, *, depth: int,
                show_nav=True, show_toggle=True, page: str = "") -> str:
    assets = "assets/" if depth == 0 else "../assets/"
    title = ("Beneath the Pipeline" if mod.num == 0
             else f"{mod.nn} · {mod.title} — Beneath the Pipeline")
    parts = [
        HEAD.format(title=escape(title), desc=escape(mod.desc), assets=assets),
        masthead(mod, depth=depth, page=page),
        '<div class="wrap"><div class="layout">',
        f'<div class="rail" id="sitenav-panel">{sitenav(mod, depth=depth, page=page)}</div>',
        '<main class="col">',
        body,
    ]
    if show_toggle and mod.num:
        parts.append(done_toggle(mod))
    if show_nav:
        parts.append(modnav(mod, depth=depth))
    parts += ['</main></div></div>', FOOT.format(assets=assets)]
    return "".join(parts)


# --------------------------------------------------------------------------
# data file — the same numbers, readable by anything that wants them
# --------------------------------------------------------------------------

def write_data_js(M: dict) -> None:
    """site/assets/data/measurements.js

    Loaded with <script src>, never fetched: fetch() is blocked under
    file://, so a JSON file would be unreadable to the page.
    """
    out = SITE / "assets" / "data" / "measurements.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "/* Generated by build.py. Every number the site prints, in one place. */\n"
        "window.BTP_MEASUREMENTS = " + json.dumps(M, indent=1, sort_keys=True) + ";\n")


# --------------------------------------------------------------------------

def build(check_only: bool = False) -> int:
    M = load_measurements()
    problems: list[str] = []
    written = 0
    missing_content = []

    for mod in MODULES:
        src = CONTENT / f"{mod.slug}.html"
        if not src.exists():
            missing_content.append(mod.slug)
            continue
        body, probs = substitute(src.read_text(), M, where=f"{mod.slug}.html")
        problems += probs
        depth = 0 if mod.num == 0 else 1
        html = render_page(mod, body, depth=depth,
                           show_toggle=mod.num != 0,
                           page="index" if mod.num == 0 else "")
        dest = (SITE / "index.html") if mod.num == 0 else (
            SITE / "modules" / f"{mod.slug}.html")
        if not check_only:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(html)
            written += 1

    # the reading list — same shell, no prev/next, no progress toggle
    rl = CONTENT / "reading-list.html"
    if rl.exists():
        body, probs = substitute(rl.read_text(), M, where="reading-list.html")
        problems += probs
        shell = BY_NUM[0]
        # It sits beside index.html, not in modules/, so it is a depth-0 page:
        # the sidebar's links have to be written from the site root.
        html = render_page(shell, body, depth=0,
                           show_nav=False, show_toggle=False,
                           page="reading-list")
        html = html.replace("<title>Beneath the Pipeline</title>",
                            "<title>The reading list — Beneath the Pipeline</title>")
        if not check_only:
            (SITE / "reading-list.html").write_text(html)
            written += 1
    else:
        missing_content.append("reading-list")

    if not check_only:
        write_data_js(M)

    if missing_content:
        print(f"content not written yet: {', '.join(missing_content)}")
    if problems:
        print(f"\n{len(problems)} unresolved token(s):")
        for p in problems[:40]:
            print("  " + p)
        if len(problems) > 40:
            print(f"  … and {len(problems) - 40} more")
    print(f"\n{written} page(s) written to {SITE}"
          f"{' (check only — nothing written)' if check_only else ''}")
    print(f"measurements loaded for: {', '.join(sorted(M)) or '(none yet)'}")
    return 1 if problems else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report unresolved tokens without writing files")
    args = ap.parse_args()
    sys.exit(build(check_only=args.check))


if __name__ == "__main__":
    main()
