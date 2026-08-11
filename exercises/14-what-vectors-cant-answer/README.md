# 14 · What vectors can't answer

**Dependencies:** `pymupdf`, `sentence-transformers`, `numpy`. `sqlite3` is stdlib.
Needs the corpus: `python data/fetch.py --only invoices`.

```sh
python exercises/14-what-vectors-cant-answer/starter.py
python exercises/14-what-vectors-cant-answer/verify.py
python exercises/14-what-vectors-cant-answer/solution.py
```

The corpus is 300 invoices rendered to PDF. Every fact about it is *known* because the
generator wrote the numbers before it drew the pages. The PDFs are the only input to the
pipeline; `ground_truth.json` is only ever used for scoring.

## TODO 1 — design a schema and extract into it

Which fields does a record hold? Are line items their own table?

This is module 2's lesson with you on the authoring side. **Every field you leave out is
a question the table can never answer.**

Grade your extractor against the ground truth before going further. An argument about
what retrieval cannot do is worthless if the data was mangled on the way in.

## TODO 2 — load the records into SQLite

Two tables: `invoices` and `line_items`. Nothing exotic.

## TODO 3 — answer the aggregate questions with SQL

`ground_truth.json` gives each aggregate question a `sql_hint` naming the operation it
wants. Write the queries.

## TODO 4 — evidence coverage

How do you grade a *retriever* on "how many invoices exceed $10,000" without inventing
an answer for it?

Measure what fraction of the documents needed to answer actually came back. To count
invoices over a threshold you need to see all of them; a top-4 retrieval can show you
four. That ratio is the honest number, and it needs no language model.

## TODO 5 — the router

Rules, not a model. A dozen words — "how many", "total", "average", "largest",
"exceed" — and then measure how often they are right.

Note which way your router errs. Sending a descriptive question to SQL loses you a good
answer; sending an aggregate to the retriever produces a confident wrong one. Those are
not equally bad.

## What you should be able to say afterwards

- What an embedding promises, and why counting is not covered by it.
- Why raising `k` does not turn a retriever into a calculator.
- What a record has that an index does not, and when you need a graph instead.
- Why the routing decision is really an ingestion decision.
