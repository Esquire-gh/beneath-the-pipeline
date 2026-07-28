#!/usr/bin/env python3
"""Check that module 2's observations reproduced on your machine.

    python exercises/02-bytes-text/verify.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import read_measurements, rule   # noqa: E402

SLUG = "02-bytes-text"


def main() -> int:
    m = read_measurements(SLUG)
    if not m:
        print("no measurements yet — run investigate.py first")
        return 1

    checks = []

    def check(name, ok, detail):
        checks.append((name, ok, detail))

    check("a byte holds 256 settings", m["byte_settings"] == 256,
          f"2**8 = {m['byte_settings']}")

    widths = {r["char"]: r["n_bytes"] for r in m["char_widths"]}
    check("UTF-8 gives characters different widths",
          len(set(widths.values())) > 1,
          ", ".join(f"{c}={n}" for c, n in widths.items()))

    check("ASCII characters still take one byte in UTF-8",
          widths.get("A") == 1, "'A' is one byte, as it was in 1963")

    cafe = m["cafe"]
    check("characters and bytes are different counts",
          cafe["len_characters"] != cafe["len_utf8_bytes"],
          f"{cafe['len_characters']} characters, "
          f"{cafe['len_utf8_bytes']} bytes")

    astro = m["astronaut"]
    check("one glyph can be several characters",
          astro["len_characters"] > 1,
          f"1 glyph, {astro['len_characters']} characters, "
          f"{astro['len_utf8_bytes']} bytes")

    dis = m["disagreement"]
    check("the same bytes decoded to two different texts",
          dis["utf8"] != dis["latin1"],
          f"UTF-8 {dis['utf8']!r} vs Latin-1 {dis['latin1']!r}")

    check("a wrong agreement can fail loudly",
          bool(m.get("decode_error")),
          (m.get("decode_error") or "no error raised"))

    check("the PNG signature is where the specification says",
          m["png"]["signature"][:4] == ["89", "50", "4e", "47"],
          " ".join(m["png"]["signature"]))

    if "pdf" in m:
        check("the PDF announces itself in readable ASCII",
              m["pdf"]["signature_ascii"].startswith("%PDF"),
              m["pdf"]["signature_ascii"])

    check("`file` identified a PNG named .txt",
          "PNG" in m["file_command"], m["file_command"].strip())

    rule("module 2 — do the observations hold?")
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
