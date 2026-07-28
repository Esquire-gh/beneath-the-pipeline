#!/usr/bin/env python3
"""Module 3 — data is bytes by agreement: numbers.  YOUR WORK GOES HERE.

Four TODOs. The plumbing is written; the ideas are not.

    python exercises/03-bytes-numbers/starter.py     # run yours
    python exercises/03-bytes-numbers/verify.py      # check it

Standard library only. Nothing to install.
"""
import struct
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402


# ==========================================================================
# TODO 1 — a hex dump tool, in about 30 lines
# ==========================================================================
#
# Return a list of strings, one per 16 bytes of `data`, laid out like this:
#
#   00000000  25 50 44 46 2d 31 2e 34  0a 25 93 8c 8b 9e 20 52  |%PDF-1.4.%.... R|
#   ^offset   ^ sixteen bytes in hex, with a gap after eight    ^ printable ASCII
#
# Rules for the right-hand column: a byte from 32 to 126 inclusive prints as
# its ASCII character; anything else prints as a dot. That range is exactly
# the printable part of the table module 2 introduced.
#
# The last row will usually be short. Pad the hex column so the right-hand
# column still lines up.

def hexdump(data: bytes, width: int = 16) -> list[str]:
    rows = []
    for offset in range(0, len(data), width):
        chunk = data[offset:offset + width]
        # TODO: build one line for this chunk and append it to rows
        ...
    return rows


# ==========================================================================
# TODO 2 — read a real format's header, straight from its written agreement
# ==========================================================================
#
# A WAV file starts with a fixed layout. Every field below is at a known
# offset, has a known width, and is stored low byte first ("little-endian").
# This table is not something you deduce — it is what the format's authors
# wrote down, and honouring it is the whole job.
#
#   offset  width  meaning
#   ------  -----  ---------------------------------------------
#        0      4  the ASCII letters RIFF
#        8      4  the ASCII letters WAVE
#       22      2  number of channels          (unsigned, 16-bit)
#       24      4  sample rate in samples/sec  (unsigned, 32-bit)
#       34      2  bits per sample             (unsigned, 16-bit)
#
# struct.unpack_from(fmt, data, offset) reads one field.
#   "<H" = little-endian unsigned 16-bit    "<I" = little-endian unsigned 32-bit
#   ">H" and ">I" are the same widths, high byte first.
#
# Return a dict with keys: riff, wave, channels, sample_rate, bits_per_sample.
# `endian` is "<" or ">" — do not hard-code it, TODO 3 depends on it.

def parse_wav_header(data: bytes, endian: str = "<") -> dict:
    # TODO: read the five fields above and return them in a dict
    ...


# ==========================================================================
# TODO 3 — integers overflow because a width is a promise about range
# ==========================================================================
#
# Pack `value` into `width` bytes as an *unsigned* integer, then read it back.
# struct raises if the value does not fit, so catch struct.error and wrap the
# value yourself the way fixed-width hardware does: keep the low bits, discard
# the rest. The arithmetic is value % (256 ** width).
#
# Return (stored_value, overflowed_bool).

def store_unsigned(value: int, width: int) -> tuple[int, bool]:
    # TODO: pack into `width` bytes, wrapping if it does not fit
    ...


# ==========================================================================
# TODO 4 — why 0.1 + 0.2 is not 0.3
# ==========================================================================
#
# A 64-bit float stores a number as a fraction times a power of two. Numbers
# that are not a sum of powers of two get the nearest value that is.
#
# Return a dict with:
#   sum          0.1 + 0.2
#   equals_point_three   whether that == 0.3
#   error        the difference between the two
#   as_bytes     0.1 packed with struct as 8 little-endian bytes, in hex
#   exact        the exact decimal value Python actually stored for 0.1
#                (hint: Decimal(0.1) — passing the float, not the string)

def float_facts() -> dict:
    from decimal import Decimal   # noqa: F401  (you will want this)
    # TODO
    ...


# --------------------------------------------------------------------------
# plumbing — written for you
# --------------------------------------------------------------------------

def make_wav(path: Path, *, channels=2, rate=44100, bits=16, seconds=0.25):
    """Write a real WAV file with the standard library, so the bytes you
    parse in TODO 2 are bytes something else wrote."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(bits // 8)
        w.setframerate(rate)
        n = int(rate * seconds)
        w.writeframes(bytes(n * channels * (bits // 8)))
    return path


def main() -> None:
    tmp = Path(__file__).parent / "_scratch"
    tmp.mkdir(exist_ok=True)
    wav = make_wav(tmp / "tone.wav")
    data = wav.read_bytes()

    rule("1 · your hex dump of a real WAV header")
    for line in (hexdump(data[:48]) or ["(hexdump returned nothing)"]):
        print("  " + str(line))

    rule("2 · the header, read by its written agreement")
    print("  ", parse_wav_header(data))

    rule("3 · the same bytes, read with the byte order flipped")
    print("  ", parse_wav_header(data, endian=">"))

    rule("4 · integers have a width, and a width is a promise")
    for value, width in ((200, 1), (255, 1), (256, 1), (70000, 2), (70000, 4)):
        print(f"   {value:>6} in {width} byte(s) -> {store_unsigned(value, width)}")

    rule("5 · floats")
    print("  ", float_facts())


if __name__ == "__main__":
    main()
