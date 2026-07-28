# 00 · The pipeline, working

**Dependencies:** `pymupdf`, `sentence-transformers`, `chromadb`.
Needs the sample PDFs: `python data/fetch.py --only pdfs`.

This is not an exercise. It is the thirty lines the site opens with, so you can run
them and see that they work before anything takes them apart.

```sh
python pipeline/naive_rag.py "what does the paper say about attention?"
```

That prints the prompt the pipeline would send to a language model: your question, and
the four passages it decided were most relevant. No model is called — the retrieval is
the part this site is about.

## Timing it

```sh
python exercises/00-pipeline/measure.py
```

Times each stage separately, counts what came out of each, and writes
`measurements.json`. The index page prints those numbers, so even the demo's figures are
measured rather than asserted.

## The one thing worth doing here

Read `pipeline/naive_rag.py` and, for each of its six functions, write down one sentence
saying what it assumes. Then compare your list with the inventory on the index page.

Anything on that page you did not think to write down is a floor you did not know was
under you — and it names the module that lays it.
