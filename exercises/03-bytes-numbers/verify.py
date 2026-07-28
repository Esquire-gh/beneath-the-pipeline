#!/usr/bin/env python3
"""Check your starter.py against what the format actually says.

    python exercises/03-bytes-numbers/verify.py

Every failure names the offset or the width it was checking, so you can go
back to the table in starter.py rather than guessing.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import rule   # noqa: E402


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    yours = load("starter")
    ref = load("solution")

    tmp = HERE / "_scratch"
    tmp.mkdir(exist_ok=True)
    data = ref.make_wav(tmp / "verify.wav").read_bytes()

    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))

    # ---- TODO 1 ----------------------------------------------------------
    try:
        got = yours.hexdump(data[:48])
        want = ref.hexdump(data[:48])
        ok = isinstance(got, list) and all(isinstance(x, str) for x in got)
        check("hexdump returns a list of strings", ok,
              f"got {type(got).__name__}")
        if ok:
            check("hexdump produced one row per 16 bytes",
                  len(got) == len(want), f"{len(got)} rows, expected {len(want)}")
            check("row 0 matches the reference layout",
                  got and got[0] == want[0],
                  f"\n         yours: {got[0] if got else '(nothing)'}"
                  f"\n         ref:   {want[0]}")
            short = yours.hexdump(data[:20])
            check("a short final row still lines up",
                  len(short) == 2 and short[1] == ref.hexdump(data[:20])[1],
                  f"\n         yours: {short[1] if len(short) > 1 else '(missing)'}"
                  f"\n         ref:   {ref.hexdump(data[:20])[1]}")
    except Exception as e:
        check("hexdump runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 2 ----------------------------------------------------------
    try:
        got = yours.parse_wav_header(data)
        want = ref.parse_wav_header(data)
        check("parse_wav_header returns a dict", isinstance(got, dict),
              f"got {type(got).__name__}")
        if isinstance(got, dict):
            for field, expected in want.items():
                check(f"field '{field}' read correctly",
                      got.get(field) == expected,
                      f"yours {got.get(field)!r}, expected {expected!r} "
                      f"(offset {ref.WAV_FIELDS[field][0]}, "
                      f"width {ref.WAV_FIELDS[field][1]})")
    except Exception as e:
        check("parse_wav_header runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 3 ----------------------------------------------------------
    try:
        got = yours.parse_wav_header(data, endian=">")
        want = ref.parse_wav_header(data, ">")
        check("the endian argument is honoured, not ignored",
              got.get("sample_rate") == want["sample_rate"],
              f"flipped sample_rate {got.get('sample_rate')!r}, "
              f"expected {want['sample_rate']!r} — if it matches the "
              f"little-endian value, the argument is not being used")
    except Exception as e:
        check("parse_wav_header honours endian", False, f"{type(e).__name__}: {e}")

    try:
        for value, width in ((200, 1), (256, 1), (300, 1), (70000, 2), (70000, 4)):
            got = yours.store_unsigned(value, width)
            want = ref.store_unsigned(value, width)
            check(f"store_unsigned({value}, {width})", tuple(got) == tuple(want),
                  f"yours {tuple(got)}, expected {tuple(want)} "
                  f"(max for {width} byte(s) is {256 ** width - 1})")
    except Exception as e:
        check("store_unsigned runs", False, f"{type(e).__name__}: {e}")

    # ---- TODO 4 ----------------------------------------------------------
    try:
        got = yours.float_facts()
        want = ref.float_facts()
        check("float_facts returns a dict", isinstance(got, dict),
              f"got {type(got).__name__}")
        if isinstance(got, dict):
            check("0.1 + 0.2 does not equal 0.3",
                  got.get("equals_point_three") is False,
                  f"got {got.get('equals_point_three')!r}")
            check("the sum is the one Python actually produces",
                  got.get("sum") == want["sum"],
                  f"yours {got.get('sum')!r}, expected {want['sum']!r}")
            check("0.1's eight bytes are right",
                  got.get("as_bytes") == want["as_bytes"],
                  f"yours {got.get('as_bytes')!r}, expected {want['as_bytes']!r}")
            check("the exact stored value is captured",
                  str(got.get("exact", "")).startswith("0.1000000000000000055"),
                  f"got {got.get('exact')!r}")
    except Exception as e:
        check("float_facts runs", False, f"{type(e).__name__}: {e}")

    rule("module 3 — your work against the format's own rules")
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}")
        if detail and not ok:
            print(f"         {detail}")
        failed += 0 if ok else 1

    print()
    if failed:
        print(f"{failed} of {len(checks)} checks failed. Each one names the "
              f"offset or width it was reading.")
    else:
        print(f"all {len(checks)} checks pass. Now read solution.py and "
              f"compare it with yours.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
