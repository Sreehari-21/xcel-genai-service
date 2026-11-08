from fastapi import APIRouter, HTTPException
from app.models.document import DocumentListResponse
from app.services.document_service import document_service
from app.api.v1.health import get_health_status

router = APIRouter(prefix="", tags=["Documents (Legacy)"])

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """Retrieve all indexed PDF and CSV documents and their processing metadata."""
    docs = document_service.list_documents()
    return DocumentListResponse(documents=docs, total_count=len(docs))

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and purge all associated vector embeddings and cached records."""
    success = document_service.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document with ID '{document_id}' not found.")
    return {"status": "success", "message": f"Document '{document_id}' deleted successfully."}

@router.get("/health")
async def health_check():
    """System health inspection and vector store diagnostic statistics."""
    return get_health_status()
