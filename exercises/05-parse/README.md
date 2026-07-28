# 05 · Parse — the agreement, honoured or not

**Dependencies:** `pymupdf`, `pdfplumber`.
Needs the documents: `python data/fetch.py --only pdfs`.

```sh
python exercises/05-parse/starter.py     # run yours
python exercises/05-parse/verify.py      # check it
python exercises/05-parse/solution.py    # read afterwards
```

## TODO 1 — honour a simple agreement by hand

CSV's agreement, in full:

- fields are separated by commas
- a field may be wrapped in double quotes
- inside quotes, a comma is data, not a separator
- inside quotes, two double quotes in a row mean one literal double quote
- an empty field is an empty string, not `None`

Walk the line one character at a time. Don't use the `csv` module — the point is that
you *can* write this, because the agreement records structure.

For `INV-10007,"Acme Corp, Ltd.",3,"He said ""ship it""",1240.50,` the answer is:

```
['INV-10007', 'Acme Corp, Ltd.', '3', 'He said "ship it"', '1240.50', '']
```

Then parse the same data as JSON with the standard library and say what *its*
agreement is.

## TODO 2 — look for the text in a PDF's bytes, and fail

Open a PDF as raw bytes. Count how many times a word you can see on the page appears
in them. Report the number honestly.

## TODO 3 — measure how far two libraries disagree

Given two extractions of the same document, return:

| key | meaning |
|---|---|
| `char_ratio` | `difflib.SequenceMatcher(None, a, b).ratio()` — 1.0 is identical |
| `same_words` | whether `sorted(a.split()) == sorted(b.split())` |
| `only_in_a` | words in a but not b |
| `only_in_b` | words in b but not a |

`same_words` matters. The same words in a different order is a different failure from
missing words, and you will see both.

## What you should be able to say afterwards

- Why two correct CSV parsers cannot disagree, and two correct PDF parsers routinely do.
- What a PDF page actually stores, in terms of the operators in its content stream.
- Why extraction quality is a variable in your pipeline rather than a settled step.
