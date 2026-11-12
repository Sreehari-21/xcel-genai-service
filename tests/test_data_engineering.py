import concurrent.futures
import json
import math
import os
import subprocess
import sys
import pytest
import pymupdf

from app.core.config import settings
from app.models.chunk import Chunk, ChunkMetadata
from app.models.document import DocumentMetadata
from app.services.document_service import DocumentRegistryService
from app.services.embedding_service import embedding_service, SentenceTransformerEmbeddingService
from app.services.ingestion_service import ingestion_service
from app.services.structured_data_retriever import PandasStructuredDataRetriever
from app.services.trace_service import TraceService
from app.services.vector_store import ChromaVectorStore


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Provide isolated directories and fresh service instances for storage/concurrency testing."""
    upload_dir = tmp_path / "uploads"
    chroma_dir = tmp_path / "chroma"
    processed_dir = tmp_path / "processed"
    db_path = processed_dir / "test_rag.db"
    upload_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "upload_dir", str(upload_dir))
    monkeypatch.setattr(settings, "chroma_dir", str(chroma_dir))
    monkeypatch.setattr(settings, "processed_dir", str(processed_dir))
    monkeypatch.setattr(settings, "sqlite_db_path", str(db_path))

    store = ChromaVectorStore(persist_directory=str(chroma_dir))
    registry = DocumentRegistryService(registry_file=str(processed_dir / "registry.json"))
    retriever = PandasStructuredDataRetriever(max_cached_tables=16)
    traces = TraceService(db_path=str(db_path))

    return {
        "tmp_path": tmp_path,
        "upload_dir": upload_dir,
        "chroma_dir": chroma_dir,
        "processed_dir": processed_dir,
        "db_path": db_path,
        "store": store,
        "registry": registry,
        "retriever": retriever,
        "traces": traces,
    }


def _make_sample_pdf_bytes(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    raw = doc.tobytes()
    doc.close()
    return raw


def test_embedding_caching_dedup_and_normalization():
    # Use shared singleton to avoid reloading model weights in test suite
    embedding_service.clear_cache()

    vec1 = embedding_service.embed_query("What is database normalization?")
    assert len(vec1) == 384
    norm = math.sqrt(sum(x * x for x in vec1))
    assert abs(norm - 1.0) < 1e-4

    # Repeat query should trigger cache hit
    vec2 = embedding_service.embed_query("What is database normalization?")
    assert vec1 == vec2
    stats = embedding_service.get_stats()
    assert stats["cache_hits"] >= 1

    # Batch deduplication preserves order and exact vector equality
    batch_texts = ["Alpha chunk", "Beta chunk", "Alpha chunk", ""]
    batch_vecs = embedding_service.embed_documents(batch_texts)
    assert len(batch_vecs) == 4
    assert batch_vecs[0] == batch_vecs[2]
    assert all(v == 0.0 for v in batch_vecs[3])


def test_chromadb_metadata_filters_replace_and_empty_guards(isolated_env):
    store: ChromaVectorStore = isolated_env["store"]

    # Empty collection safety
    empty_res = store.query(ChromaVectorStore.COLLECTION_PDF, [0.1] * 384, top_k=5)
    assert empty_res == []

    # Create 3 chunks across 2 documents and 2 pages
    texts = [
        "First Normal Form requires atomic values.",
        "Second Normal Form removes partial dependencies.",
        "Transactions ensure ACID properties.",
    ]
    embs = embedding_service.embed_documents(texts)

    chunks_doc1 = [
        Chunk(
            id="doc1_chunk_1",
            text=texts[0],
            metadata=ChunkMetadata(
                source_type="pdf",
                document_id="doc_1",
                document_name="norm.pdf",
                chunk_id="doc1_chunk_1",
                page_number=1,
                section="1NF",
            ),
            embedding=embs[0],
        ),
        Chunk(
            id="doc1_chunk_2",
            text=texts[1],
            metadata=ChunkMetadata(
                source_type="pdf",
                document_id="doc_1",
                document_name="norm.pdf",
                chunk_id="doc1_chunk_2",
                page_number=2,
                section="2NF",
            ),
            embedding=embs[1],
        ),
    ]
    chunks_doc2 = [
        Chunk(
            id="doc2_chunk_1",
            text=texts[2],
            metadata=ChunkMetadata(
                source_type="pdf",
                document_id="doc_2",
                document_name="acid.pdf",
                chunk_id="doc2_chunk_1",
                page_number=3,
                section="ACID",
            ),
            embedding=embs[2],
        )
    ]

    store.add_chunks(ChromaVectorStore.COLLECTION_PDF, chunks_doc1 + chunks_doc2)

    # 1. Exact scalar metadata filter (plus top_k > filtered count safety)
    res_doc1 = store.query(
        ChromaVectorStore.COLLECTION_PDF,
        embs[1],
        top_k=10,
        filters={"document_id": "doc_1", "page_number": 2},
    )
    assert len(res_doc1) == 1
    assert res_doc1[0].id == "doc1_chunk_2"

    # 2. Operator filter ($gte)
    res_gte = store.query(
        ChromaVectorStore.COLLECTION_PDF,
        embs[2],
        top_k=5,
        filters={"page_number": {"$gte": 2}},
    )
    returned_ids = {r.id for r in res_gte}
    assert returned_ids == {"doc1_chunk_2", "doc2_chunk_1"}

    # 3. List membership filter ($in auto-conversion)
    res_in = store.query(
        ChromaVectorStore.COLLECTION_PDF,
        embs[0],
        top_k=5,
        filters={"document_name": ["norm.pdf", "acid.pdf"]},
    )
    assert len(res_in) == 3

    # 4. Replace document chunks cleanly purges stale chunks when count shrinks
    replacement_chunk = [
        Chunk(
            id="doc1_chunk_1",
            text="Updated single chunk for norm.pdf.",
            metadata=ChunkMetadata(
                source_type="pdf",
                document_id="doc_1",
                document_name="norm.pdf",
                chunk_id="doc1_chunk_1",
                page_number=1,
            ),
            embedding=embedding_service.embed_text("Updated single chunk for norm.pdf."),
        )
    ]
    store.replace_document_chunks(ChromaVectorStore.COLLECTION_PDF, "doc_1", replacement_chunk)
    stored_doc1 = store.get_by_document_id("doc_1")
    assert len(stored_doc1) == 1
    assert stored_doc1[0]["id"] == "doc1_chunk_1"

    # Verify query cache was invalidated after replace
    res_after_replace = store.query(
        ChromaVectorStore.COLLECTION_PDF,
        embs[1],
        top_k=10,
        filters={"document_id": "doc_1", "page_number": 2},
    )
    assert res_after_replace == []


def test_duplicate_ingestion_prevention_and_isolation(isolated_env, monkeypatch):
    # Redirect global singletons' underlying store/registry paths cleanly for ingestion test
    from app.services import document_service as doc_mod
    from app.services import vector_store as vs_mod
    from app.services import ingestion_service as ing_mod

    store: ChromaVectorStore = isolated_env["store"]
    registry: DocumentRegistryService = isolated_env["registry"]
    monkeypatch.setattr(doc_mod, "document_service", registry)
    monkeypatch.setattr(ing_mod, "document_service", registry)
    monkeypatch.setattr(vs_mod, "vector_store", store)
    monkeypatch.setattr(ing_mod, "vector_store", store)

    pdf_bytes = _make_sample_pdf_bytes("Duplicate Prevention Check: Normalization eliminates redundancy.")
    first = ingestion_service.process_file(file_bytes=pdf_bytes, file_name="dup_check.pdf")
    assert first.processing_status == "completed"
    assert first.is_duplicate is False

    stats_after_first = store.get_stats()
    assert stats_after_first[ChromaVectorStore.COLLECTION_PDF] == first.chunk_count

    # Second upload of identical bytes should deduplicate safely
    second = ingestion_service.process_file(file_bytes=pdf_bytes, file_name="dup_check_renamed.pdf")
    assert second.document_id == first.document_id
    assert second.is_duplicate is True
    assert store.get_stats() == stats_after_first
    assert len(registry.list_documents()) == 1


def test_structured_csv_caching_operators_and_invalidation(isolated_env):
    processed_dir = isolated_env["processed_dir"]
    retriever: PandasStructuredDataRetriever = isolated_env["retriever"]

    csv_path = processed_dir / "csv_ops.csv"
    csv_path.write_text(
        "student_id,name,semester,subject,marks\n"
        "101,Akhil,6,DBMS,85\n"
        "102,Anu,6,DBMS,90\n"
        "103,Kavya,6,DBMS,96\n"
        "104,Priya,5,OS,92\n"
    )

    # 1. >= operator regression check (previously failed because >= matched =)
    res_gte = retriever.retrieve(
        "Which students scored >= 90 in DBMS?",
        document_id="csv_ops",
        file_name="students.csv",
        top_k=5,
    )
    names_gte = [r.text for r in res_gte]
    assert len(res_gte) == 2
    assert any("Anu" in t for t in names_gte)
    assert any("Kavya" in t for t in names_gte)

    # 2. Repeat query should hit DataFrame cache
    res_cached = retriever.retrieve(
        "Which students scored >= 90 in DBMS?",
        document_id="csv_ops",
        file_name="students.csv",
        top_k=5,
    )
    assert len(res_cached) == 2
    assert retriever.get_stats()["cache_hits"] >= 1

    # 3. Multi-column filter (semester == 6 and marks between 85 and 95)
    res_multi = retriever.retrieve(
        "Students in semester == 6 with marks between 85 and 95",
        document_id="csv_ops",
        file_name="students.csv",
        top_k=5,
    )
    assert len(res_multi) == 2
    assert any("Akhil" in r.text for r in res_multi)
    assert any("Anu" in r.text for r in res_multi)
    assert not any("Kavya" in r.text for r in res_multi)

    # 4. Pure aggregate query without filter conditions
    res_agg = retriever.retrieve(
        "What is the average marks in students dataset?",
        document_id="csv_ops",
        file_name="students.csv",
        top_k=4,
    )
    assert len(res_agg) >= 2
    assert "Computed Statistics for Query" in res_agg[0].text
    assert "Average: 90.75" in res_agg[0].text

    # 5. Cache invalidation when deleted
    retriever.invalidate_cache("csv_ops")
    assert "csv_ops" not in retriever.get_stats()["cached_document_ids"]


def test_persistence_across_subprocess_restart(isolated_env):
    chroma_dir = str(isolated_env["chroma_dir"])
    reg_file = str(isolated_env["processed_dir"] / "registry.json")
    db_path = str(isolated_env["db_path"])

    store: ChromaVectorStore = isolated_env["store"]
    registry: DocumentRegistryService = isolated_env["registry"]
    traces: TraceService = isolated_env["traces"]

    emb = embedding_service.embed_text("Persistent storage check across restart.")
    chunk = Chunk(
        id="persist_doc_chunk_1",
        text="Persistent storage check across restart.",
        metadata=ChunkMetadata(
            source_type="pdf",
            document_id="persist_doc",
            document_name="persist.pdf",
            chunk_id="persist_doc_chunk_1",
            page_number=1,
        ),
        embedding=emb,
    )
    store.add_chunks(ChromaVectorStore.COLLECTION_PDF, [chunk])
    registry.register_document(
        DocumentMetadata(
            document_id="persist_doc",
            file_name="persist.pdf",
            file_type="pdf",
            file_size=512,
            processing_status="completed",
            chunk_count=1,
            page_count=1,
            content_hash="abc123",
        )
    )
    traces.save_trace(
        request_id="req_persist_1",
        query="Persistence check?",
        scope="pdf",
        trace_dict={"status": "ok"},
        latency_ms=12.3,
    )

    # Spawn a brand-new Python subprocess to prove durability across service restarts
    probe = (
        "import json, sys; sys.path.insert(0, 'backend'); "
        "from app.services.vector_store import ChromaVectorStore; "
        "from app.services.document_service import DocumentRegistryService; "
        "from app.services.trace_service import TraceService; "
        f"vs = ChromaVectorStore(persist_directory={json.dumps(chroma_dir)}); "
        f"reg = DocumentRegistryService(registry_file={json.dumps(reg_file)}); "
        f"tr = TraceService(db_path={json.dumps(db_path)}); "
        "print(json.dumps({"
        "'stats': vs.get_stats(), "
        "'doc_exists': vs.document_exists('persist_doc'), "
        "'reg_count': len(reg.list_documents()), "
        "'trace': tr.get_trace('req_persist_1') is not None"
        "}))"
    )
    proc = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    last_line = [l for l in proc.stdout.strip().splitlines() if l.strip()][-1]
    result = json.loads(last_line)
    assert result["stats"]["pdf_documents"] == 1
    assert result["doc_exists"] is True
    assert result["reg_count"] == 1
    assert result["trace"] is True


def test_concurrent_access_and_storage_reliability(isolated_env, monkeypatch):
    from app.services import document_service as doc_mod
    from app.services import vector_store as vs_mod
    from app.services import ingestion_service as ing_mod

    store: ChromaVectorStore = isolated_env["store"]
    registry: DocumentRegistryService = isolated_env["registry"]
    traces: TraceService = isolated_env["traces"]
    retriever: PandasStructuredDataRetriever = isolated_env["retriever"]

    monkeypatch.setattr(doc_mod, "document_service", registry)
    monkeypatch.setattr(ing_mod, "document_service", registry)
    monkeypatch.setattr(vs_mod, "vector_store", store)
    monkeypatch.setattr(ing_mod, "vector_store", store)

    # Seed one CSV for concurrent structured querying
    csv_path = isolated_env["processed_dir"] / "conc_csv.csv"
    csv_path.write_text("id,name,marks\n1,Alice,95\n2,Bob,82\n")

    shared_pdf = _make_sample_pdf_bytes(
        "Concurrent duplicate PDF stress test content for relational database systems and normalization."
    )

    def worker_unique_ingest(idx: int):
        pdf = _make_sample_pdf_bytes(f"Concurrent unique document payload #{idx} on relational systems.")
        return ingestion_service.process_file(file_bytes=pdf, file_name=f"conc_{idx}.pdf")

    def worker_dup_ingest(_: int):
        return ingestion_service.process_file(file_bytes=shared_pdf, file_name="shared_dup.pdf")

    def worker_query(idx: int):
        emb = embedding_service.embed_query(f"relational systems query {idx % 3}")
        vec_hits = store.query(ChromaVectorStore.COLLECTION_PDF, emb, top_k=3)
        csv_hits = retriever.retrieve("marks >= 90", "conc_csv", "conc.csv", top_k=2)
        traces.save_trace(
            request_id=f"req_conc_{idx}",
            query=f"query {idx}",
            scope="hybrid",
            trace_dict={"idx": idx, "vec_hits": len(vec_hits), "csv_hits": len(csv_hits)},
            latency_ms=5.0,
        )
        return len(csv_hits)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        unique_futs = [pool.submit(worker_unique_ingest, i) for i in range(5)]
        dup_futs = [pool.submit(worker_dup_ingest, i) for i in range(6)]
        query_futs = [pool.submit(worker_query, i) for i in range(12)]

        unique_docs = [f.result() for f in unique_futs]
        dup_docs = [f.result() for f in dup_futs]
        query_counts = [f.result() for f in query_futs]

    # All 5 unique docs + exactly 1 deduplicated shared doc = 6 total documents
    all_docs = registry.list_documents()
    assert len(all_docs) == 6
    assert len({d.document_id for d in dup_docs}) == 1
    assert sum(1 for d in dup_docs if not d.is_duplicate) == 1
    assert sum(1 for d in dup_docs if d.is_duplicate) == 5

    # Every unique doc exists in ChromaDB and registry reloaded cleanly from disk
    reloaded = DocumentRegistryService(registry_file=str(isolated_env["processed_dir"] / "registry.json"))
    assert len(reloaded.list_documents()) == 6
    for doc in unique_docs:
        assert store.document_exists(doc.document_id)

    # All concurrent SQLite trace writes survived without database-locked drops
    trace_stats = traces.get_stats()
    assert trace_stats["query_traces_count"] == 12
    assert trace_stats["journal_mode"].lower() == "wal"
    assert all(c == 1 for c in query_counts)

