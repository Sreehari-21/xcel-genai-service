import pytest
import pymupdf
from app.services.pdf_service import pdf_parser
from app.services.chunking_service import chunking_service
from app.services.csv_service import csv_service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store, ChromaVectorStore
from app.services.retrieval_service import retrieval_service
from app.services.document_service import document_service
from app.models.document import DocumentMetadata

@pytest.fixture(scope="module")
def setup_hybrid_data(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("hybrid_data")
    
    # 1. Setup PDF
    pdf_path = str(tmp_path / "dbms.pdf")
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 72), "Database Normalization Theory\n\nSection: Normalization\nNormalization is a systematic approach of decomposing tables to eliminate data redundancy and anomalies in relational database design.", fontsize=12)
    doc.save(pdf_path)
    doc.close()

    extracted_pdf = pdf_parser.parse(pdf_path, "doc_hybrid_pdf", "dbms.pdf")
    pdf_chunks = chunking_service.chunk_pdf(extracted_pdf)
    pdf_texts = [c.text for c in pdf_chunks]
    pdf_embs = embedding_service.embed_documents(pdf_texts)
    for c, emb in zip(pdf_chunks, pdf_embs):
        c.embedding = emb
    vector_store.add_chunks(ChromaVectorStore.COLLECTION_PDF, pdf_chunks)
    document_service.register_document(
        DocumentMetadata(
            document_id="doc_hybrid_pdf",
            file_name="dbms.pdf",
            file_type="pdf",
            file_size=1024,
            processing_status="completed",
            chunk_count=len(pdf_chunks),
            page_count=1
        )
    )

    # 2. Setup CSV
    csv_path = str(tmp_path / "students.csv")
    with open(csv_path, "w") as f:
        f.write("student_id,name,semester,subject,marks\n101,Akhil,6,DBMS,85\n102,Rahul,6,DBMS,72\n103,Anu,6,DBMS,95\n")
    
    processed_csv = csv_service.parse_csv(csv_path, "csv_hybrid_data", "students.csv")
    schema_emb = embedding_service.embed_text(processed_csv.schema_chunk.text)
    processed_csv.schema_chunk.embedding = schema_emb
    vector_store.add_chunks(ChromaVectorStore.COLLECTION_CSV_SCHEMAS, [processed_csv.schema_chunk])

    record_texts = [r.text for r in processed_csv.record_chunks]
    record_embs = embedding_service.embed_documents(record_texts)
    for r, emb in zip(processed_csv.record_chunks, record_embs):
        r.embedding = emb
    vector_store.add_chunks(ChromaVectorStore.COLLECTION_CSV_RECORDS, processed_csv.record_chunks)
    document_service.register_document(
        DocumentMetadata(
            document_id="csv_hybrid_data",
            file_name="students.csv",
            file_type="csv",
            file_size=512,
            processing_status="completed",
            chunk_count=len(processed_csv.record_chunks),
            row_count=3
        )
    )

    yield {"pdf_id": "doc_hybrid_pdf", "csv_id": "csv_hybrid_data"}
    document_service.delete_document("doc_hybrid_pdf")
    document_service.delete_document("csv_hybrid_data")

def test_pdf_retrieval(setup_hybrid_data):
    top_chunks, context, citations, trace = retrieval_service.retrieve(
        query="Explain database normalization",
        top_k=3,
        filters={"source_type": "pdf"}
    )
    assert len(top_chunks) > 0
    assert any(c.metadata.get("source_type") == "pdf" for c in top_chunks)
    assert "dbms.pdf" in context
    assert any(cit.source_type == "pdf" and cit.file_name == "dbms.pdf" for cit in citations)

def test_csv_retrieval(setup_hybrid_data):
    top_chunks, context, citations, trace = retrieval_service.retrieve(
        query="Which student scored 95 in DBMS?",
        top_k=3,
        filters={"source_type": "csv"}
    )
    assert len(top_chunks) > 0
    assert any("Anu" in c.text for c in top_chunks)
    assert "students.csv" in context

def test_mixed_hybrid_retrieval(setup_hybrid_data):
    # Unified query requiring both sources
    top_chunks, context, citations, trace = retrieval_service.retrieve(
        query="Based on the DBMS normalization concept and student records, who took DBMS?",
        top_k=6,
        filters=None
    )
    source_types = [c.metadata.get("source_type") for c in top_chunks]
    assert "pdf" in source_types
    assert ("csv" in source_types or "csv_schema" in source_types)
    assert len(citations) >= 2
