import os
import uuid
import re
from typing import Optional
from fastapi import HTTPException
from app.core.config import settings
from app.core.logging import log_event
from app.models.document import DocumentMetadata
from app.services.pdf_service import pdf_parser
from app.services.chunking_service import chunking_service
from app.services.csv_service import csv_service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store, ChromaVectorStore
from app.services.document_service import document_service

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and special character attacks."""
    basename = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9_\.-]', '_', basename)
    return clean or "unnamed_file"

class IngestionService:
    """Unified service for ingesting, parsing, chunking, and indexing PDF and CSV documents."""

    def process_file(
        self,
        file_bytes: bytes,
        file_name: str,
        document_id: Optional[str] = None
    ) -> DocumentMetadata:
        clean_name = sanitize_filename(file_name)
        ext = clean_name.split(".")[-1].lower() if "." in clean_name else ""

        if ext not in ["pdf", "csv"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '.{ext}'. Only .pdf and .csv files are supported."
            )

        file_size = len(file_bytes)
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {settings.max_file_size_mb}MB."
            )

        if not document_id:
            prefix = "doc" if ext == "pdf" else "csv"
            document_id = f"{prefix}_{uuid.uuid4().hex[:10]}"

        file_path = os.path.join(settings.upload_dir, f"{document_id}_{clean_name}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        log_event("UPLOAD", f"Saved {ext.upper()} {clean_name} ({file_size} bytes) to {file_path}")

        # Register initial document record
        doc_record = DocumentMetadata(
            document_id=document_id,
            file_name=clean_name,
            file_type=ext,
            file_size=file_size,
            processing_status="processing"
        )
        document_service.register_document(doc_record)

        try:
            if ext == "pdf":
                extracted = pdf_parser.parse(file_path, document_id, clean_name)
                chunks = chunking_service.chunk_pdf(extracted)
                if not chunks:
                    raise ValueError("No text chunks could be created from this PDF.")

                chunk_texts = [c.text for c in chunks]
                embeddings = embedding_service.embed_documents(chunk_texts)
                for chunk, emb in zip(chunks, embeddings):
                    chunk.embedding = emb

                vector_store.add_chunks(ChromaVectorStore.COLLECTION_PDF, chunks)
                updated_doc = document_service.update_document(
                    document_id,
                    processing_status="completed",
                    chunk_count=len(chunks),
                    page_count=extracted.total_pages
                )
                log_event("UPLOAD", f"PDF {clean_name} indexed: {len(chunks)} chunks, {extracted.total_pages} pages")
                return updated_doc

            else:  # CSV
                processed_csv = csv_service.parse_csv(file_path, document_id, clean_name)
                
                # Embed dataset schema
                schema_emb = embedding_service.embed_text(processed_csv.schema_chunk.text)
                processed_csv.schema_chunk.embedding = schema_emb
                vector_store.add_chunks(ChromaVectorStore.COLLECTION_CSV_SCHEMAS, [processed_csv.schema_chunk])

                # Embed rows
                record_texts = [r.text for r in processed_csv.record_chunks]
                record_embeddings = embedding_service.embed_documents(record_texts)
                for record, emb in zip(processed_csv.record_chunks, record_embeddings):
                    record.embedding = emb

                vector_store.add_chunks(ChromaVectorStore.COLLECTION_CSV_RECORDS, processed_csv.record_chunks)
                updated_doc = document_service.update_document(
                    document_id,
                    processing_status="completed",
                    chunk_count=len(processed_csv.record_chunks),
                    row_count=processed_csv.row_count,
                    schema_summary=processed_csv.schema_text
                )
                log_event("UPLOAD", f"CSV {clean_name} indexed: {len(processed_csv.record_chunks)} rows")
                return updated_doc

        except Exception as e:
            err = str(e)
            log_event("ERROR", f"Processing failed for {clean_name}: {err}")
            document_service.update_document(
                document_id,
                processing_status="failed",
                error_message=err
            )
            raise HTTPException(status_code=422, detail=f"Failed to process {ext.upper()}: {err}")

ingestion_service = IngestionService()
