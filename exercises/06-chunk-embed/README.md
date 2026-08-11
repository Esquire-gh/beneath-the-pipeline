# 06 · Chunk & Embed — how text becomes vectors

**Dependencies:** `sentence-transformers`, `numpy`.
Needs the corpus: `python data/fetch.py --only msmarco --small`.

```sh
python exercises/06-chunk-embed/starter.py     # run yours
python exercises/06-chunk-embed/verify.py      # check it
python exercises/06-chunk-embed/solution.py    # read afterwards
```

The first run downloads the embedding model (~90 MB). After that it is offline.

## TODO 1 — fixed-size chunking

Cut text into pieces of `size` characters, each starting `size - overlap` after the
last. Return `{"start", "end", "text"}` per chunk. Keeping the offsets is the only
addition to what the Part 0 pipeline does, and it is what makes TODO 4 possible.

## TODO 2 — sentence-boundary chunking

Split into sentences, then pack whole sentences up to `max_chars`. Never cut a
sentence.

Your sentence rule will be wrong for `Dr. Smith` and for `3.14`. Being wrong in a
knowable way beats being wrong in an unknowable one — write the rule down.

## TODO 3 — cosine similarity, by hand

```
cosine(a, b) = sum(a[i]*b[i]) / (sqrt(sum(a[i]^2)) * sqrt(sum(b[i]^2)))
```

No library. About five lines. `verify.py` checks it against numpy on 384 dimensions.

## TODO 4 — find what the chunker broke

Return the boundaries that landed inside a word, with the word reassembled from the
text either side of the cut.

## Then run the solution and look at two things

1. The chunk boundary it finds in `gen-tables.pdf` — a table row cut in half.
2. The similarity between `the cat sat on the mat` and `the cat did not sit on the
   mat`. Compare it with the paraphrase score before you read the module page.

## What you should be able to say afterwards

- Why chunking is a decision rather than a default.
- What an embedding promises, stated in one sentence, and what it does not.
- Why a negation can score higher than a paraphrase.
