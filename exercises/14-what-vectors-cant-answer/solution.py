#!/usr/bin/env python3
"""Module 14 — worked solution, and the source of the module page's numbers.

    python exercises/14-what-vectors-cant-answer/solution.py

Every fact in this corpus is known, because the generator wrote it. So both
kinds of question can be graded exactly:

    descriptive   "which invoice from Acme includes a servo motor?"
                  the answer is a document — which is what a retriever returns
    aggregate     "how many invoices exceed $10,000?"
                  the answer is a number nobody wrote down

Needs: pymupdf, sentence-transformers, numpy. sqlite3 is in the standard library.
"""
import argparse
import json
import math
import re
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "exercises"))

from common import human_time, normalized, rule, write_measurements   # noqa: E402

SLUG = "14-what-vectors-cant-answer"
INVOICES = REPO / "data" / "invoices"
TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


# --------------------------------------------------------------------------
# 1 · parse the PDFs — the pipeline's only input
# --------------------------------------------------------------------------

def parse_invoices() -> dict[str, str]:
    import fitz
    out = {}
    for path in sorted((INVOICES / "pdf").glob("*.pdf")):
        with fitz.open(path) as doc:
            out[path.stem] = "\n".join(page.get_text() for page in doc)
    return out


# --------------------------------------------------------------------------
# 2 · a schema you design, and an extractor that fills it
# --------------------------------------------------------------------------
#
# Module 2 said a format is an agreement about what bytes mean. Here YOU are
# the format author: you decide what a record holds, and everything you leave
# out is a question the table cannot answer later.

MONEY = r"\$([\d,]+\.\d{2})"

FIELD_PATTERNS = {
    "invoice_id": re.compile(r"\b(INV-\d+)\b"),
    "purchase_order": re.compile(r"Purchase order (PO-\d+)"),
    "issue_date": re.compile(r"(\d{4}-\d{2}-\d{2})"),
    "terms": re.compile(r"(Net \d+|Due on receipt)"),
    "subtotal": re.compile(r"Subtotal\s*\n?" + MONEY),
    "tax": re.compile(r"Sales tax \([\d.]+%\)\s*\n?" + MONEY),
    "total": re.compile(r"Total due\s*\n?" + MONEY),
    "status": re.compile(r"Status: (\w+)"),
}

LINE_ITEM = re.compile(
    r"^(?P<description>[A-Z][^\n$]*?)\n"
    r"(?P<quantity>\d+)\n"
    r"(?P<uom>[a-z]+)\n"
    r"\$(?P<unit_price>[\d,]+\.\d{2})\n"
    r"\$(?P<amount>[\d,]+\.\d{2})$",
    re.M)


def money(text: str) -> float:
    return float(text.replace(",", ""))


def extract_record(text: str, vendors: list[str], customers: list[str]) -> dict:
    rec = {}
    for field, pattern in FIELD_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            rec[field] = None
            continue
        value = match.group(1)
        rec[field] = money(value) if field in ("subtotal", "tax", "total") else value

    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
    rec["vendor"] = first_line if first_line in vendors else None
    rec["customer"] = next((c for c in customers if c in text), None)

    dates = FIELD_PATTERNS["issue_date"].findall(text)
    rec["issue_date"] = dates[0] if dates else None
    rec["due_date"] = dates[1] if len(dates) > 1 else None

    rec["line_items"] = [
        {"description": mm.group("description").strip(),
         "quantity": int(mm.group("quantity")),
         "uom": mm.group("uom"),
         "unit_price": money(mm.group("unit_price")),
         "amount": money(mm.group("amount"))}
        for mm in LINE_ITEM.finditer(text)
    ]
    return rec


# --------------------------------------------------------------------------
# 3 · the two stores
# --------------------------------------------------------------------------

