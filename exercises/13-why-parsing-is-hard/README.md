# 13 · Why parsing is a hard problem

**Dependencies:** `pymupdf`, `pdfplumber`, `pytesseract` **and the Tesseract binary**.
Part (d) also needs `transformers`, `torch`, `torchvision`; `--skip-ml` leaves it out.

```sh
brew install tesseract          # macOS
sudo apt install tesseract-ocr  # Debian / Ubuntu

python data/fetch.py --only pdfs
python exercises/13-why-parsing-is-hard/solution.py
python exercises/13-why-parsing-is-hard/verify.py
```

`pytesseract` is only a wrapper. Without the binary you get `TesseractNotFoundError`.

This module is investigate-first: the solution runs all four experiments and prints
what happened. Read it, then change things — the dpi, the OCR settings, the documents —
and watch the numbers move.

## (a) Text-based against image-based

The repository builds the matched pair: a clean text PDF, and the same pages rendered to
images and wrapped back into a PDF. Run the same extractor over both.

## (b) OCR, and where its errors cluster

Character error rate is edits per character of the true text. `edit_distance` is written
out in the solution rather than imported, because that number is the whole accuracy
story.

Run it on three documents — a clean scan, a bad scan, and a page of tables — and look
at where the errors land rather than only at the average.

## (c) Layout

Two experiments. First, the same extractor with layout awareness off, on a two-column
page. Second, two documents holding the same numbers in the same visual arrangement,
one drawn with a full grid and one with horizontal rules only. Predict which one a
table finder can see.

## (d) Why the good models want a GPU

Tesseract is a character-level engine that runs on the CPU. TrOCR is 334M parameters and
a matrix multiply against every one of them per line. Time both, on CPU and on whatever
accelerator you have.

Report both honestly. The ML model is more than an order of magnitude more expensive per
page *even on a GPU*, and for a clean scan Tesseract already gets a near-zero error
rate. The ML path earns its cost where the rules fail, not everywhere.

## What you should be able to say afterwards

- The four rungs of the parsing ladder, and what each needs.
- Why parsing fails *silently* and per document, unlike every other pipeline stage.
- The first measurement to add to any ingestion pipeline.
