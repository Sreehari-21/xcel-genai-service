from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Security
from app.models.document import DocumentMetadata, DocumentListResponse, DocumentUploadResponse
from app.services.ingestion_service import ingestion_service
from app.services.document_service import document_service
from app.core.auth import verify_api_key

router = APIRouter(prefix="/api/v1/documents", tags=["Documents (v1)"])

@router.post("/upload", response_model=DocumentUploadResponse, dependencies=[Depends(verify_api_key)])
async def upload_document(file: UploadFile = File(...)):
    """
    Standardized document upload supporting both PDF and CSV files.
    Extracts text/tables, performs structure-aware chunking, generates embeddings,
    and indexes into ChromaDB.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    metadata = ingestion_service.process_file(file_bytes=content, file_name=file.filename)
    return DocumentUploadResponse(
        document_id=metadata.document_id,
        file_name=metadata.file_name,
        file_type=metadata.file_type,
        processing_status=metadata.processing_status,
        page_count=metadata.page_count,
        row_count=metadata.row_count,
        chunk_count=metadata.chunk_count,
        file_size=metadata.file_size,
        upload_time=metadata.upload_time
    )

@router.get("", response_model=DocumentListResponse, dependencies=[Depends(verify_api_key)])
async def list_documents():
    """Retrieve all indexed PDF and CSV documents and their processing metadata."""
    docs = document_service.list_documents()
    return DocumentListResponse(documents=docs, total_count=len(docs))

@router.delete("/{document_id}", dependencies=[Depends(verify_api_key)])
async def delete_document(document_id: str):
    """Safely delete a document and purge all associated vector embeddings and cached records."""
    success = document_service.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document with ID '{document_id}' not found.")
    return {
        "status": "success",
        "message": f"Document '{document_id}' and all associated vector embeddings deleted successfully."
    }

