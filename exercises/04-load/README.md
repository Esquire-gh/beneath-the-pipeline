# 04 · Load — what reading a file costs

**Dependencies: none** beyond the standard library.
Needs the corpus: `python data/fetch.py --only corpus`. This unpacks
`data/corpus_small.zip`, which ships with the repo — about a second, no download.

```sh
python exercises/04-load/starter.py     # run yours
python exercises/04-load/verify.py      # check it
python exercises/04-load/solution.py    # read afterwards
```

## Read this first: the counter

Your program cannot touch the disk. It asks the operating system to, and every ask is
a **syscall** — a function call with a border crossing inside it. The `Crossings` class
at the top of `starter.py` wraps `os.open`, `os.read` and `os.close` and counts them.
It does nothing else.

Use `c.open` / `c.read` / `c.close`, never `os.*` directly, or nothing gets counted.

## TODO 1 — read the corpus one file at a time

Open each of the 10,000 files, read all of it, close it. Return total bytes.

`os.read(fd, n)` returns *at most* `n` bytes and returns `b""` at end of file, so
reading a whole file means looping until you get `b""`.

## TODO 2 — read one large file in small pieces

`data/corpus_small/all.txt` holds the same bytes as those 10,000 files. Open it once
and ask for 4 KB at a time. This is what "line by line" costs underneath.

## TODO 3 — read the same file in as few asks as you can

Same file, 4 MB at a time. Nothing else changes.

## Predict before you run the solution

The solution adds a fourth strategy: the same 10,000 files, read with the 4 MB buffer.
Write down what you expect it to do before you look.

## What you should be able to say afterwards

- Why the cost of loading tracks the number of asks, not the number of bytes.
- What `open()` actually does, in terms of module 1's bookkeeping.
- Why a bigger buffer helps one large file and hurts ten thousand small ones.
- Why the page cache means most of what you measured was not the disk at all.
