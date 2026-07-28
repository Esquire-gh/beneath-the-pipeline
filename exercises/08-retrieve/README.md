# 08 · Retrieve — ranked by what?

**Dependencies:** `numpy`, `sentence-transformers`.
Needs the corpus and its judgments: `python data/fetch.py --only msmarco`.

```sh
python exercises/08-retrieve/starter.py --queries 200
python exercises/08-retrieve/verify.py
python exercises/08-retrieve/solution.py --scale part2 --queries 1000
```

## TODO 1 — raw term counts

Add up how often each query word appears in each document. The obvious thing. Run it
and look at what it likes.

## TODO 2 — tf-idf

Two fixes:

```
tf_weight = 1 + log(tf)          # the tenth occurrence counts for less than the first
idf       = log(N / df)          # a word in every document tells you nothing
score     = sum(tf_weight * idf) / sqrt(doc_len)
```

## TODO 3 — BM25

The same ideas, tuned by forty years of measurement:

```
idf(t) = log(1 + (N - df + 0.5) / (df + 0.5))
score += idf(t) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len/avgdl))
```

`k1` (usually 1.2) controls how fast extra occurrences stop helping.
`b` (usually 0.75) controls how hard long documents are penalised; `b=0` turns the
length penalty off.

Keep the `1 +` inside the idf logarithm. Without it, terms appearing in more than half
the corpus get *negative* weight and scramble the ranking.

## TODO 4 — precision@k

The fraction of the top k that are relevant. If fewer than k results came back, still
divide by k — three good results out of a requested ten is not perfect precision.

## TODO 5 — NDCG@k

Precision does not care whether the answer was first or tenth. NDCG does:

```
DCG  = sum over positions i (from 1) of  relevance(i) / log2(i + 1)
IDCG = the DCG of the best possible ranking
NDCG = DCG / IDCG,  or 0.0 when there is nothing relevant to find
```

## Then run the solution and watch the last section

It tries four changes that all sound like improvements. Predict which ones help before
you look. Most people get this wrong, which is the entire reason the harness exists.

## What you should be able to say afterwards

- Why weighting by rarity is worth more than any amount of counting.
- What NDCG measures that precision does not.
- Why "this change made results better" is not a claim you can make without judgments.
- What a judgment set does *not* tell you.
