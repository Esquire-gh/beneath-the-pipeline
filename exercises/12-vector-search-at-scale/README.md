# 12 · How vector search scales

**Dependencies:** `hnswlib`, `numpy`, `sentence-transformers`.
Needs the corpus and cached vectors: `python data/fetch.py --only msmarco`.

```sh
python exercises/12-vector-search-at-scale/starter.py --scale part2
python exercises/12-vector-search-at-scale/verify.py
python exercises/12-vector-search-at-scale/solution.py --scale big
```

`--scale big` embeds and indexes 1,000,000 vectors. The HNSW build alone takes a few
minutes and the graph needs a couple of gigabytes. `--scale part2` is the laptop-safe
default.

If `pip install hnswlib` fails on macOS with `fatal error: 'iostream' file not found`,
see the note at the bottom of `requirements.txt` — it compiles C++ and needs the libc++
headers on the compiler's search path.

## TODO 1 — brute force

Score the query against every vector, return the top k. You cannot say an index is 90%
correct until you have the 100% to compare it against.

## TODO 2 — build an HNSW index

```python
index = hnswlib.Index(space="ip", dim=dims)   # unit-length vectors, so inner
                                              # product IS cosine similarity
index.init_index(max_elements=n, ef_construction=200, M=16)
index.add_items(vectors, numpy.arange(n))
index.set_ef(ef_search)                       # the knob — set per query
```

`M` and `ef_construction` are build-time. `ef_search` is the one you can change
afterwards, which is why it is the knob that matters.

## TODO 3 — recall@k

```
recall = |approx[:k] ∩ truth[:k]| / k
```

Order does not matter. This asks whether the index *found* the right documents;
module 8's NDCG asks whether they were worth finding. The two can disagree, and the
solution shows a case where they do.

## Then run the solution and look at section 5

A filter matching 1% of documents. Predict what happens to the graph before you look.

## What you should be able to say afterwards

- Why an approximate index needs a recall number next to it and WAND does not.
- What `ef_search` buys and what it costs, in both recall and latency.
- Why post-filtering an ANN index collapses, and when to scan instead.
- What Part 0's `db.add()` chose for you.
