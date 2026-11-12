# Embeddings, Database & Data Engineering Report

**Project:** Xcel RAG — Multi-Modal GenAI Microservice  
**Scope:** Processed Data Storage (`data/`), Embedding Generation, ChromaDB Optimization, Structured CSV Retrieval, Caching, Concurrency, and Persistence Reliability

---

## 1. Executive Summary

This report documents the audit, fixes, performance optimizations, concurrency hardening, persistence verification, and `data/` storage standardization performed for the **Embeddings, Database & Data Engineering** layer.

### Key Outcomes
- **Offline-First Embedding Generation & Caching**: Eliminated ~120s HuggingFace Hub timeout hangs in offline/restricted environments by loading local cached weights first (`383.67 ms` load time), added thread-safe `RLock` inference guards, intra-batch deduplication, and bounded LRU query/text caching (**373.9x speedup** on repeated queries: `21.799 ms` → `0.0583 ms`).
- **ChromaDB Optimization & Metadata Accuracy**: Added HNSW tuning (`construction_ef=128`, `search_ef=64`, `M=16`), collection handle caching, thread-safe locking, full metadata filter operator support (`$and`, `$or`, `$in`, `$gte`, etc.), `top_k > count` safety bounds, `replace_document_chunks()` stale-chunk cleanup, and write-invalidated query caching (**28.9x speedup**: `16.58 ms` → `0.5746 ms`).
- **Structured CSV Retrieval & Caching**: Fixed regex collision where `>=`/`<=` matched `=` and yielded 0 rows, added multi-column local operator context resolution, `between X and Y` range support, pure aggregate fallback queries, and a thread-safe `mtime`-validated DataFrame LRU cache (**4.3x speedup**: `34.468 ms` → `7.9325 ms`).
- **Duplicate Ingestion Prevention & Atomic Rollback**: Added SHA-256 `content_hash` deduplication with per-hash concurrency locks in `ingestion_service.py` (preventing duplicate files and duplicate vector indexing in `4.289 ms`) plus rollback cleanup on ingestion failure.
- **Persistence & Concurrent Reliability**: Added `RLock` + atomic temp-file `os.replace()` for `data/processed/registry.json` and processed CSVs, enabled SQLite WAL mode + `busy_timeout=10000` in `data/processed/xcel_rag.db`, and verified durability across fresh Python subprocess restarts.
- **Clean `data/` Baseline**: Purged leftover test artifacts (`csv_test_1.csv`, test fixtures), added teardown isolation to `tests/test_csv.py` and `tests/test_retrieval.py`, seeded `dbms.pdf` and `students.csv` cleanly, and created `data/seed_and_verify.py` for repeatable seeding and verification.

---

## 2. Audit Findings & Resolutions

| Component | Audit Finding | Resolution Implemented |
|---|---|---|
| **Embedding Service** (`embedding_service.py`) | Cold-started `SentenceTransformer` attempted HuggingFace Hub network calls first (~120s+ timeout when offline); no query/batch caching; unprotected concurrent `encode()` calls risk Rust `tokenizers` borrow panics. | Added `local_files_only=True` offline-first load (`383.67 ms`), `_encode_lock` (`RLock`), bounded LRU cache (`max_cache_size=1024`), intra-batch deduplication, empty-text guard, and telemetry (`get_stats()`). |
| **Vector Store** (`vector_store.py`) | Dict operator filters (`{"page_number": {"$gte": 2}}`) were silently stripped; `n_results > count` caused Chroma warnings/errors; no locking on concurrent writes; re-indexing left stale tail chunks; no query cache. | Added `_build_where_filter()`, `n_results` clamping & filtered-count retry, `threading.RLock`, `replace_document_chunks()`, collection handle cache, bounded LRU query cache invalidated on writes, `verify_persistence()`, and `get_performance_metrics()`. |
| **Structured CSV Retriever** (`structured_data_retriever.py`) | Read CSV from disk via `pd.read_csv()` on every request; `>=` / `<=` double-matched `=` yielding 0 rows; multiple numeric conditions targeted only the first numeric column; pure aggregate queries without row filters returned `[]`. | Added `mtime`-aware DataFrame LRU cache (`invalidate_cache()`), ordered non-overlapping regex spans (`>=`, `<=`, `!=`, `>`, `<`, `==`, `between`), per-match local column resolution, multi-value categorical `OR` within columns, aggregate-only fallback, and `get_stats()`. |
| **Metadata & Registry** (`chunk.py`, `csv_service.py`, `document_service.py`) | `None` in `additional_meta` serialized as `"None"` strings; non-atomic `registry.json` writes risked corruption under concurrency; missing `content_hash`. | Skipped `None` and normalized numpy scalars via `.item()`; added `RLock` + atomic `os.replace()` saves, `content_hash`, `find_by_hash()`, and cache invalidation on deletion. |
| **Ingestion & Trace Persistence** (`ingestion_service.py`, `trace_service.py`) | Uploading identical files created duplicate IDs, files, and vectors; partial CSV failure left orphan schema chunks; SQLite used default journal mode without lock coordination. | Added SHA-256 deduplication (`is_duplicate=True`), per-hash locks, rollback cleanup on failure, and SQLite WAL mode (`PRAGMA journal_mode=WAL`, `busy_timeout=10000`, `RLock`). |
| **`data/` & Test Hygiene** (`tests/test_csv.py`, `tests/test_retrieval.py`) | Tests wrote `csv_test_1.csv`, `doc_hybrid_pdf`, and `csv_hybrid_data` into production `data/` without cleanup. | Added fixture teardowns in `tests/test_csv.py` and `tests/test_retrieval.py`; cleaned `data/` and seeded official sample datasets via `data/seed_and_verify.py`. |

