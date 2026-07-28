#!/usr/bin/env python3
"""Module 3 — worked solution, and the source of the module page's numbers.

Read this after you have written your own. Running it records
measurements.json.

    python exercises/03-bytes-numbers/solution.py
"""
import struct
import sys
import wave
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule, write_measurements   # noqa: E402

SLUG = "03-bytes-numbers"


# --------------------------------------------------------------------------
# 1 · a hex dump, in about thirty lines
# --------------------------------------------------------------------------

def hexdump(data: bytes, width: int = 16) -> list[str]:
    rows = []
    for offset in range(0, len(data), width):
        chunk = data[offset:offset + width]
        hex_cells = []
        for i, byte in enumerate(chunk):
            hex_cells.append(f"{byte:02x}")
            if i % 8 == 7:
                hex_cells.append("")            # the gap after eight bytes
        hex_col = " ".join(hex_cells)
        pad = " " * (width * 3 + 1 - len(hex_col))
        text = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        rows.append(f"{offset:08x}  {hex_col}{pad} |{text}|")
    return rows


# --------------------------------------------------------------------------
# 2 · the WAV header, read from its written agreement
# --------------------------------------------------------------------------

WAV_FIELDS = {
    "riff":            (0, 4, "ascii"),
    "wave":            (8, 4, "ascii"),
    "channels":        (22, 2, "H"),
    "sample_rate":     (24, 4, "I"),
    "bits_per_sample": (34, 2, "H"),
}


def parse_wav_header(data: bytes, endian: str = "<") -> dict:
    out = {}
    for name, (offset, width, kind) in WAV_FIELDS.items():
        if kind == "ascii":
            out[name] = data[offset:offset + width].decode("ascii", "replace")
        else:
            out[name] = struct.unpack_from(endian + kind, data, offset)[0]
    return out


# --------------------------------------------------------------------------
# 3 · a width is a promise about range
# --------------------------------------------------------------------------

WIDTH_FMT = {1: "B", 2: "H", 4: "I", 8: "Q"}


def store_unsigned(value: int, width: int) -> tuple[int, bool]:
    fmt = "<" + WIDTH_FMT[width]
    try:
        packed = struct.pack(fmt, value)
        return struct.unpack(fmt, packed)[0], False
    except struct.error:
        wrapped = value % (256 ** width)
        return struct.unpack(fmt, struct.pack(fmt, wrapped))[0], True


# --------------------------------------------------------------------------
# 4 · floats
# --------------------------------------------------------------------------

def float_facts() -> dict:
    total = 0.1 + 0.2
    return {
        "sum": total,
        "equals_point_three": total == 0.3,
        "error": total - 0.3,
        "as_bytes": struct.pack("<d", 0.1).hex(" "),
        "exact": str(Decimal(0.1)),
        "exact_sum": str(Decimal(total)),
    }


# --------------------------------------------------------------------------

def make_wav(path: Path, *, channels=2, rate=44100, bits=16, seconds=0.25):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(bits // 8)
        w.setframerate(rate)
        w.writeframes(bytes(int(rate * seconds) * channels * (bits // 8)))
    return path


def main() -> None:
    tmp = Path(__file__).parent / "_scratch"
    tmp.mkdir(exist_ok=True)
    wav = make_wav(tmp / "tone.wav")
    data = wav.read_bytes()

    m = {"wav": {"channels": 2, "rate": 44100, "bits": 16,
                 "size": len(data), "name": wav.name}}

    rule("1 · a hex dump of the first 48 bytes of a real WAV")
    dump = hexdump(data[:48])
    for line in dump:
        print("  " + line)
    m["hexdump_lines"] = dump
    m["hexdump_dump"] = [
        {"offset": i * 16,
         "hex": [f"{b:02x}" for b in data[i * 16:i * 16 + 16]],
         "ascii": "".join(chr(b) if 32 <= b <= 126 else "."
                          for b in data[i * 16:i * 16 + 16])}
        for i in range(3)
    ]

    rule("2 · the header, honouring the agreement")
    correct = parse_wav_header(data, "<")
    m["header_correct"] = correct
    for k, v in correct.items():
        print(f"  {k:<16} {v!r}")

    rule("3 · the same bytes, byte order flipped")
    flipped = parse_wav_header(data, ">")
    m["header_flipped"] = flipped
    for k, v in flipped.items():
        marker = "" if correct[k] == v else "   <- nonsense"
        print(f"  {k:<16} {v!r}{marker}")
    m["endian_ratio"] = (flipped["sample_rate"] / correct["sample_rate"]
                         if correct["sample_rate"] else None)

    rule("4 · a width is a promise about range")
    rows = []
    for value, width in ((200, 1), (255, 1), (256, 1), (300, 1),
                         (70000, 2), (70000, 4)):
        stored, overflowed = store_unsigned(value, width)
        rows.append({"value": value, "width": width, "stored": stored,
                     "overflowed": overflowed,
                     "max": 256 ** width - 1})
        print(f"   {value:>6} in {width} byte(s) -> {stored:>6}"
              f"{'   OVERFLOW' if overflowed else ''}")
    m["integer_widths"] = rows
    m["width_limits"] = {str(w): 256 ** w - 1 for w in (1, 2, 4, 8)}

    rule("5 · floats")
    ff = float_facts()
    m["floats"] = ff
    print(f"  0.1 + 0.2            = {ff['sum']!r}")
    print(f"  == 0.3               ? {ff['equals_point_three']}")
    print(f"  difference           = {ff['error']!r}")
    print(f"  0.1 as eight bytes   = {ff['as_bytes']}")
    print(f"  what 0.1 really is   = {ff['exact']}")

    # The number that matters to a pipeline: an embedding is 384 of these.
    dims = 384
    m["embedding"] = {
        "dims": dims,
        "float32_bytes": dims * 4,
        "float64_bytes": dims * 8,
        "million_float32_bytes": dims * 4 * 1_000_000,
        "million_float64_bytes": dims * 8 * 1_000_000,
    }
    print(f"\n  one {dims}-dimensional embedding is {dims * 4} bytes at 32-bit "
          f"precision, {dims * 8} at 64-bit")

    path = write_measurements(SLUG, m)
    print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
