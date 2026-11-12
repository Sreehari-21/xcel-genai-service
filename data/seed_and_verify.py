"""
Data Engineering Seed, Persistence Verification & Storage Benchmark Utility.
Run from project root:
    python data/seed_and_verify.py
"""

import json
import os
import subprocess
import sys
import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings
from app.services.document_service import document_service
from app.services.embedding_service import embedding_service
from app.services.ingestion_service import ingestion_service
from app.services.structured_data_retriever import structured_retriever
from app.services.trace_service import trace_service
from app.services.vector_store import vector_store, ChromaVectorStore


def seed_baseline_samples() -> dict:
    samples = [
        os.path.join(ROOT_DIR, "data", "samples", "dbms.pdf"),
        os.path.join(ROOT_DIR, "data", "samples", "students.csv"),
    ]
    results = []
    for path in samples:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing sample dataset: {path}")
        with open(path, "rb") as f:
            raw = f.read()
        t0 = time.perf_counter()
        meta = ingestion_service.process_file(file_bytes=raw, file_name=os.path.basename(path))
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        results.append({
            "file_name": meta.file_name,
            "document_id": meta.document_id,
            "file_type": meta.file_type,
            "chunk_count": meta.chunk_count,
            "is_duplicate": meta.is_duplicate,
            "content_hash": meta.content_hash,
            "elapsed_ms": elapsed_ms,
        })
    return {"seeded": results}


def verify_cross_process_persistence() -> dict:
    script = (
        "import json, sys; sys.path.insert(0, 'backend'); "
        "from app.services.vector_store import vector_store; "
        "from app.services.document_service import document_service; "
        "from app.services.trace_service import trace_service; "
        "print(json.dumps({"
        "'vector_stats': vector_store.get_stats(), "
        "'docs': [d.model_dump() for d in document_service.list_documents()], "
        "'trace_db': trace_service.get_stats()"
        "}))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    # Extract the final JSON line (stdout also includes structured JSON log lines if any)
    last_line = [line for line in proc.stdout.strip().splitlines() if line.strip()][-1]
    return json.loads(last_line)


def run_storage_benchmarks() -> dict:
    # 1. Duplicate ingestion benchmark
    dbms_path = os.path.join(ROOT_DIR, "data", "samples", "dbms.pdf")
    with open(dbms_path, "rb") as f:
        dbms_bytes = f.read()
    t0 = time.perf_counter()
    dup_res = ingestion_service.process_file(file_bytes=dbms_bytes, file_name="dbms.pdf")
    dup_ms = round((time.perf_counter() - t0) * 1000, 3)

    # 2. Embedding query cold vs warm cache benchmark
    embedding_service.clear_cache()
    test_query = "Explain First Normal Form (1NF) in relational databases"
    t0 = time.perf_counter()
    emb_cold = embedding_service.embed_query(test_query)
    emb_cold_ms = round((time.perf_counter() - t0) * 1000, 3)

    t0 = time.perf_counter()
    emb_warm = embedding_service.embed_query(test_query)
    emb_warm_ms = round((time.perf_counter() - t0) * 1000, 4)
    assert emb_cold == emb_warm

    # 3. ChromaDB vector query cold vs cached benchmark
    t0 = time.perf_counter()
    res_cold = vector_store.query(
        ChromaVectorStore.COLLECTION_PDF,
        emb_cold,
        top_k=5,
        filters={"document_name": "dbms.pdf"}
    )
    vec_cold_ms = round((time.perf_counter() - t0) * 1000, 3)

    t0 = time.perf_counter()
    res_warm = vector_store.query(
        ChromaVectorStore.COLLECTION_PDF,
        emb_cold,
        top_k=5,
        filters={"document_name": "dbms.pdf"}
    )
    vec_warm_ms = round((time.perf_counter() - t0) * 1000, 4)
    assert len(res_cold) == len(res_warm)

    # 4. Structured CSV cold vs cached DataFrame benchmark
    csv_docs = [d for d in document_service.list_documents() if d.file_type == "csv"]
    csv_bench = {}
    if csv_docs:
        csv_doc = csv_docs[0]
        structured_retriever.invalidate_cache(csv_doc.document_id)
        t0 = time.perf_counter()
        s_cold = structured_retriever.retrieve(
            "Which students scored >= 90 in DBMS?",
            csv_doc.document_id,
            csv_doc.file_name,
            top_k=5,
        )
        csv_cold_ms = round((time.perf_counter() - t0) * 1000, 3)

        t0 = time.perf_counter()
        s_warm = structured_retriever.retrieve(
            "Which students scored >= 90 in DBMS?",
            csv_doc.document_id,
            csv_doc.file_name,
            top_k=5,
        )
        csv_warm_ms = round((time.perf_counter() - t0) * 1000, 4)
        csv_bench = {
            "matched_rows": len(s_cold),
            "cold_read_ms": csv_cold_ms,
            "cached_read_ms": csv_warm_ms,
            "speedup_factor": round(csv_cold_ms / max(csv_warm_ms, 0.0001), 1),
        }

    return {
        "duplicate_dedup_check": {
            "is_duplicate": dup_res.is_duplicate,
            "document_id": dup_res.document_id,
            "latency_ms": dup_ms,
        },
        "embedding_query_cache": {
            "cold_ms": emb_cold_ms,
            "warm_cache_ms": emb_warm_ms,
            "speedup_factor": round(emb_cold_ms / max(emb_warm_ms, 0.0001), 1),
        },
        "vector_store_query_cache": {
            "hits_returned": len(res_cold),
            "cold_ms": vec_cold_ms,
            "warm_cache_ms": vec_warm_ms,
            "speedup_factor": round(vec_cold_ms / max(vec_warm_ms, 0.0001), 1),
        },
        "structured_csv_cache": csv_bench,
        "embedding_stats": embedding_service.get_stats(),
        "vector_store_metrics": vector_store.get_performance_metrics(),
        "structured_retriever_stats": structured_retriever.get_stats(),
        "trace_db_stats": trace_service.get_stats(),
    }


def main():
    os.chdir(ROOT_DIR)
    seed_info = seed_baseline_samples()
    persistence_info = verify_cross_process_persistence()
    benchmarks = run_storage_benchmarks()
    report = {
        "seed": seed_info,
        "persistence_subprocess_check": {
            "vector_stats": persistence_info["vector_stats"],
            "registered_docs_count": len(persistence_info["docs"]),
            "registered_files": [d["file_name"] for d in persistence_info["docs"]],
            "trace_db": persistence_info["trace_db"],
        },
        "benchmarks": benchmarks,
    }
    print("=== DATA_VERIFICATION_REPORT ===")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

