import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str
    top_k: int = 8
    conversation_id: Optional[str] = None
    scope: Optional[str] = Field(default="hybrid", description="Retrieval scope: 'hybrid', 'pdf', or 'csv'")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SourceCitation(BaseModel):
    source_type: str  # 'pdf', 'csv', 'csv_schema'
    file_name: str
    document_id: Optional[str] = None
    page: Optional[int] = None
    row: Optional[int] = None
    chunk_id: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None

class RetrievedChunk(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float
    rank: int

class QueryResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    answer: str
    sources: List[SourceCitation]
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[str] = None
    
    # Backwards compatibility fields for frontend & legacy consumers
    retrieved_chunks: Optional[List[RetrievedChunk]] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    pipeline_trace: Optional[Dict[str, Any]] = None

class QueryTraceResponse(BaseModel):
    request_id: str
    query: str
    scope: Optional[str] = None
    created_at: str
    total_latency_ms: float
    llm_provider: str
    llm_model: str
    tokens_usage: Dict[str, int] = Field(default_factory=dict)
    trace: Dict[str, Any]
