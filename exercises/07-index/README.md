# 07 · Index — how search gets fast

**Dependencies:** `numpy` (and `sentence-transformers` for the cached vectors).
Needs the corpus: `python data/fetch.py --only msmarco`.

```sh
python exercises/07-index/starter.py --scale small
python exercises/07-index/verify.py
python exercises/07-index/solution.py --scale part2
```

`--scale small` is 50,000 passages and runs on a laptop. The module page's numbers come
from `--scale part2`, which is 100,000.

## TODO 1 — tokenize

Lowercase, then pull out runs of letters and digits.

This must be the **same function** for indexing and for searching. Index `Block` and
search `block` and the index will confidently report no matches. Most "the index is
broken" bugs are this.

## TODO 2 — the scan

Find a word by reading every passage, every time. This is the honest baseline, it is
what `grep` does, and it always works.

## TODO 3 — the inverted index

Build `word -> sorted list of passage ids`. That list is a **posting list**.

Sort each list, and store each id **once**. Both matter later: module 9 compresses
these lists and needs them sorted; module 11 skips through them and needs no
duplicates.

## TODO 4 — brute-force nearest neighbour

Every vector already has length 1, so cosine similarity is just a dot product. Score
the query against every row and return the top k. One matrix multiply.

## Then run the solution and read three numbers

1. How much bigger the index is than the corpus it indexes.
2. How long the build took — work moved off the query path.
3. The cost per query of the brute-force vector search. At 100,000 it is fine.

## What you should be able to say afterwards

- What an index is, in one sentence, without using the word "index".
- The three places an index costs you: build time, memory, and staying current.
- Why a word index and a vector index fail in different ways.
