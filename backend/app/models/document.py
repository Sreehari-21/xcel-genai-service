from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentMetadata(BaseModel):
    document_id: str
    file_name: str
    file_type: str  # 'pdf' or 'csv'
    file_size: int
    upload_time: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    processing_status: str = "processing"  # 'processing', 'completed', 'failed'
    chunk_count: int = 0
    row_count: Optional[int] = None
    page_count: Optional[int] = None
    error_message: Optional[str] = None
    schema_summary: Optional[str] = None

class DocumentUploadResponse(BaseModel):
    document_id: str
    file_name: str
    file_type: str
    processing_status: str
    page_count: Optional[int] = None
    row_count: Optional[int] = None
    chunk_count: int
    file_size: Optional[int] = None
    upload_time: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentMetadata]
    total_count: int
