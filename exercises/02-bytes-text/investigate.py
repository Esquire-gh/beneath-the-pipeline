#!/usr/bin/env python3
"""Module 2 — data is bytes by agreement: text.

Runs every investigation from the README, prints what came back, and records
the numbers the module page prints.

Standard library only. Nothing to install.

    python exercises/02-bytes-text/investigate.py
"""
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule, write_measurements   # noqa: E402

SLUG = "02-bytes-text"

MYSTERY = bytes([0x48, 0x65, 0x6c, 0x6c, 0x6f, 0x21, 0x00, 0x2a])


def sh(cmd: str, cwd: Path) -> str:
    out = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    text = (out.stdout + out.stderr).rstrip()
    print(f"  $ {cmd}")
    for line in text.splitlines():
        print(f"    {line}")
    return text


def hexdump(data: bytes, width: int = 16) -> list[dict]:
    """The same layout `hexdump -C` produces, as data we can put on a page."""
    rows = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        rows.append({
            "offset": off,
            "hex": [f"{b:02x}" for b in chunk],
            "ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in chunk),
        })
    return rows


def main() -> None:
    m = {}
    tmp = Path(tempfile.mkdtemp(prefix="btp-module2-"))
    print(f"working in {tmp}\n")

    # ---- eight bytes, no answer ------------------------------------------
    rule("1 · eight bytes, and no way to know what they mean")
    m["mystery_bytes"] = [f"{b:02x}" for b in MYSTERY]
    readings = {
        "ascii_text": "".join(chr(b) if 32 <= b < 127 else "\\x%02x" % b
                              for b in MYSTERY),
        "two_int32_le": [int.from_bytes(MYSTERY[0:4], "little"),
                         int.from_bytes(MYSTERY[4:8], "little")],
        "two_int32_be": [int.from_bytes(MYSTERY[0:4], "big"),
                         int.from_bytes(MYSTERY[4:8], "big")],
        "one_float64_le": __import__("struct").unpack("<d", MYSTERY)[0],
        "rgba_pixels": [tuple(MYSTERY[0:4]), tuple(MYSTERY[4:8])],
    }
    m["mystery_readings"] = readings
    print(f"  bytes:            {' '.join(m['mystery_bytes'])}")
    print(f"  as ASCII text:    {readings['ascii_text']!r}")
    print(f"  as two 32-bit ints (little-endian): {readings['two_int32_le']}")
    print(f"  as two 32-bit ints (big-endian):    {readings['two_int32_be']}")
    print(f"  as one 64-bit float:                {readings['one_float64_le']!r}")
    print(f"  as two RGBA pixels:                 {readings['rgba_pixels']}")
    print("  the question 'what do these bytes mean' has no answer.")

    # ---- a byte is 256 settings ------------------------------------------
    rule("2 · a byte is eight switches")
    m["byte_settings"] = 2 ** 8
    m["letter_a"] = {"char": "A", "code": ord("A"), "bits": format(ord("A"), "08b")}
    print(f"  one byte holds {2 ** 8} distinct settings, and nothing else")
    print(f"  someone decided {ord('A')} means 'A'.  in bits: "
          f"{format(ord('A'), '08b')}")

    # ---- hexdump a plain text file ---------------------------------------
    rule("3 · hexdump a text file and read it against an ASCII table")
    plain = tmp / "plain.txt"
    plain.write_text("Hello, floor.\n", encoding="ascii")
    dumper = "xxd" if shutil.which("xxd") else "hexdump -C"
    sh(f"{dumper} plain.txt", tmp)
    m["plain"] = {"text": "Hello, floor.\n", "bytes": len(plain.read_bytes()),
                  "dump": hexdump(plain.read_bytes()), "tool": dumper}

    # ---- one character, several bytes ------------------------------------
    rule("4 · one character is not one byte")
    samples = ["A", "é", "→", "🧱"]
    rows = []
    for ch in samples:
        enc = ch.encode("utf-8")
        rows.append({
            "char": ch,
            "name": unicodedata.name(ch, "?"),
            "codepoint": f"U+{ord(ch):04X}",
            "utf8_bytes": [f"{b:02x}" for b in enc],
            "n_bytes": len(enc),
        })
        print(f"  {ch!r:<6} {rows[-1]['codepoint']:<8} "
              f"{len(enc)} byte(s): {' '.join(rows[-1]['utf8_bytes'])}")
    m["char_widths"] = rows

    word = "café"
    m["cafe"] = {
        "text": word,
        "len_characters": len(word),
        "len_utf8_bytes": len(word.encode("utf-8")),
        "utf8": [f"{b:02x}" for b in word.encode("utf-8")],
        "len_utf16_bytes": len(word.encode("utf-16-le")),
    }
    print(f"\n  len('café')             = {len(word)}   (characters)")
    print(f"  len('café'.encode())   = {len(word.encode())}   (bytes, UTF-8)")

    flag = "👩‍🚀"          # one thing on screen, several characters
    m["astronaut"] = {
        "displayed_as": "one glyph",
        "len_characters": len(flag),
        "len_utf8_bytes": len(flag.encode("utf-8")),
    }
    print(f"  '{flag}' is 1 glyph on screen, {len(flag)} characters, "
          f"{len(flag.encode())} bytes. three different 'lengths'.")

    # ---- the same bytes, two agreements ----------------------------------
    rule("5 · the same bytes, decoded two ways")
    raw = "café".encode("utf-8")
    as_utf8 = raw.decode("utf-8")
    as_latin1 = raw.decode("latin-1")
    m["disagreement"] = {
        "bytes": [f"{b:02x}" for b in raw],
        "utf8": as_utf8,
        "latin1": as_latin1,
        "same_bytes": True,
    }
    print(f"  bytes            {' '.join(f'{b:02x}' for b in raw)}")
    print(f"  read as UTF-8    {as_utf8!r}")
    print(f"  read as Latin-1  {as_latin1!r}")
    print("  one set of bytes. two readers. two different texts.")

    broken = tmp / "broken.txt"
    broken.write_bytes(b"caf\xe9\n")     # Latin-1 on disk, read as UTF-8
    try:
        broken.read_text(encoding="utf-8")
        m["decode_error"] = None
    except UnicodeDecodeError as e:
        m["decode_error"] = str(e)
        print(f"  and when the agreement is simply wrong:\n    {e}")

    # ---- file formats are the same idea, grown large ---------------------
    rule("6 · a file format is this same agreement, grown large")
    png = tmp / "one.png"
    png.write_bytes(ONE_PIXEL_PNG)
    dump = hexdump(ONE_PIXEL_PNG[:32])
    m["png"] = {
        "signature": [f"{b:02x}" for b in ONE_PIXEL_PNG[:8]],
        "signature_ascii": "".join(chr(b) if 32 <= b < 127 else "."
                                   for b in ONE_PIXEL_PNG[:8]),
        "dump": dump,
        "size": len(ONE_PIXEL_PNG),
    }
    sh(f"{dumper} -l 32 one.png" if dumper == "xxd"
       else f"{dumper} -n 32 one.png", tmp)
    print(f"  every PNG starts with these 8 bytes. the specification says so.")

    pdf = REPO / "pipeline" / "sample_pdfs" / "gen-clean-1col.pdf"
    if pdf.exists():
        head = pdf.read_bytes()[:32]
        m["pdf"] = {
            "signature": [f"{b:02x}" for b in head[:8]],
            "signature_ascii": "".join(chr(b) if 32 <= b < 127 else "."
                                       for b in head[:8]),
            "dump": hexdump(head),
            "name": pdf.name,
        }
        print(f"  and a PDF opens with "
              f"{''.join(chr(b) if 32 <= b < 127 else '.' for b in head[:8])!r}")

    # ---- `file` reads contents, not names --------------------------------
    rule("7 · `file` answers from the bytes")
    shutil.copy(png, tmp / "notes.txt")
    m["file_command"] = sh("file notes.txt", tmp)

    shutil.rmtree(tmp, ignore_errors=True)
    path = write_measurements(SLUG, m)
    print(f"\nwrote {path.relative_to(REPO)}")


ONE_PIXEL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


if __name__ == "__main__":
    main()
