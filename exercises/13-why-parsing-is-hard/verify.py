#!/usr/bin/env python3
"""Check that module 13's observations reproduced on your machine.

    python exercises/13-why-parsing-is-hard/verify.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import read_measurements, rule   # noqa: E402

SLUG = "13-why-parsing-is-hard"


def check_your_code(checks):
    """The three functions in starter.py, before the observations."""
    import importlib.util
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("starter", here / "starter.py")
    yours = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(yours)
    except Exception as e:
        checks.append(("starter.py imports", False, f"{type(e).__name__}: {e}"))
        return

    try:
        for a, b, want in (("kitten", "sitting", 3), ("block", "b1ock", 1),
                           ("same", "same", 0), ("", "abc", 3), ("abc", "", 3)):
            got = yours.edit_distance(a, b)
            checks.append((f"edit_distance({a!r}, {b!r}) == {want}",
                           got == want, f"got {got!r}"))
    except Exception as e:
        checks.append(("edit_distance runs", False, f"{type(e).__name__}: {e}"))

    try:
        ref = "The disk hands back 4096 bytes."
        checks.append(("character_error_rate is 0 for a perfect read",
                       abs(float(yours.character_error_rate(ref, ref))) < 1e-12,
                       f"got {yours.character_error_rate(ref, ref)!r}"))
        one = yours.character_error_rate(ref, ref.replace("0", "O"))
        checks.append(("one wrong character gives 1/len",
                       abs(float(one) - 1 / len(ref)) < 1e-9,
                       f"got {one!r}, expected {1 / len(ref):.6f}"))
        checks.append(("whitespace is normalised before comparing",
                       abs(float(yours.character_error_rate(
                           ref, ref.replace(" ", "\n  "))) ) < 1e-12,
                       "line breaks should not count as errors"))
        checks.append(("an empty reference gives 0.0",
                       abs(float(yours.character_error_rate("", "anything"))) < 1e-12,
                       f"got {yours.character_error_rate('', 'anything')!r}"))
    except Exception as e:
        checks.append(("character_error_rate runs", False,
                       f"{type(e).__name__}: {e}"))

    try:
        checks.append(("extraction_failed catches an empty string",
                       yours.extraction_failed("") is True, "got False"))
        checks.append(("extraction_failed catches whitespace only",
                       yours.extraction_failed("   \n  \n ") is True, "got False"))
        checks.append(("extraction_failed passes a real page",
                       yours.extraction_failed("word " * 200) is False,
                       "a page of prose was reported as a failure"))
    except Exception as e:
        checks.append(("extraction_failed runs", False, f"{type(e).__name__}: {e}"))


def main() -> int:
    m = read_measurements(SLUG)
    if not m:
        print("no measurements yet — run solution.py first")
        return 1

    checks = []

    def check(name, ok, detail):
        checks.append((name, ok, detail))

    check_your_code(checks)

    pair = m["matched_pairs"]["clean_1col"]
    check("the text PDF yields text", pair["text_chars"] > 500,
          f"{pair['text_chars']:,} characters")
    check("the scanned twin yields NONE", pair["image_chars"] == 0,
          f"{pair['image_chars']} characters from a page that looks identical")
    check("the scan is very much larger on disk", pair["size_ratio"] > 10,
          f"{pair['size_ratio']:.0f}x the file size for the same page")

    ocr = m["ocr"]
    check("OCR recovers a clean scan almost perfectly",
          ocr["clean_scan"]["cer"] < 0.02,
          f"character error rate {ocr['clean_scan']['cer']:.4f}")
    check("a poor scan is dramatically worse",
          ocr["noisy_scan"]["cer"] > ocr["clean_scan"]["cer"] * 5,
          f"{ocr['noisy_scan']['cer']:.4f} against "
          f"{ocr['clean_scan']['cer']:.4f} — "
          f"{m['ocr_spread']['ratio']:.0f}x, same engine")

    layout = m["layout"]
    check("coordinate order changes the document",
          layout["similarity"] < 0.9,
          f"character similarity {layout['similarity']:.3f} between "
          f"layout-aware and coordinate-order readings")

    tables = m.get("tables", {})
    if "rules_only" in tables and "full_grid" in tables:
        check("a table without vertical rules is not detected",
              tables["rules_only"]["rows_found"] == 0,
              f"{tables['rules_only']['rows_found']} rows found in "
              f"{tables['rules_only']['file']}")
        check("the same table with a grid is detected",
              tables["full_grid"]["rows_found"] > 0,
              f"{tables['full_grid']['rows_found']} rows found in "
              f"{tables['full_grid']['file']}")

    ml = m.get("ml", {})
    if ml.get("gpu_speedup"):
        check("the accelerator runs the same model faster",
              ml["gpu_speedup"] > 1.0,
              f"{ml['gpu_speedup']:.1f}x on {ml['gpu_device']}")
    if ml.get("ml_vs_tesseract_per_page"):
        check("the ML model costs much more per page than Tesseract",
              ml["ml_vs_tesseract_per_page"] > 1.0,
              f"{ml['ml_vs_tesseract_per_page']:.1f}x, even on the "
              f"accelerator")

    rule("module 13 — do the observations hold?")
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}")
        print(f"         {detail}")
        failed += 0 if ok else 1
    print()
    print(f"all {len(checks)} checks hold." if not failed else
          f"{failed} of {len(checks)} checks did not hold — see the "
          f"troubleshooting note on the module page.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
