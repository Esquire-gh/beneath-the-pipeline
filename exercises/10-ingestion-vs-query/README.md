# 10 · Keeping the index fresh as documents arrive

**Dependencies: none** beyond the standard library.

```sh
python exercises/10-ingestion-vs-query/starter.py --scale small
python exercises/10-ingestion-vs-query/verify.py
python exercises/10-ingestion-vs-query/solution.py --scale small
```

## TODO 1 — search across every segment

No single segment knows about the whole corpus, so a query consults all of them and
combines the answers. Return the sorted unique document ids and how many segments you
touched. That second number is the **fanout**.

## TODO 2 — merge two segments

Merge their posting lists term by term. Build the result directly from the merged
postings rather than re-tokenizing — though re-tokenizing works too, and being slower
is itself part of the lesson.

## TODO 3 — a merge policy

Bucket segments by size tier (`log(n_docs, fan)`), and merge any tier with `fan` or
more members. Return the new segment list and how many documents the merges rewrote.

Bucket by *tier*, not by exact document count, or two batches differing by one document
will never merge.

## TODO 4 — write the index down

You are the format author now. Header, all little-endian:

| offset | width | meaning |
|---|---|---|
| 0 | 4 | magic bytes `BTP1` |
| 4 | 2 | format version |
| 6 | 2 | flags |
| 8 | 4 | number of terms |

Then per term: 2-byte length, UTF-8 term bytes, 4-byte posting count, then that many
4-byte document ids.

`read_index` is written for you. Read it before you write `write_index` — it tells you
exactly what the bytes have to look like.

## Then look at the compatibility matrix the solution prints

Four rows: old reader with old data, old reader with new data, new reader with old
data, new reader with new data. All four should behave deliberately. Work out why
version 2 *appending* a section rather than inserting one is what makes that possible.

## What you should be able to say afterwards

- Why "never modify a written file" leads to segments, and segments lead to merging.
- What write amplification is, in terms of the rewritten column.
- Why the fastest-query policy and the cheapest-ingestion policy can never be the same.
- What `pickle` costs you that forty lines of `struct` does not.
