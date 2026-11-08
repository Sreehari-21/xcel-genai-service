import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.document import DocumentMetadata
from app.services.ingestion_service import ingestion_service, sanitize_filename

router = APIRouter(prefix="", tags=["Upload (Legacy)"])

@router.post("/upload/sample/{sample_name}", response_model=DocumentMetadata)
async def upload_sample(sample_name: str):
    """Load pre-generated realistic sample PDF or CSV dataset."""
    sample_file = sanitize_filename(sample_name)
    sample_path = os.path.join("./data/samples", sample_file)
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail=f"Sample file '{sample_name}' not found.")

    with open(sample_path, "rb") as f:
        file_bytes = f.read()

    document_id = f"sample_{uuid.uuid4().hex[:8]}"
    return ingestion_service.process_file(
        file_bytes=file_bytes,
        file_name=sample_file,
        document_id=document_id
    )

@router.post("/upload/pdf", response_model=DocumentMetadata)
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and process a PDF document with structure-aware chunking and vector indexing."""
    clean_name = sanitize_filename(file.filename)
    if not clean_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file format. Only PDF files are supported.")

    file_bytes = await file.read()
    return ingestion_service.process_file(file_bytes=file_bytes, file_name=clean_name)

@router.post("/upload/csv", response_model=DocumentMetadata)
async def upload_csv(file: UploadFile = File(...)):
    """Upload and process a structured CSV dataset with schema embedding and row indexing."""
    clean_name = sanitize_filename(file.filename)
    if not clean_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file format. Only CSV files are supported.")

    file_bytes = await file.read()
    return ingestion_service.process_file(file_bytes=file_bytes, file_name=clean_name)