def build_sqlite(records: list[dict]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE invoices (
        invoice_id TEXT PRIMARY KEY, vendor TEXT, customer TEXT,
        issue_date TEXT, due_date TEXT, terms TEXT, purchase_order TEXT,
        subtotal REAL, tax REAL, total REAL, status TEXT)""")
    conn.execute("""CREATE TABLE line_items (
        invoice_id TEXT, description TEXT, quantity INTEGER,
        uom TEXT, unit_price REAL, amount REAL)""")
    for r in records:
        conn.execute(
            "INSERT OR REPLACE INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (r["invoice_id"], r["vendor"], r["customer"], r["issue_date"],
             r["due_date"], r["terms"], r["purchase_order"], r["subtotal"],
             r["tax"], r["total"], r["status"]))
        for it in r["line_items"]:
            conn.execute("INSERT INTO line_items VALUES (?,?,?,?,?,?)",
                         (r["invoice_id"], it["description"], it["quantity"],
                          it["uom"], it["unit_price"], it["amount"]))
    conn.commit()
    return conn


class Retriever:
    """BM25 and dense over the same invoice texts, fused. The best the
    similarity side of the argument can be made to look."""

    def __init__(self, docs: dict[str, str], model_name="all-MiniLM-L6-v2"):
        import numpy as np
        from sentence_transformers import SentenceTransformer

        self.ids = sorted(docs)
        self.texts = [docs[i] for i in self.ids]

        self.postings: dict[str, list[tuple[int, int]]] = {}
        self.doc_len = []
        for i, text in enumerate(self.texts):
            counts: dict[str, int] = {}
            for tok in tokenize(text):
                counts[tok] = counts.get(tok, 0) + 1
            self.doc_len.append(sum(counts.values()))
            for term, tf in counts.items():
                self.postings.setdefault(term, []).append((i, tf))
        self.N = len(self.texts)
        self.avgdl = sum(self.doc_len) / self.N

        self.model = SentenceTransformer(model_name)
        vecs = self.model.encode(self.texts, batch_size=64,
                                 show_progress_bar=False).astype("float32")
        self.vectors = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    def bm25(self, query: str, k1=1.2, b=0.75) -> dict[int, float]:
        scores: dict[int, float] = {}
        for term in set(tokenize(query)):
            plist = self.postings.get(term)
            if not plist:
                continue
            idf = math.log(1 + (self.N - len(plist) + 0.5) / (len(plist) + 0.5))
            for doc, tf in plist:
                norm = 1 - b + b * self.doc_len[doc] / self.avgdl
                scores[doc] = scores.get(doc, 0.0) + idf * (tf * (k1 + 1)) / (tf + k1 * norm)
        return scores

    def dense(self, query: str):
        import numpy as np
        q = self.model.encode([query])[0].astype("float32")
        q /= np.linalg.norm(q)
        return self.vectors @ q

    def search(self, query: str, k: int = 4) -> list[str]:
        """Reciprocal rank fusion of the two, which is module 15's move."""
        import numpy as np
        bm = self.bm25(query)
        bm_rank = {d: r for r, (d, _) in enumerate(
            sorted(bm.items(), key=lambda kv: -kv[1]))}
        dense_scores = self.dense(query)
        dense_rank = {int(d): r for r, d in enumerate(np.argsort(-dense_scores))}
        fused: dict[int, float] = {}
        for d in set(bm_rank) | set(dense_rank):
            fused[d] = (1 / (60 + bm_rank.get(d, 10_000))
                        + 1 / (60 + dense_rank.get(d, 10_000)))
        top = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [self.ids[d] for d, _ in top]


# --------------------------------------------------------------------------
# 4 · answering the aggregate questions with SQL
# --------------------------------------------------------------------------

def answer_with_sql(conn: sqlite3.Connection, question: dict):
    """One handler per question shape. Deliberately plain: the point is that
    these questions have exact answers, not that the routing is clever."""
    q = question["question"]
    cur = conn.cursor()

    m = re.search(r"total across all invoices from (.+?)\?", q)
    if m:
        row = cur.execute("SELECT SUM(total) FROM invoices WHERE vendor = ?",
                          (m.group(1),)).fetchone()
        return round(row[0], 2) if row[0] is not None else None

    m = re.search(r"How many invoices did (.+?) issue\?", q)
    if m:
        return cur.execute("SELECT COUNT(*) FROM invoices WHERE vendor = ?",
                           (m.group(1),)).fetchone()[0]

    m = re.search(r"How many invoices exceed \$([\d,]+)\?", q)
    if m:
        threshold = float(m.group(1).replace(",", ""))
        return cur.execute("SELECT COUNT(*) FROM invoices WHERE total > ?",
                           (threshold,)).fetchone()[0]

    if "largest total" in q:
        return cur.execute(
            "SELECT invoice_id FROM invoices ORDER BY total DESC LIMIT 1").fetchone()[0]
    if "total value of every invoice" in q:
        return round(cur.execute("SELECT SUM(total) FROM invoices").fetchone()[0], 2)
    if "average invoice total" in q:
        return round(cur.execute("SELECT AVG(total) FROM invoices").fetchone()[0], 2)
    if "overdue" in q:
        return cur.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'overdue'").fetchone()[0]
    if "servo motors" in q:
        row = cur.execute("SELECT SUM(quantity) FROM line_items "
                          "WHERE description LIKE 'Servo motor%'").fetchone()
        return row[0]
    return None


def sql_descriptive(conn: sqlite3.Connection, question: str) -> list[str]:
    """The structured store attempting a descriptive question, honestly.

    It can only match on fields it stored, with LIKE. That is a real strategy
    and it is what the comparison needs — not a straw man that returns
    nothing.
    """
    cur = conn.cursor()
    po = re.search(r"\b(PO-\d+)\b", question)
    if po:
        rows = cur.execute("SELECT invoice_id FROM invoices "
                           "WHERE purchase_order = ?", (po.group(1),)).fetchall()
        if rows:
            return [r[0] for r in rows]
    words = [w for w in tokenize(question) if len(w) > 3]
    like = "%" + "%".join(words[-3:]) + "%"
    rows = cur.execute(
        "SELECT DISTINCT invoice_id FROM line_items WHERE description LIKE ? "
        "LIMIT 4", (like,)).fetchall()
    return [r[0] for r in rows]


# --------------------------------------------------------------------------
# 5 · the router
# --------------------------------------------------------------------------

AGGREGATE_MARKERS = re.compile(
    r"\b(how many|total|sum|average|mean|largest|smallest|count|most|least|"
    r"exceed|over \$|value of every)\b", re.I)


def route(question: str) -> str:
    """Rules, not a model. Twelve words of pattern, and the page reports how
    often they are right."""
    return "sql" if AGGREGATE_MARKERS.search(question) else "retrieval"


# --------------------------------------------------------------------------

def evidence_coverage(retrieved: list[str], required: list[str]) -> float:
    """What fraction of the documents needed to answer actually came back.

    This is how a retriever gets graded on an aggregate question without
    inventing an answer for it. To count invoices over $10,000 you need to see
    all of them; a top-4 retrieval can show you four.
    """
    if not required:
        return 0.0
    return len(set(retrieved) & set(required)) / len(required)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", type=int, default=4,
                    help="how many documents the retriever returns (Part 0 used 4)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    truth_path = INVOICES / "ground_truth.json"
    if not truth_path.exists():
        sys.exit("missing invoices — run: python data/fetch.py --only invoices")
    truth = json.loads(truth_path.read_text())
    invoices = truth["invoices"]
    questions = truth["questions"]

    m = {"k": args.k, "n_invoices": len(invoices),
         "n_descriptive": len(questions["descriptive"]),
         "n_aggregate": len(questions["aggregate"])}

    rule("1 · parse the PDFs and extract records")
    t0 = time.perf_counter()
    docs = parse_invoices()
    parse_seconds = time.perf_counter() - t0

    vendors = sorted({r["vendor"] for r in invoices})
    customers = sorted({r["customer"] for r in invoices})
    t0 = time.perf_counter()
    records = [extract_record(text, vendors, customers) for text in docs.values()]
    extract_seconds = time.perf_counter() - t0

    # How good is the extraction? Grade it against what the generator wrote.
    by_id = {r["invoice_id"]: r for r in invoices}
    field_hits = {f: 0 for f in ("vendor", "customer", "issue_date", "terms",
                                 "purchase_order", "total", "status")}
    line_item_ok = 0
    for rec in records:
        real = by_id.get(rec.get("invoice_id"))
        if not real:
            continue
        for f in field_hits:
            got, want = rec.get(f), real.get(f)
            if f == "total":
                if got is not None and abs(got - want) < 0.005:
                    field_hits[f] += 1
            elif got == want:
                field_hits[f] += 1
        if len(rec["line_items"]) == len(real["line_items"]):
            line_item_ok += 1

    m["extraction"] = {
        "parse_seconds": parse_seconds,
        "extract_seconds": extract_seconds,
        "documents": len(docs),
        "field_accuracy": {f: n / len(records) for f, n in field_hits.items()},
        "line_item_count_accuracy": line_item_ok / len(records),
    }
    print(f"  parsed {len(docs)} invoices in {human_time(parse_seconds)}, "
          f"extracted records in {human_time(extract_seconds)}")
    for f, acc in m["extraction"]["field_accuracy"].items():
        print(f"    {f:<16} {acc:.1%}")
    print(f"    {'line item count':<16} "
          f"{m['extraction']['line_item_count_accuracy']:.1%}")

    rule("2 · build both stores over the same documents")
    conn = build_sqlite(records)
    t0 = time.perf_counter()
    retriever = Retriever(docs)
    print(f"  SQLite: {len(records)} invoices, "
          f"{sum(len(r['line_items']) for r in records)} line items")
    print(f"  retriever: BM25 + dense over the same {len(docs)} documents "
          f"({human_time(time.perf_counter() - t0)})")

    # ======================================================================
    rule("3 · descriptive questions — 'which invoice says X?'")
    # ======================================================================
    desc = questions["descriptive"]
    ret_hits = ret_top1 = sql_hits = 0
    ret_lat, sql_lat = [], []
    for q in desc:
        t0 = time.perf_counter()
        got = retriever.search(q["question"], k=args.k)
        ret_lat.append(time.perf_counter() - t0)
        if q["answer"] in got:
            ret_hits += 1
        if got and got[0] == q["answer"]:
            ret_top1 += 1

        t0 = time.perf_counter()
        sql_got = sql_descriptive(conn, q["question"])
        sql_lat.append(time.perf_counter() - t0)
        if q["answer"] in sql_got:
            sql_hits += 1

    ret_lat.sort(); sql_lat.sort()
    m["descriptive"] = {
        "retrieval": {"accuracy_at_k": ret_hits / len(desc),
                      "accuracy_at_1": ret_top1 / len(desc),
                      "median_seconds": ret_lat[len(ret_lat) // 2]},
        "sql": {"accuracy_at_k": sql_hits / len(desc),
                "median_seconds": sql_lat[len(sql_lat) // 2]},
    }
    print(f"  retrieval  correct in top-{args.k}: "
          f"{ret_hits / len(desc):.1%}   top-1: {ret_top1 / len(desc):.1%}")
    print(f"  SQL        correct in top-{args.k}: {sql_hits / len(desc):.1%}")

    # ======================================================================
    rule("4 · aggregate questions — 'how many? what's the total?'")
    # ======================================================================
    agg = questions["aggregate"]
    sql_correct = 0
    ret_exact = 0
    distinctive_total = 0
    coverages = []
    sql_lat2, ret_lat2 = [], []

    # which invoices would you have to SEE to answer each aggregate question?
    def required_docs(q):
        text = q["question"]
        vendor = next((v for v in vendors if v in text), None)
        if vendor:
            return [r["invoice_id"] for r in invoices if r["vendor"] == vendor]
        mm = re.search(r"exceed \$([\d,]+)", text)
        if mm:
            threshold = float(mm.group(1).replace(",", ""))
            return [r["invoice_id"] for r in invoices if r["total"] > threshold]
        if "overdue" in text:
            return [r["invoice_id"] for r in invoices if r["status"] == "overdue"]
        return [r["invoice_id"] for r in invoices]

    rows = []
    for q in agg:
        t0 = time.perf_counter()
        sql_answer = answer_with_sql(conn, q)
        sql_lat2.append(time.perf_counter() - t0)
        want = q["answer"]
        ok = (sql_answer is not None
              and (abs(sql_answer - want) < 0.02
                   if isinstance(want, (int, float)) else sql_answer == want))
        sql_correct += ok

        t0 = time.perf_counter()
        got = retriever.search(q["question"], k=args.k)
        ret_lat2.append(time.perf_counter() - t0)
        needed = required_docs(q)
        cov = evidence_coverage(got, needed)
        coverages.append(cov)
        # Could the retrieved text even contain the answer, written out?
        # Only ask this for distinctive answers — a two-digit count like "21"
        # appears by coincidence in almost any invoice, so counting those as
        # hits would flatter the retriever for no reason.
        blob = " ".join(docs[d] for d in got).replace("$", "").replace(",", "")
        distinctive = isinstance(want, float) and want >= 1000
        answer_text = f"{want:.2f}" if isinstance(want, float) else str(want)
        found = distinctive and answer_text in blob
        ret_exact += found
        distinctive_total += distinctive

        rows.append({"id": q["id"], "question": q["question"],
                     "kind": q["kind"], "true_answer": want,
                     "sql_answer": sql_answer, "sql_correct": bool(ok),
                     "documents_needed": len(needed),
                     "documents_retrieved": args.k,
                     "evidence_coverage": cov,
                     "answer_is_distinctive": bool(distinctive),
                     "answer_text_present": bool(found)})

    sql_lat2.sort(); ret_lat2.sort()
    m["aggregate"] = {
        "sql": {"accuracy": sql_correct / len(agg),
                "median_seconds": sql_lat2[len(sql_lat2) // 2]},
        "retrieval": {
            "answer_present_rate": (ret_exact / distinctive_total
                                    if distinctive_total else 0.0),
            "distinctive_answers": distinctive_total,
            "answers_found": ret_exact,
            "mean_evidence_coverage": sum(coverages) / len(coverages),
            "median_seconds": ret_lat2[len(ret_lat2) // 2],
            "median_documents_needed": sorted(
                r["documents_needed"] for r in rows)[len(rows) // 2],
        },
        "examples": rows[:6],
        "all": rows,
    }
    a = m["aggregate"]
    print(f"  SQL        exactly correct: {a['sql']['accuracy']:.1%}  "
          f"({human_time(a['sql']['median_seconds'])} per question)")
    print(f"  retrieval  answer written in the retrieved text: "
          f"{a['retrieval']['answers_found']}/"
          f"{a['retrieval']['distinctive_answers']} of the questions whose "
          f"answer is a distinctive number")
    print(f"             evidence coverage: "
          f"{a['retrieval']['mean_evidence_coverage']:.1%} of the documents "
          f"needed")
    print(f"             a median aggregate question needs "
          f"{a['retrieval']['median_documents_needed']} documents; "
          f"you retrieved {args.k}")

    print(f"\n  {'question':<52} {'true':>12} {'SQL':>12}  needs")
    for r in rows[:6]:
        tv = f"{r['true_answer']:,}" if not isinstance(r['true_answer'], str) \
            else r['true_answer']
        sv = f"{r['sql_answer']:,}" if not isinstance(r['sql_answer'], str) \
            else str(r['sql_answer'])
        print(f"  {r['question'][:50]:<52} {tv:>12} {sv:>12}  "
              f"{r['documents_needed']:>4} docs")

    # ======================================================================
    rule("5 · the router")
    # ======================================================================
    correct_routes = 0
    for q in desc:
        correct_routes += route(q["question"]) == "retrieval"
    for q in agg:
        correct_routes += route(q["question"]) == "sql"
    total_q = len(desc) + len(agg)
    m["router"] = {"accuracy": correct_routes / total_q,
                   "questions": total_q}

    # end-to-end: each strategy alone, against the router
    def score_all(strategy: str) -> float:
        score = 0
        for q in desc:
            if strategy == "sql":
                score += q["answer"] in sql_descriptive(conn, q["question"])
            else:
                score += q["answer"] in retriever.search(q["question"], k=args.k)
        for q in agg:
            if strategy == "retrieval":
                score += 0          # measured above: it cannot produce a number
            else:
                sql_answer = answer_with_sql(conn, q)
                want = q["answer"]
                score += bool(sql_answer is not None
                              and (abs(sql_answer - want) < 0.02
                                   if isinstance(want, (int, float))
                                   else sql_answer == want))
        return score / total_q

    routed = 0
    for q in desc + agg:
        target = route(q["question"])
        if target == "sql" and q in agg:
            sql_answer = answer_with_sql(conn, q)
            want = q["answer"]
            routed += bool(sql_answer is not None
                           and (abs(sql_answer - want) < 0.02
                                if isinstance(want, (int, float))
                                else sql_answer == want))
        elif target == "sql":
            routed += q["answer"] in sql_descriptive(conn, q["question"])
        elif q in agg:
            routed += 0
        else:
            routed += q["answer"] in retriever.search(q["question"], k=args.k)

    m["end_to_end"] = {
        "retrieval_only": score_all("retrieval"),
        "sql_only": score_all("sql"),
        "routed": routed / total_q,
    }
    e = m["end_to_end"]
    print(f"  routing rules correct on {m['router']['accuracy']:.1%} of "
          f"{total_q} questions")
    print(f"  retrieval alone   {e['retrieval_only']:.1%} of all questions")
    print(f"  SQL alone         {e['sql_only']:.1%}")
    print(f"  routed            {e['routed']:.1%}")

    if not args.no_write:
        path = write_measurements(SLUG, m)
        print(f"\nwrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
