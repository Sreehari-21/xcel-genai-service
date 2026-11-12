from abc import ABC, abstractmethod
from collections import OrderedDict
import hashlib
import json
import os
import threading
import time
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
    """
    Thread-safe, persistent ChromaDB vector store with HNSW optimization,
    collection handle caching, safe metadata filter normalization,
    query result caching with write-through invalidation, and persistence diagnostics.
    """

    COLLECTION_PDF = "pdf_documents"
    COLLECTION_CSV_RECORDS = "csv_records"
    COLLECTION_CSV_SCHEMAS = "csv_schemas"
    ALL_COLLECTIONS = (COLLECTION_PDF, COLLECTION_CSV_RECORDS, COLLECTION_CSV_SCHEMAS)

    HNSW_METADATA = {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 128,
        "hnsw:search_ef": 64,
        "hnsw:M": 16,
    }

    def __init__(self, persist_directory: str = settings.chroma_dir, max_query_cache_size: int = 256):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)
        self._lock = threading.RLock()
        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collections: Dict[str, Any] = {}
        self._max_query_cache_size = max(1, max_query_cache_size)
        self._query_cache: OrderedDict[str, List[RetrievedChunk]] = OrderedDict()

        # Telemetry metrics
        self._query_cache_hits = 0
        self._query_cache_misses = 0
        self._total_queries = 0
        self._total_query_ms = 0.0
        self._total_inserts = 0
        self._total_chunks_inserted = 0
        self._total_insert_ms = 0.0

        self._init_collections()

    def _init_collections(self) -> None:
        with self._lock:
            for col in self.ALL_COLLECTIONS:
                self._get_or_cache_collection(col)

    def _get_or_cache_collection(self, collection_name: str):
        if collection_name not in self._collections:
            try:
                col = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata=dict(self.HNSW_METADATA)
                )
            except Exception:
                col = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            self._collections[collection_name] = col
        return self._collections[collection_name]

    def get_collection(self, collection_name: str):
        with self._lock:
            return self._get_or_cache_collection(collection_name)

    def _invalidate_query_cache(self) -> None:
        self._query_cache.clear()

    @staticmethod
    def _normalize_scalar(value: Any) -> Any:
        if hasattr(value, "item"):
            return value.item()
        return value

    @classmethod
    def _build_where_filter(cls, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Normalize user/service filters into valid ChromaDB `where` syntax.
        Supports:
          - Scalar key-value pairs: {"document_id": "doc_1", "page_number": 2}
          - List values (auto-mapped to $in): {"document_id": ["doc_1", "doc_2"]}
          - Chroma operator dicts: {"page_number": {"$gte": 2}} or {"$and": [...]} / {"$or": [...]}
        """
        if not filters:
            return None

        # Direct top-level logical operator
        if len(filters) == 1 and any(k in filters for k in ("$and", "$or")):
            return filters

        clauses: List[Dict[str, Any]] = []
        for raw_key, raw_val in filters.items():
            if raw_val is None:
                continue

            if raw_key in ("$and", "$or"):
                clauses.append({raw_key: raw_val})
                continue

            val = cls._normalize_scalar(raw_val)
            if isinstance(val, dict):
                # Operator dict like {"$gte": 2}
                clean_ops = {op: cls._normalize_scalar(op_v) for op, op_v in val.items() if op_v is not None}
                if clean_ops:
                    clauses.append({raw_key: clean_ops})
            elif isinstance(val, (list, tuple)):
                clean_list = [cls._normalize_scalar(item) for item in val if item is not None]
                if len(clean_list) == 1:
                    clauses.append({raw_key: clean_list[0]})
                elif len(clean_list) > 1:
                    clauses.append({raw_key: {"$in": clean_list}})
            elif isinstance(val, (str, int, float, bool)):
                clauses.append({raw_key: val})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _make_query_cache_key(
        collection_name: str,
        query_embedding: List[float],
        top_k: int,
        where_filter: Optional[Dict[str, Any]]
    ) -> str:
        # Quantize floats slightly only for digest stability across float repr
        emb_bytes = ",".join(f"{x:.6f}" for x in query_embedding).encode("utf-8")
        emb_digest = hashlib.sha256(emb_bytes).hexdigest()[:24]
        filter_str = json.dumps(where_filter, sort_keys=True) if where_filter else ""
        return f"{collection_name}|{top_k}|{emb_digest}|{filter_str}"

    def _validate_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        valid: List[Chunk] = []
        for chunk in chunks:
            if not chunk.id or not chunk.id.strip():
                raise ValueError("Chunk id cannot be empty.")
            if not chunk.embedding or not isinstance(chunk.embedding, list):
                raise ValueError(f"Chunk '{chunk.id}' is missing a valid embedding vector.")
            valid.append(chunk)
        return valid

    def add_chunks(self, collection_name: str, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        validated = self._validate_chunks(chunks)

        start = time.perf_counter()
        with self._lock:
            collection = self._get_or_cache_collection(collection_name)

            # Batch upsert to avoid ChromaDB SQLite variable / payload limits
            batch_size = 250
            for i in range(0, len(validated), batch_size):
                batch = validated[i : i + batch_size]
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

            self._invalidate_query_cache()
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._total_inserts += 1
            self._total_chunks_inserted += len(validated)
            self._total_insert_ms += elapsed_ms

        log_event(
            "VECTOR INSERTION",
            f"Upserted {len(validated)} chunks into collection {collection_name} in {round(elapsed_ms, 2)}ms"
        )

    def replace_document_chunks(self, collection_name: str, document_id: str, chunks: List[Chunk]) -> None:
        """
        Atomically replace all chunks belonging to `document_id` inside `collection_name`.
        Prevents stale/orphaned chunks when re-ingesting a document with fewer chunks.
        """
        validated = self._validate_chunks(chunks) if chunks else []
        with self._lock:
            collection = self._get_or_cache_collection(collection_name)
            try:
                collection.delete(where={"document_id": document_id})
            except Exception as e:
                log_event("WARN", f"Pre-replace delete failed for {document_id} in {collection_name}: {str(e)}")

            if validated:
                self.add_chunks(collection_name, validated)
            else:
                self._invalidate_query_cache()

    def query(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        if not query_embedding or top_k <= 0:
            return []

        where_filter = self._build_where_filter(filters)
        cache_key = self._make_query_cache_key(collection_name, query_embedding, top_k, where_filter)

        start = time.perf_counter()
        with self._lock:
            cached = self._query_cache.get(cache_key)
            if cached is not None:
                self._query_cache.move_to_end(cache_key)
                self._query_cache_hits += 1
                self._total_queries += 1
                return [c.model_copy(deep=True) for c in cached]

            self._query_cache_misses += 1
            collection = self._get_or_cache_collection(collection_name)
            col_count = collection.count()
            if col_count == 0:
                self._total_queries += 1
                return []

            n_results = min(top_k, col_count)

            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )
            except Exception as e:
                # Handle filtered subset smaller than requested n_results
                if where_filter is not None:
                    try:
                        matched = collection.get(where=where_filter, include=[])
                        matched_count = len(matched.get("ids", []))
                        if matched_count == 0:
                            self._total_queries += 1
                            return []
                        results = collection.query(
                            query_embeddings=[query_embedding],
                            n_results=min(n_results, matched_count),
                            where=where_filter,
                            include=["documents", "metadatas", "distances"]
                        )
                    except Exception as retry_err:
                        log_event("ERROR", f"ChromaDB query failed on {collection_name}: {str(retry_err)}")
                        return []
                else:
                    log_event("ERROR", f"ChromaDB query failed on {collection_name}: {str(e)}")
                    return []

            retrieved: List[RetrievedChunk] = []
            if results and results.get("ids") and results["ids"][0]:
                ids = results["ids"][0]
                docs = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]

                for rank, (chunk_id, doc, meta, dist) in enumerate(zip(ids, docs, metadatas, distances), start=1):
                    score = max(0.0, min(1.0, 1.0 - float(dist)))
                    retrieved.append(
                        RetrievedChunk(
                            id=chunk_id,
                            text=doc,
                            metadata=meta or {},
                            score=round(score, 4),
                            rank=rank
                        )
                    )

            # Populate bounded LRU cache
            self._query_cache[cache_key] = [c.model_copy(deep=True) for c in retrieved]
            while len(self._query_cache) > self._max_query_cache_size:
                self._query_cache.popitem(last=False)

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._total_queries += 1
            self._total_query_ms += elapsed_ms

            return retrieved

    def get_by_document_id(
        self,
        document_id: str,
        collection_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve all stored records and metadata for a given document_id."""
        target_cols = [collection_name] if collection_name else list(self.ALL_COLLECTIONS)
        items: List[Dict[str, Any]] = []
        with self._lock:
            for col_name in target_cols:
                col = self._get_or_cache_collection(col_name)
                try:
                    res = col.get(where={"document_id": document_id}, include=["documents", "metadatas"])
                    for cid, doc, meta in zip(
                        res.get("ids", []),
                        res.get("documents", []),
                        res.get("metadatas", [])
                    ):
                        items.append({
                            "collection": col_name,
                            "id": cid,
                            "text": doc,
                            "metadata": meta or {}
                        })
                except Exception as e:
                    log_event("ERROR", f"Failed to get {document_id} from {col_name}: {str(e)}")
        return items

    def document_exists(self, document_id: str) -> bool:
        """Check whether at least one vector chunk exists for `document_id`."""
        with self._lock:
            for col_name in self.ALL_COLLECTIONS:
                col = self._get_or_cache_collection(col_name)
                try:
                    res = col.get(where={"document_id": document_id}, limit=1, include=[])
                    if res and res.get("ids"):
                        return True
                except Exception:
                    continue
        return False

    def delete_by_document_id(self, document_id: str) -> None:
        log_event("RETRIEVAL", f"Deleting chunks for document_id={document_id} across collections")
        with self._lock:
            for col_name in self.ALL_COLLECTIONS:
                col = self._get_or_cache_collection(col_name)
                try:
                    col.delete(where={"document_id": document_id})
                except Exception as e:
                    log_event("ERROR", f"Failed to delete {document_id} from {col_name}: {str(e)}")
            self._invalidate_query_cache()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = {}
            for col_name in self.ALL_COLLECTIONS:
                col = self._get_or_cache_collection(col_name)
                stats[col_name] = col.count()
            return stats

    def get_disk_usage_bytes(self) -> int:
        total = 0
        if os.path.exists(self.persist_directory):
            for root, _, files in os.walk(self.persist_directory):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        total += os.path.getsize(fpath)
                    except OSError:
                        pass
        return total

    def verify_persistence(self) -> Dict[str, Any]:
        """
        Open an independent Chroma PersistentClient pointing at `self.persist_directory`
        to confirm all collections and counts are durable on disk.
        """
        fresh_client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        disk_counts = {}
        for col_name in self.ALL_COLLECTIONS:
            col = fresh_client.get_or_create_collection(name=col_name)
            disk_counts[col_name] = col.count()
        return {
            "persist_directory": self.persist_directory,
            "collection_counts": disk_counts,
            "total_vectors": sum(disk_counts.values()),
            "disk_usage_bytes": self.get_disk_usage_bytes()
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        with self._lock:
            total_lookups = self._query_cache_hits + self._query_cache_misses
            hit_rate = round(self._query_cache_hits / total_lookups, 4) if total_lookups > 0 else 0.0
            avg_query_ms = (
                round(self._total_query_ms / self._query_cache_misses, 3)
                if self._query_cache_misses > 0
                else 0.0
            )
            avg_insert_ms = (
                round(self._total_insert_ms / self._total_inserts, 3)
                if self._total_inserts > 0
                else 0.0
            )
            return {
                "collection_counts": self.get_stats(),
                "disk_usage_bytes": self.get_disk_usage_bytes(),
                "hnsw_config": dict(self.HNSW_METADATA),
                "query_cache_size": len(self._query_cache),
                "max_query_cache_size": self._max_query_cache_size,
                "query_cache_hits": self._query_cache_hits,
                "query_cache_misses": self._query_cache_misses,
                "query_cache_hit_rate": hit_rate,
                "total_queries": self._total_queries,
                "avg_uncached_query_ms": avg_query_ms,
                "total_inserts": self._total_inserts,
                "total_chunks_inserted": self._total_chunks_inserted,
                "avg_insert_ms": avg_insert_ms,
            }


# Singleton instance
vector_store = ChromaVectorStore()