---

## 3. `data/` Folder Structure & Verified State

```text
data/
├── chroma/
│   ├── .gitkeep
│   ├── chroma.sqlite3                      # Persistent ChromaDB metadata & HNSW registry
│   └── <3 collection segment folders>/     # pdf_documents (6), csv_records (10), csv_schemas (1)
├── processed/
│   ├── .gitkeep
│   ├── registry.json                       # Atomic document registry (2 completed docs w/ SHA-256 hashes)
│   ├── csv_e8137c32e3.csv                  # Normalized DataFrame for students.csv (10 rows)
│   └── xcel_rag.db                         # SQLite trace & conversation store (journal_mode=wal)
├── samples/
│   ├── dbms.pdf                            # 3-page normalization reference PDF
│   ├── students.csv                        # 10-row student marks dataset
│   └── generate_samples.py
├── uploads/
│   ├── .gitkeep
│   ├── doc_15bdd4734e_dbms.pdf             # 3,091 bytes
│   └── csv_e8137c32e3_students.csv         # 280 bytes
└── seed_and_verify.py                      # Seeding, cross-process persistence & benchmark script
```

---

## 4. Sub-Team Interface Coordination

### Sub-Team 1 (Ingestion & Parsing)
- **Contract**: `ingestion_service.process_file(file_bytes, file_name, document_id=None) -> DocumentMetadata`
- Computes SHA-256 `content_hash` and checks `document_service.find_by_hash()` + `vector_store.document_exists()` under per-hash lock.
- Uses `vector_store.replace_document_chunks(...)` when re-indexing an explicit `document_id`.
- Calls `structured_retriever.invalidate_cache(document_id)` upon CSV updates or deletions.
- Returns `is_duplicate=True` in `DocumentUploadResponse` (`POST /api/v1/documents/upload`) when an identical file is already cleanly indexed.

### Sub-Team 3 (Retrieval & LLM Orchestration)
- **Contract**: `retrieval_service.retrieve(query, top_k, filters) -> (chunks, context, citations, trace)`
- Preserves and forwards metadata filters (`document_id`, `document_name`, `file_name` mapped to `document_name`, `page_number`, `row_number`, `section`, `col_*`, and Chroma operator dicts) to `vector_store.query(...)` and filters `csv_docs` in `structured_retriever.retrieve(...)`.
- Scores all candidates during `mixed` queries before applying modality balancing so large CSV sets do not crowd out PDF chunks.
- Health observability exposed via `GET /api/v1/health` (`storage_metrics` section with embedding, vector store, structured cache, and trace DB metrics).

---

## 5. Measured Performance & Verification Results

Measured directly from `python data/seed_and_verify.py` and `pytest` runs:

### A. Ingestion & Deduplication
- `dbms.pdf` (3 pages, 6 chunks, cold model load included): **632.93 ms** (`25.16 ms` Chroma upsert)
- `students.csv` (10 rows + 1 schema chunk): **168.29 ms** (`19.83 ms` schema upsert + `22.17 ms` rows upsert)
- Duplicate `dbms.pdf` re-upload detection: **4.289 ms** (`is_duplicate: true`, 0 new vectors added)

### B. Caching & Query Latency
| Layer | Cold Latency | Warm Cache Latency | Measured Speedup |
|---|---:|---:|---:|
| **Embedding Query Cache** (`all-MiniLM-L6-v2`) | `21.799 ms` | `0.0583 ms` | **373.9x** |
| **ChromaDB Query Cache** (`pdf_documents`, `top_k=5`) | `16.580 ms` | `0.5746 ms` | **28.9x** |
| **Structured CSV Cache** (`students.csv`, `marks >= 90`) | `34.468 ms` | `7.9325 ms` | **4.3x** |

### C. Disk Footprint & Persistence Check
- ChromaDB directory usage (`data/chroma/`): **856,556 bytes** (`pdf_documents: 6`, `csv_records: 10`, `csv_schemas: 1`)
- Cross-process persistence probe (fresh Python subprocess): Confirmed all **17 vectors**, **2 registered documents** (`dbms.pdf`, `students.csv`), and SQLite **`wal`** journal mode survived intact across process restart.

### D. Retrieval Evaluation Benchmark (`tests/test_eval.py`)
- **Total Queries**: 5 (`evaluation_questions.json`, `top_k=5`)
- **Hit@5**: **100.00%** (`5 / 5`)
- **MRR**: **1.0000**

### E. Automated Test Suite Scope
Executed in sandbox:
```text
$env:PYTHONPATH="backend"; python -m pytest tests/test_pdf.py tests/test_csv.py tests/test_ollama.py tests/test_retrieval.py tests/test_eval.py tests/test_data_engineering.py -v
```
- **Result**: **18 passed, 0 failed** in `13.97s` (including multi-threaded concurrency stress test across 8 workers doing simultaneous unique ingestions, duplicate uploads, vector queries, structured CSV queries, and SQLite trace writes, plus subprocess restart persistence test).
- *Note*: ASGI `TestClient` suites (`tests/test_api.py`, `tests/test_phase2_standardization.py`) were not run inside the restricted sandbox because `asyncio` loopback `socketpair()` initialization is blocked in Windows sandbox mode, and `test_v1_query_endpoints_and_citations` requires a running local Ollama daemon on `localhost:11434`.

