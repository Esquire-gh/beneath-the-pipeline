#!/usr/bin/env python3
"""Time Part 0's pipeline, stage by stage, and record what it produced.

Not an exercise — there is nothing to fill in here. This runs the pipeline the
site opens with and captures the numbers the index page prints, so that even
the demo's figures are measured rather than asserted.

    python exercises/00-pipeline/measure.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "exercises"))

from common import human_bytes, human_time, rule, timed, write_measurements  # noqa: E402

SLUG = "00-pipeline"


def count_pipeline_lines() -> dict:
    """How long is 'thirty lines', exactly?

    Counted from the file, between the two markers, so the claim on the page
    stays true if the code changes.
    """
    src = (REPO / "pipeline" / "naive_rag.py").read_text().splitlines()
    start = next(i for i, l in enumerate(src) if "BEGIN PIPELINE" in l)
    end = next(i for i, l in enumerate(src) if "END PIPELINE" in l)
    body = src[start + 1:end]
    code = [l for l in body if l.strip() and not l.strip().startswith("#")]
    return {"total_lines": len(body), "code_lines": len(code)}


def main() -> None:
    import fitz
    from sentence_transformers import SentenceTransformer

    sys.path.insert(0, str(REPO / "pipeline"))
    import naive_rag as nr

    pdf_dir = REPO / "pipeline" / "sample_pdfs"
    question = "what does the paper say about attention?"

    rule("Part 0 — the naive pipeline, timed")
    m = {"question": question,
         "pdf_dir": str(pdf_dir.relative_to(REPO)),
         "pipeline_lines": count_pipeline_lines()}

    with timed("load the embedding model") as t:
        model = SentenceTransformer("all-MiniLM-L6-v2")
    m["model_load_seconds"] = t["seconds"]
    m["model_name"] = "all-MiniLM-L6-v2"

    with timed("load()   — open the PDFs") as t:
        docs = nr.load(pdf_dir)
    m["load_seconds"] = t["seconds"]
    m["n_pdfs"] = len(docs)
    m["pdf_bytes"] = sum(p.stat().st_size for p in pdf_dir.glob("*.pdf"))
    m["n_pages"] = sum(len(d) for _, d in docs)

    with timed("parse()  — pages to text") as t:
        parsed = nr.parse(docs)
    m["parse_seconds"] = t["seconds"]
    m["n_chars"] = sum(len(t_) for _, t_ in parsed)

    with timed("split()  — text to chunks") as t:
        chunks = nr.split(parsed)
    m["split_seconds"] = t["seconds"]
    m["n_chunks"] = len(chunks)
    m["chunk_size"] = 1000
    m["chunk_overlap"] = 200
    m["mean_chunk_chars"] = sum(len(c["text"]) for c in chunks) / len(chunks)

    with timed("embed()  — chunks to vectors") as t:
        vectors = nr.embed(chunks, model)
    m["embed_seconds"] = t["seconds"]
    m["n_vectors"] = len(vectors)
    m["dims"] = int(vectors.shape[1])
    m["vector_bytes"] = int(vectors.nbytes)

    with timed("db.add() — build the index") as t:
        db = nr.index(chunks, vectors)
    m["index_seconds"] = t["seconds"]

    with timed("retrieve() — one query") as t:
        hits = nr.retrieve(db, model, question)
    m["retrieve_seconds"] = t["seconds"]
    m["k"] = len(hits)

    m["total_seconds"] = sum(m[k] for k in (
        "model_load_seconds", "load_seconds", "parse_seconds", "split_seconds",
        "embed_seconds", "index_seconds", "retrieve_seconds"))
    m["pipeline_seconds"] = m["total_seconds"] - m["model_load_seconds"]
    m["top_hit_source"] = hits[0][1]["source"]
    m["top_hit_excerpt"] = " ".join(hits[0][0].split())[:220]
    m["sources"] = sorted({c["source"] for c in chunks})

    rule("what came out")
    print(f"  {m['n_pdfs']} PDFs, {m['n_pages']} pages, "
          f"{human_bytes(m['pdf_bytes'])} on disk")
    print(f"  {m['n_chars']:,} characters of text")
    print(f"  {m['n_chunks']:,} chunks -> {m['n_vectors']:,} vectors of "
          f"{m['dims']} floats ({human_bytes(m['vector_bytes'])})")
    print(f"  whole pipeline, model load excluded: "
          f"{human_time(m['pipeline_seconds'])}")
    print(f"  top hit came from {m['top_hit_source']}")

    path = write_measurements(SLUG, m)
    print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
