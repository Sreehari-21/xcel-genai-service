from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.core.logging import log_event
from app.models.chunk import Chunk
from app.models.query import RetrievedChunk

class BaseVectorStore(ABC):
    @abstractmethod
    def add_chunks(self, collection_name: str, chunks: List[Chunk]) -> None:
        pass

    @abstractmethod
    def query(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        pass

    @abstractmethod
    def delete_by_document_id(self, document_id: str) -> None:
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        pass

class ChromaVectorStore(BaseVectorStore):
    COLLECTION_PDF = "pdf_documents"
    COLLECTION_CSV_RECORDS = "csv_records"
    COLLECTION_CSV_SCHEMAS = "csv_schemas"

    def __init__(self, persist_directory: str = settings.chroma_dir):
        self.persist_directory = persist_directory
        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._init_collections()

    def _init_collections(self):
        for col in [self.COLLECTION_PDF, self.COLLECTION_CSV_RECORDS, self.COLLECTION_CSV_SCHEMAS]:
            self._client.get_or_create_collection(
                name=col,
                metadata={"hnsw:space": "cosine"}
            )

    def get_collection(self, collection_name: str):
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, collection_name: str, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        collection = self.get_collection(collection_name)
        
        # Batch insert to avoid ChromaDB batch limits
        batch_size = 250
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            ids = [c.id for c in batch]
            documents = [c.text for c in batch]
            embeddings = [c.embedding for c in batch]
            metadatas = [c.metadata.to_chroma_dict() for c in batch]

            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
        log_event("VECTOR INSERTION", f"Inserted {len(chunks)} chunks into collection {collection_name}")

    def query(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        collection = self.get_collection(collection_name)
        
        # Format filters for ChromaDB if provided
        where_filter = None
        if filters:
            # Clean filters to only contain non-empty scalar values
            valid_filters = {k: v for k, v in filters.items() if v is not None and not isinstance(v, (list, dict))}
            if len(valid_filters) == 1:
                where_filter = valid_filters
            elif len(valid_filters) > 1:
                where_filter = {"$and": [{k: v} for k, v in valid_filters.items()]}

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            log_event("ERROR", f"ChromaDB query failed on {collection_name}: {str(e)}")
            return []

        retrieved: List[RetrievedChunk] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return retrieved

        ids = results["ids"][0]
        docs = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for rank, (chunk_id, doc, meta, dist) in enumerate(zip(ids, docs, metadatas, distances), start=1):
            # Convert cosine distance to cosine similarity score (score = 1 - distance)
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            retrieved.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=doc,
                    metadata=meta,
                    score=round(score, 4),
                    rank=rank
                )
            )
        return retrieved

    def delete_by_document_id(self, document_id: str) -> None:
        log_event("RETRIEVAL", f"Deleting chunks for document_id={document_id} across collections")
        for col_name in [self.COLLECTION_PDF, self.COLLECTION_CSV_RECORDS, self.COLLECTION_CSV_SCHEMAS]:
            col = self.get_collection(col_name)
            try:
                col.delete(where={"document_id": document_id})
            except Exception as e:
                log_event("ERROR", f"Failed to delete {document_id} from {col_name}: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        stats = {}
        for col_name in [self.COLLECTION_PDF, self.COLLECTION_CSV_RECORDS, self.COLLECTION_CSV_SCHEMAS]:
            col = self.get_collection(col_name)
            stats[col_name] = col.count()
        return stats

# Singleton instance
vector_store = ChromaVectorStore()
