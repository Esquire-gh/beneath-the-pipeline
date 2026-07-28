#!/usr/bin/env python3
"""Module 13 — worked solution, and the source of the module page's numbers.

    python exercises/13-why-parsing-is-hard/solution.py
    python exercises/13-why-parsing-is-hard/solution.py --skip-ml   # no TrOCR

Four investigations, each one a mechanism:

    (a) text-based against image-based, on documents that look identical
    (b) OCR, and where its errors cluster
    (c) layout, and why reading order is a guess
    (d) why the good models want a GPU

Needs: pymupdf, pdfplumber, pytesseract + the Tesseract binary.
(d) also needs transformers, torch and torchvision; --skip-ml leaves it out.
"""
import argparse
import io
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import gpu, human_time, rule, write_measurements   # noqa: E402

SLUG = "13-why-parsing-is-hard"
PDFS = REPO / "data" / "hard_pdfs"


# --------------------------------------------------------------------------
# measuring how wrong an OCR result is
# --------------------------------------------------------------------------

def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance: the fewest single-character edits from a to b.

    Written out rather than imported, because the number it produces is the
    whole of this module's accuracy story and it should not be a black box.
    """
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1,          # delete
                               current[j - 1] + 1,       # insert
                               previous[j - 1] + (ca != cb)))   # substitute
        previous = current
    return previous[-1]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def character_error_rate(reference: str, guess: str) -> float:
    """Edits per character of the original. 0.0 is perfect; 1.0 is hopeless."""
    reference, guess = normalize(reference), normalize(guess)
    if not reference:
        return 0.0
    return edit_distance(reference, guess) / len(reference)


def word_accuracy(reference: str, guess: str) -> float:
    ref_words = normalize(reference).split()
    got_words = set(normalize(guess).split())
    if not ref_words:
        return 0.0
    return sum(1 for w in ref_words if w in got_words) / len(ref_words)


# --------------------------------------------------------------------------
# extraction helpers
# --------------------------------------------------------------------------

def pymupdf_text(path: Path, sort: bool = False) -> str:
    import fitz
    with fitz.open(path) as doc:
        return "\n".join(page.get_text("text", sort=sort) for page in doc)


def page_images(path: Path, dpi: int = 200, limit: int | None = None):
    import fitz
    from PIL import Image
    out = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc):
            if limit is not None and i >= limit:
                break
            pix = page.get_pixmap(dpi=dpi)
            out.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
    return out


def tesseract_text(images) -> tuple[str, float]:
    import pytesseract
    t0 = time.perf_counter()
    text = "\n".join(pytesseract.image_to_string(img) for img in images)
    return text, time.perf_counter() - t0


def tesseract_lines(image, min_conf: int = -1):
    """Line boxes from Tesseract, used to feed the ML model the same lines."""
    import pytesseract
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    lines: dict[tuple, list[int]] = {}
    for i in range(len(data["text"])):
        if not data["text"][i].strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(i)
    boxes = []
    for key, idxs in lines.items():
        left = min(data["left"][i] for i in idxs)
        top = min(data["top"][i] for i in idxs)
        right = max(data["left"][i] + data["width"][i] for i in idxs)
        bottom = max(data["top"][i] + data["height"][i] for i in idxs)
        text = " ".join(data["text"][i] for i in idxs)
        boxes.append({"box": (left, top, right, bottom), "text": text})
    return boxes


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-ml", action="store_true",
                    help="skip the TrOCR comparison in part (d)")
    ap.add_argument("--ml-lines", type=int, default=24,
                    help="how many text lines to run through the ML model")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    m = {}
    clean = PDFS / "gen-clean-1col.pdf"
    scanned = PDFS / "gen-clean-1col-scanned.pdf"
    noisy = PDFS / "gen-2col-scanned-noisy.pdf"
    tables = PDFS / "gen-tables.pdf"
    tables_scan = PDFS / "gen-tables-scanned.pdf"
    two_col = PDFS / "gen-2col.pdf"
    if not scanned.exists():
        sys.exit("missing PDFs — run: python data/fetch.py --only pdfs")

    # ======================================================================
    rule("(a) two documents that look identical")
    # ======================================================================
    pairs = [
        ("clean_1col", clean, scanned),
        ("tables", tables, tables_scan),
    ]
    m["matched_pairs"] = {}
    for name, text_pdf, image_pdf in pairs:
        a, b = pymupdf_text(text_pdf), pymupdf_text(image_pdf)
        m["matched_pairs"][name] = {
            "text_pdf": text_pdf.name,
            "image_pdf": image_pdf.name,
            "text_chars": len(a.strip()),
            "image_chars": len(b.strip()),
            "text_bytes": text_pdf.stat().st_size,
            "image_bytes": image_pdf.stat().st_size,
            "size_ratio": image_pdf.stat().st_size / text_pdf.stat().st_size,
        }
        r = m["matched_pairs"][name]
        print(f"  {text_pdf.name:<30} {r['text_chars']:>6,} characters, "
              f"{r['text_bytes'] / 1024:>8,.0f} KB")
        print(f"  {image_pdf.name:<30} {r['image_chars']:>6,} characters, "
              f"{r['image_bytes'] / 1024:>8,.0f} KB   "
              f"<- same page, {r['size_ratio']:.0f}x the file, no text at all")

    # ======================================================================
    rule("(b) OCR — reconstructing what the scanner threw away")
    # ======================================================================
    reference = pymupdf_text(clean)
    m["ocr"] = {}

    cases = [
        ("clean_scan", scanned, reference, "a clean 150 dpi scan"),
        ("noisy_scan", noisy, pymupdf_text(two_col),
         "120 dpi, skewed, speckled"),
        ("table_scan", tables_scan, pymupdf_text(tables),
         "ruled tables, dense small numbers"),
    ]
    for key, pdf, ref_text, description in cases:
        images = page_images(pdf, dpi=200)
        got, seconds = tesseract_text(images)
        m["ocr"][key] = {
            "file": pdf.name,
            "description": description,
            "pages": len(images),
            "seconds": seconds,
            "seconds_per_page": seconds / len(images),
            "cer": character_error_rate(ref_text, got),
            "word_accuracy": word_accuracy(ref_text, got),
            "reference_chars": len(normalize(ref_text)),
            "got_chars": len(normalize(got)),
            "excerpt": normalize(got)[:260],
        }
        r = m["ocr"][key]
        print(f"  {description:<32} CER {r['cer']:.4f}   "
              f"words found {r['word_accuracy']:.1%}   "
              f"{human_time(r['seconds_per_page'])}/page")

    m["ocr_spread"] = {
        "best": min(m["ocr"], key=lambda k: m["ocr"][k]["cer"]),
        "worst": max(m["ocr"], key=lambda k: m["ocr"][k]["cer"]),
    }
    m["ocr_spread"]["ratio"] = (m["ocr"][m["ocr_spread"]["worst"]]["cer"]
                                / max(m["ocr"][m["ocr_spread"]["best"]]["cer"], 1e-9))
    print(f"  the worst case is {m['ocr_spread']['ratio']:.1f}x the error rate "
          f"of the best — same OCR engine, same settings")

    # a concrete look at what OCR did to the numbers in a table
    print(f"\n  what the table scan came back as:")
    print(f"    {m['ocr']['table_scan']['excerpt'][:200]}…")

    # ======================================================================
    rule("(c) layout — reading order is a guess")
    # ======================================================================
    smart = pymupdf_text(two_col, sort=False)
    naive = pymupdf_text(two_col, sort=True)
    import difflib
    m["layout"] = {
        "file": two_col.name,
        "same_words": sorted(smart.split()) == sorted(naive.split()),
        "similarity": difflib.SequenceMatcher(None, smart, naive).ratio(),
        "layout_aware_excerpt": normalize(smart)[220:520],
        "coordinate_order_excerpt": normalize(naive)[220:520],
    }
    print(f"  same document, same library, layout awareness off:")
    print(f"    identical bag of words: {m['layout']['same_words']}")
    print(f"    character similarity:   {m['layout']['similarity']:.3f}")
    print(f"\n  in coordinate order:\n    {m['layout']['coordinate_order_excerpt'][:190]}…")

    # Two documents holding the same numbers in the same visual arrangement.
    # One is drawn with horizontal rules only; the other has a full grid. A
    # human reads both as tables. A line-based table finder can only see one.
    import pdfplumber
    m["tables"] = {}
    for key, pdf_path in (("rules_only", tables),
                          ("full_grid", PDFS / "gen-tables-ruled.pdf")):
        if not pdf_path.exists():
            continue
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            found = page.extract_tables()
            flat = page.extract_text() or ""
            m["tables"][key] = {
                "file": pdf_path.name,
                "tables_found": len(found),
                "rows_found": sum(len(t) for t in found),
                "horizontal_lines": len(page.horizontal_edges),
                "vertical_lines": len(page.vertical_edges),
                "first_row": found[0][0] if found and found[0] else None,
                "linearised_excerpt": normalize(flat)[:240],
            }
        r = m["tables"][key]
        print(f"\n  {pdf_path.name:<24} {r['horizontal_lines']:>3} horizontal "
              f"and {r['vertical_lines']:>3} vertical rules "
              f"-> {r['tables_found']} table(s), {r['rows_found']} rows")
    print(f"\n  the undetected page, as plain text:\n    "
          f"{m['tables']['rules_only']['linearised_excerpt'][:190]}…")

    # ======================================================================
    rule("(d) why the good models want a GPU")
    # ======================================================================
    accel = gpu()
    m["accelerator"] = accel
    print(f"  this machine: {accel['kind']}"
          f"{' — ' + accel['name'] if accel['name'] else ''}")

    images = page_images(scanned, dpi=200)
    boxes = tesseract_lines(images[0])
    m["ml"] = {"lines_available": len(boxes)}

    tess_text, tess_seconds = tesseract_text(images[:1])
    m["ml"]["tesseract"] = {
        "seconds_per_page": tess_seconds,
        "cer": character_error_rate(reference, tess_text),
        "device": "cpu",
        "approx_parameters": None,
        "note": "Tesseract is a character-level engine; it runs on the CPU.",
    }
    print(f"  Tesseract, one page: {human_time(tess_seconds)} on the CPU, "
          f"CER {m['ml']['tesseract']['cer']:.4f}")

    if args.skip_ml:
        print("  (skipping the ML model — --skip-ml)")
    else:
        try:
            import torch
            from transformers import (AutoImageProcessor, AutoTokenizer,
                                      VisionEncoderDecoderModel)

            t0 = time.perf_counter()
            imgproc = AutoImageProcessor.from_pretrained(
                "microsoft/trocr-base-printed")
            tok = AutoTokenizer.from_pretrained("roberta-base")
            model = VisionEncoderDecoderModel.from_pretrained(
                "microsoft/trocr-base-printed").eval()
            load_seconds = time.perf_counter() - t0
            params = sum(p.numel() for p in model.parameters())

            crops = [images[0].crop(b["box"]) for b in boxes[:args.ml_lines]]
            truth = " ".join(b["text"] for b in boxes[:args.ml_lines])
            m["ml"]["trocr"] = {
                "model": "microsoft/trocr-base-printed",
                "parameters": int(params),
                "load_seconds": load_seconds,
                "lines": len(crops),
                "devices": {},
            }
            print(f"  TrOCR: {params / 1e6:.0f}M parameters, "
                  f"loaded in {human_time(load_seconds)}")

            devices = ["cpu"]
            if accel["kind"] in ("cuda", "mps"):
                devices.append(accel["kind"])

            for dev in devices:
                model.to(dev)
                px = imgproc(images=crops, return_tensors="pt").pixel_values.to(dev)
                with torch.no_grad():             # two warm-up passes: the
                    model.generate(px[:2], max_new_tokens=8)   # first call on
                    model.generate(px[:2], max_new_tokens=8)   # a GPU compiles
                t0 = time.perf_counter()
                with torch.no_grad():
                    out = model.generate(px, max_new_tokens=40)
                seconds = time.perf_counter() - t0
                text = " ".join(tok.batch_decode(out, skip_special_tokens=True))
                m["ml"]["trocr"]["devices"][dev] = {
                    "seconds": seconds,
                    "seconds_per_line": seconds / len(crops),
                    "cer_against_tesseract_lines": character_error_rate(truth, text),
                    "excerpt": normalize(text)[:200],
                }
                print(f"    {dev:<5} {human_time(seconds)} for {len(crops)} "
                      f"lines = {human_time(seconds / len(crops))} per line")

            devs = m["ml"]["trocr"]["devices"]
            if len(devs) > 1:
                other = [d for d in devs if d != "cpu"][0]
                m["ml"]["gpu_speedup"] = (devs["cpu"]["seconds"]
                                          / devs[other]["seconds"])
                m["ml"]["gpu_device"] = other
                print(f"  the {other} runs the same model "
                      f"{m['ml']['gpu_speedup']:.1f}x faster than the CPU")
            else:
                m["ml"]["gpu_speedup"] = None
                m["ml"]["gpu_device"] = None
                print("  no GPU on this machine — CPU timing only")

            per_line_ml = devs[list(devs)[-1]]["seconds_per_line"]
            m["ml"]["ml_vs_tesseract_per_page"] = (
                per_line_ml * len(boxes) / tess_seconds)
            print(f"  extrapolated to a whole page "
                  f"({len(boxes)} lines), the ML model costs "
                  f"{m['ml']['ml_vs_tesseract_per_page']:.1f}x Tesseract")
        except Exception as e:
            m["ml"]["trocr_error"] = f"{type(e).__name__}: {e}"
            print(f"  ML model unavailable: {type(e).__name__}: {e}")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
