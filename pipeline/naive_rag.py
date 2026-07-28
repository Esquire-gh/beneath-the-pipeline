#!/usr/bin/env python3
"""The naive RAG pipeline, exactly as the internet teaches it.

    python pipeline/naive_rag.py "what does the paper say about attention?"

It works. For a demo, this is fine. Every line of it is also a promise you
have not checked, which is what the rest of the site is about.

Needs: pymupdf, sentence-transformers, chromadb.
"""
import sys
from pathlib import Path

import chromadb
import fitz                                     # PyMuPDF
from sentence_transformers import SentenceTransformer

PDF_DIR = Path(__file__).parent / "sample_pdfs"


# --- BEGIN PIPELINE -------------------------------------------------------

def load(pdf_dir):
    return [(p.name, fitz.open(p)) for p in sorted(pdf_dir.glob("*.pdf"))]


def parse(docs):
    return [(name, "\n".join(page.get_text() for page in doc))
            for name, doc in docs]


def split(parsed, size=1000, overlap=200):
    chunks = []
    for name, text in parsed:
        for i in range(0, len(text), size - overlap):
            chunk = text[i:i + size].strip()
            if chunk:
                chunks.append({"source": name, "text": chunk})
    return chunks


def embed(chunks, model):
    return model.encode([c["text"] for c in chunks], batch_size=64)


def index(chunks, vectors):
    db = chromadb.Client().create_collection("docs", get_or_create=True)
    db.add(ids=[str(i) for i in range(len(chunks))],
           embeddings=[v.tolist() for v in vectors],
           documents=[c["text"] for c in chunks],
           metadatas=[{"source": c["source"]} for c in chunks])
    return db


def retrieve(db, model, question, k=4):
    q = model.encode([question])[0].tolist()
    hits = db.query(query_embeddings=[q], n_results=k)
    return list(zip(hits["documents"][0], hits["metadatas"][0]))


def prompt_for(question, passages):
    context = "\n\n".join(f"[{m['source']}] {d}" for d, m in passages)
    return (f"Answer using only the context below.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\nAnswer:")

# --- END PIPELINE ---------------------------------------------------------


def run(question, pdf_dir=PDF_DIR, model_name="all-MiniLM-L6-v2"):
    model = SentenceTransformer(model_name)
    docs = load(pdf_dir)
    parsed = parse(docs)
    chunks = split(parsed)
    vectors = embed(chunks, model)
    db = index(chunks, vectors)
    return prompt_for(question, retrieve(db, model, question))


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else \
        "what does the paper say about attention?"
    print(run(question))
