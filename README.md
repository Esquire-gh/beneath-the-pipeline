# Beneath the Pipeline

A local, static tutorial site that takes a retrieval pipeline apart, one line at a time,
all the way down to blocks on a disk — and then pushes every piece until it breaks.

Open `site/index.html` in a browser. No server, no build step, no internet after the
initial data download.

```sh
open site/index.html          # macOS
xdg-open site/index.html      # Linux
```

## What's here

```
site/                     the site — open index.html, everything else follows
  index.html              Part 0: the pipeline, the inventory of assumptions, the map
  modules/01-… 15-….html  fifteen modules, in pipeline order
  reading-list.html       every book, with the chapter and the reason
  assets/                 one stylesheet, one script, the measurements as data

pipeline/naive_rag.py     the thirty lines Part 0 opens with, runnable
exercises/NN-slug/        README, starter.py, solution.py, verify.py, measurements.json
data/fetch.py             corpora — idempotent and resumable
build.py                  authoring-time only; the committed HTML is complete
```

## Running the exercises

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python data/fetch.py            # ~4 GB: MS MARCO, difficult PDFs, generated corpora
python data/fetch.py --small    # or 100k passages instead of 8.8M
```

**Part I needs nothing installed.** Modules 1 and 2 are shell only; module 3 is the
Python standard library. Nobody hits a dependency wall before understanding what a file
is. Each exercise's README declares the subset it actually needs.

Every exercise takes `--scale`, defaulting to a size that finishes on a laptop:

```sh
python exercises/07-index/starter.py --scale small     # 50,000 passages
python exercises/07-index/solution.py --scale part2    # 100,000 — the site's numbers
python exercises/09-index-that-doesnt-fit/solution.py --scale big   # 1,000,000
```

Then check your work:

```sh
python exercises/07-index/verify.py
```

`verify.py` compares your `starter.py` against `solution.py` and names the offset, the
width, or the formula term that differs — not just that a number is wrong.

## About the numbers

Every figure printed on the site was produced by running the code. Measurements land in
`exercises/NN-slug/measurements.json` as the exercises run, and `build.py` injects them
into the HTML — no number in any page is typed by hand, and the build fails loudly if a
page names a measurement that was never taken.

**Your absolute numbers will differ.** The machine that produced these is named on the
index page. What the site claims are the *ratios*, and where a ratio depends on your
hardware the page says so. Every module ends with a troubleshooting note for the case
where your output disagrees.

## Rebuilding the site

Only needed if you change the content or re-run an exercise:

```sh
python build.py           # regenerate site/ from content/ + measurements
python build.py --check   # report unresolved measurements, write nothing
```

## Platform notes

Shell commands are given for macOS and Linux, both labelled where they differ. Windows:
use WSL.

`hnswlib` (module 12) compiles C++ at install time and can fail on macOS with
`fatal error: 'iostream' file not found` — see the note at the bottom of
`requirements.txt` for the one-line fix.

`pytesseract` (module 13) is only a wrapper; the engine is a separate binary:

```sh
brew install tesseract          # macOS
sudo apt install tesseract-ocr  # Debian / Ubuntu
```
