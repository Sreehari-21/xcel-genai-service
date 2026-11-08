from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ChunkMetadata(BaseModel):
    source_type: str  # 'pdf', 'csv', 'csv_schema'
    document_id: str
    document_name: str
    chunk_id: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    row_number: Optional[int] = None
    columns: Optional[List[str]] = None
    additional_meta: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def to_chroma_dict(self) -> Dict[str, Any]:
        """Flatten or stringify metadata to satisfy ChromaDB requirements (scalars only)."""
        data: Dict[str, Any] = {
            "source_type": self.source_type,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "chunk_id": self.chunk_id,
        }
        if self.page_number is not None:
            data["page_number"] = int(self.page_number)
        if self.section is not None:
            data["section"] = str(self.section)
        if self.row_number is not None:
            data["row_number"] = int(self.row_number)
        if self.columns is not None:
            data["columns"] = ",".join(self.columns)
            
        if self.additional_meta:
            for k, v in self.additional_meta.items():
                if isinstance(v, (str, int, float, bool)):
                    data[k] = v
                else:
                    data[k] = str(v)
        return data

class Chunk(BaseModel):
    id: str
    text: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None
