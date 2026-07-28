# 03 · Data is bytes by agreement — numbers

**Dependencies: none.** Python standard library only (`struct`, `wave`, `decimal`).

This is the first module where you write code rather than run commands.

```sh
python exercises/03-bytes-numbers/starter.py    # run yours
python exercises/03-bytes-numbers/verify.py     # check it
python exercises/03-bytes-numbers/solution.py   # read afterwards
```

## TODO 1 — a hex dump tool, in about 30 lines

Return one string per 16 bytes, laid out like `xxd`:

```
00000000  52 49 46 46 68 ac 00 00  57 41 56 45 66 6d 74 20  |RIFFh...WAVEfmt |
^offset   ^ hex, with a gap after eight bytes               ^ printable ASCII
```

Bytes 32–126 print as their character; everything else prints as a dot. Pad the hex
column so a short final row still lines up.

## TODO 2 — read a WAV header from its written agreement

The starter writes a real WAV file with the standard library, so the bytes you parse
were produced by something other than your parser. Read these fields:

| offset | width | meaning | how |
|---|---|---|---|
| 0 | 4 | the letters `RIFF` | ASCII |
| 8 | 4 | the letters `WAVE` | ASCII |
| 22 | 2 | channels | unsigned 16-bit, low byte first |
| 24 | 4 | sample rate | unsigned 32-bit, low byte first |
| 34 | 2 | bits per sample | unsigned 16-bit, low byte first |

`struct.unpack_from("<H", data, 22)` reads a little-endian unsigned 16-bit value at
offset 22. `<I` is the 32-bit version; `>` is the same widths, high byte first.

Do not hard-code the `<` — TODO 3 depends on the `endian` argument being used.

## TODO 3 — flip the byte order

Call your parser with `endian=">"`. The bytes on disk do not move. Watch which fields
break and which survive, and be able to say why the text fields came through intact.

## TODO 4 — break integers and floats deliberately

Store values in 1, 2 and 4 bytes and find where each width stops working. Then look at
`0.1 + 0.2`, at the eight bytes of `0.1`, and at the exact decimal Python stored —
`Decimal(0.1)`, passing the float, not the string.

## What you should be able to say afterwards

- Why reading a field needs three facts, not one: offset, width, and byte order.
- Why a wrong byte order gives a plausible wrong answer instead of an error.
- What overflow is, and why hardware does it silently.
- Why `0.1` is not 0.1, and what that means for a similarity score computed from
  384 of them.
