# 09 · When the index doesn't fit in memory

**Dependencies: none** beyond the standard library.
Needs the corpus: `python data/fetch.py --only msmarco`.

```sh
python exercises/09-index-that-doesnt-fit/starter.py --scale small
python exercises/09-index-that-doesnt-fit/verify.py
python exercises/09-index-that-doesnt-fit/solution.py --scale part2
```

`--scale big` runs the full 1,000,000-passage curve and takes a few minutes.

## TODO 1 — gaps

A posting list is sorted, so store the differences instead of the ids:

```
ids   [3, 17, 18, 92, 415, 416, 417]
gaps  [3, 14,  1, 74, 323,   1,   1]
```

Nothing is lost, and the numbers get much smaller.

## TODO 2 — varbyte

Write those small numbers in as few bytes as each needs. Seven bits of the value per
byte, low bits first; the high bit of a byte means "this is the last byte of this
number".

```
3    -> 1 byte
200  -> 2 bytes
```

The continuation bit marks the **last** byte, not the first. That is the usual bug.

## TODO 3 — build in blocks (SPIMI)

Read documents one at a time. Accumulate postings until you have `block_size`
documents, write that block to disk sorted by term, throw the dict away, continue.

Peak memory is then set by `block_size`, not by the corpus.

## TODO 4 — merge the sorted runs

Every block is sorted by term, so merge them without loading any of them: always take
the smallest term available, and join the posting lists when several blocks carry the
same term. `heapq.merge` does exactly this.

## What you should be able to say afterwards

- Why streaming the corpus is a precondition, not an optimisation.
- Why gaps alone save nothing, and what has to change for them to pay.
- What compression charges you back, and when that is a good deal.
- Where SPIMI's remaining memory cost is, and what a production system does about it.
