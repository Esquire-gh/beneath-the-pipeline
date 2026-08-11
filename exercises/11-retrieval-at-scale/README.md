# 11 · How ranking stays fast at scale

**Dependencies:** `numpy`.
Needs the corpus: `python data/fetch.py --only msmarco`.

```sh
python exercises/11-retrieval-at-scale/starter.py --scale small --queries 60
python exercises/11-retrieval-at-scale/verify.py
python exercises/11-retrieval-at-scale/solution.py --scale part2 --queries 200
```

## TODO 1 — document at a time

Module 8 scored *term* at a time and needed a score map over every document any term
touched. Do it *document* at a time: walk all the posting lists together in document
order, finish each document, keep a heap of the best k. No score map.

**Tie-breaking matters.** When two documents score equally, every strategy here must
order them the same way, or "the same answer" means nothing. Compare the whole tuple
`(score, -doc)`, not just the score.

## TODO 2 — skip pointers

Fill in `Cursor.advance_skipping`. Posting lists are sorted, so look `stride` entries
ahead: if the value there is still below your target, move the whole block without
reading inside it. Count every look as one touched posting — a skip is cheap, not free.

Advancing to `current + 1` can never skip anything. Skipping only pays when the target
is far away, which is what TODO 3 produces.

## TODO 3 — WAND

`index.upper[term]` is the largest score any single document could get from that term,
computed once at build time.

Keep the k best scores; the worst is your **threshold**. Then repeatedly:

1. sort live cursors by the document they are on
2. accumulate upper bounds down that list; the first cursor where the running total
   exceeds the threshold is the **pivot**
3. if there is no such cursor, nothing left can beat the top k — stop
4. if the first cursor is already on the pivot's document, so is everything before it:
   score that document and advance past it
5. otherwise advance one lagging cursor **up to** the pivot without scoring anything

Update the threshold whenever the heap changes.

## All three must return the same answer

The starter checks this and prints `same answer n/n`. It is not a formality — writing
this module produced a WAND that was faster and wrong, and only the cross-check caught
it. A faster wrong answer is not a result.

## What you should be able to say afterwards

- What an upper bound is and why pruning with one is *sound* rather than approximate.
- Why documents-scored fell far more than postings-touched.
- Why p99 got worse relative to the median, and why production teams watch the tail.
