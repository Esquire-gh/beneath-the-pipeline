# 02 · Data is bytes by agreement — text

**Dependencies: none.** Shell and the Python standard library.
`xxd` ships with macOS and most Linux systems; where it doesn't, `hexdump -C` prints
the same information.

## 1 · Eight bytes with no meaning of their own

```python
raw = bytes([0x48, 0x65, 0x6c, 0x6c, 0x6f, 0x21, 0x00, 0x2a])

print(raw.decode("ascii", "replace"))                 # as text
print(int.from_bytes(raw[:4], "little"))              # as a number
print(int.from_bytes(raw[:4], "big"))                 # as a different number
import struct; print(struct.unpack("<d", raw)[0])     # as one decimal number
```

Four readings, all correct. Which one is *the* meaning? There isn't one.

## 2 · Look at text as bytes

```sh
printf 'Hello, floor.\n' > plain.txt

xxd plain.txt          # or: hexdump -C plain.txt
```

Three columns: offset, bytes in hex, and those bytes as characters where a character
exists. Find `48` and check it against an ASCII table.

## 3 · One character is not one byte

```python
for ch in "A", "é", "→", "🧱":
    print(ch, len(ch), len(ch.encode("utf-8")), ch.encode("utf-8").hex(" "))

print(len("café"), len("café".encode()))
```

Then the three lengths of one glyph:

```python
astronaut = "👩‍🚀"
print(len(astronaut), len(astronaut.encode()))   # characters, bytes — and 1 on screen
```

## 4 · Break the agreement

```python
raw = "café".encode("utf-8")
print(raw.decode("utf-8"))      # the agreement honoured
print(raw.decode("latin-1"))    # the same bytes, a different agreement
```

No error. Different words. Now make it fail:

```python
open("broken.txt", "wb").write(b"caf\xe9\n")   # written as Latin-1
open("broken.txt", encoding="utf-8").read()    # read as UTF-8
```

## 5 · A file format is the same agreement, grown large

```sh
xxd -l 32 one.png                                    # hexdump -C -n 32 one.png
xxd -l 32 pipeline/sample_pdfs/gen-clean-1col.pdf
file notes.txt          # the renamed PNG from module 1
```

Every PNG starts with the same eight bytes. Every PDF starts with `%PDF-`. `file`
reads those openings and answers from them — never from the name.

---

## Run it all, and record the numbers

```sh
python exercises/02-bytes-text/investigate.py
python exercises/02-bytes-text/verify.py
```

## What you should be able to say afterwards

- Why a byte has no meaning until someone supplies a convention.
- Why "the length of a string" is three different questions.
- What mojibake actually is, mechanically.
- Why "what makes a PDF a PDF" is a statement about agreements, not about storage.
