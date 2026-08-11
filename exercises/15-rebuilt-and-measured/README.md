# 15 · The pipeline, rebuilt and measured

**Dependencies:** `pymupdf`, `pdfplumber`, `pytesseract` + Tesseract,
`sentence-transformers`, `numpy`.

```sh
python data/make_eval_docs.py          # the 20 documents with known text
python exercises/15-rebuilt-and-measured/solution.py --scale part2
```

The first run downloads a cross-encoder (~90 MB).

## Part 1 — assemble it from your own parts

Module 8's BM25. Module 6's embeddings. Module 7's index. Module 8's harness.

Then two additions:

**Reciprocal rank fusion.** BM25 scores and cosine similarities are not comparable —
different scales entirely. Ranks are. A document's fused score is the sum of
`1/(60 + its rank)` across the lists.

**A cross-encoder rerank over the top 50.** A model that reads query and document
*together*. That is why it is accurate, and why it cannot be an index: there is nothing
to precompute, so it can only reorder a shortlist something cheaper produced.

Measure NDCG at each stage. **Predict the four numbers before you run it.** One of them
is likely to surprise you, and that surprise is module 8's lesson arriving one last
time.

## Part 2 — the reckoning

`data/make_eval_docs.py` writes 20 documents whose true text is known, in four layouts,
half of them printed to images the way a scanner would.

Run the *entire* pipeline three times — extract, chunk, embed, index, retrieve, rerank,
evaluate — changing only which program turns the PDFs into text:

1. PyMuPDF
2. pdfplumber
3. PyMuPDF, falling back to OCR when it returns nothing

Then compare two spreads: the range across extractors, and the range across retrieval
architectures. Look at the "documents with no text" column before you look at anything
else.

## What you should be able to say afterwards

- Why fusion is not automatically an improvement.
- Why a reranker has to be a second stage.
- Which single measurement you would add to an ingestion pipeline tomorrow.
- Why the pipeline's quality is decided upstream of everything you tuned.
