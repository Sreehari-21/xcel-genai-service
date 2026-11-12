from abc import ABC, abstractmethod
from collections import OrderedDict
import hashlib
import time
import threading
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.core.logging import log_event


class BaseEmbeddingService(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        pass


class SentenceTransformerEmbeddingService(BaseEmbeddingService):
    """
    Thread-safe local embedding service powered by SentenceTransformers.
    Features offline-first model loading, LRU query/text embedding caching,
    intra-batch deduplication, and performance telemetry.
    """

    DEFAULT_DIMENSION = 384

    def __init__(self, model_name: str = settings.embedding_model, max_cache_size: int = 1024):
        self.model_name = model_name
        self.max_cache_size = max(1, max_cache_size)
        self._model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None
        self._load_lock = threading.Lock()
        self._encode_lock = threading.RLock()
        self._cache_lock = threading.RLock()
        self._cache: OrderedDict[str, List[float]] = OrderedDict()

        # Telemetry metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_texts_embedded = 0
        self._total_queries_embedded = 0
        self._total_batches = 0
        self._total_encode_ms = 0.0
        self._model_load_ms: Optional[float] = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    start = time.perf_counter()
                    log_event("EMBEDDING", f"Loading embedding model: {self.model_name}")
                    try:
                        # Prefer local HuggingFace cache first to prevent offline network timeouts
                        self._model = SentenceTransformer(self.model_name, local_files_only=True)
                    except Exception:
                        log_event("EMBEDDING", f"Model {self.model_name} not in local cache; fetching from Hub")
                        self._model = SentenceTransformer(self.model_name)
                    if hasattr(self._model, "get_embedding_dimension"):
                        self._dimension = self._model.get_embedding_dimension() or self.DEFAULT_DIMENSION
                    else:
                        self._dimension = self._model.get_sentence_embedding_dimension() or self.DEFAULT_DIMENSION
                    self._model_load_ms = round((time.perf_counter() - start) * 1000, 2)
                    log_event(
                        "EMBEDDING",
                        f"Embedding model {self.model_name} loaded (dim={self._dimension}) in {self._model_load_ms}ms"
                    )
        return self._model

    def get_dimension(self) -> int:
        if self._dimension is not None:
            return self._dimension
        if self._model is not None:
            if hasattr(self._model, "get_embedding_dimension"):
                self._dimension = self._model.get_embedding_dimension() or self.DEFAULT_DIMENSION
            else:
                self._dimension = self._model.get_sentence_embedding_dimension() or self.DEFAULT_DIMENSION
            return self._dimension
        return self.DEFAULT_DIMENSION

    @staticmethod
    def _cache_key(text: str) -> str:
        normalized = text.strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[List[float]]:
        with self._cache_lock:
            vec = self._cache.get(key)
            if vec is not None:
                self._cache.move_to_end(key)
                self._cache_hits += 1
                return list(vec)
            self._cache_misses += 1
            return None

    def _cache_put(self, key: str, vec: List[float]) -> None:
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = list(vec)
            while len(self._cache) > self.max_cache_size:
                self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.get_dimension()

        key = self._cache_key(text)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        model = self._get_model()
        start = time.perf_counter()
        with self._encode_lock:
            embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        elapsed_ms = (time.perf_counter() - start) * 1000

        vec = embedding.tolist()
        self._cache_put(key, vec)
        with self._cache_lock:
            self._total_texts_embedded += 1
            self._total_encode_ms += elapsed_ms
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        uncached_map: Dict[str, List[int]] = {}
        uncached_texts: List[str] = []
        uncached_keys: List[str] = []

        # Deduplicate intra-batch texts and satisfy cache hits before encoding
        for idx, text in enumerate(texts):
            if not text or not text.strip():
                results[idx] = [0.0] * self.get_dimension()
                continue
            key = self._cache_key(text)
            cached = self._cache_get(key)
            if cached is not None:
                results[idx] = cached
            else:
                if key not in uncached_map:
                    uncached_map[key] = []
                    uncached_texts.append(text)
                    uncached_keys.append(key)
                uncached_map[key].append(idx)

        if uncached_texts:
            model = self._get_model()
            log_event(
                "EMBEDDING",
                f"Generating embeddings for {len(uncached_texts)} unique chunks (total requested: {len(texts)})"
            )
            start = time.perf_counter()
            with self._encode_lock:
                embeddings = model.encode(
                    uncached_texts,
                    batch_size=32,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
            elapsed_ms = (time.perf_counter() - start) * 1000

            vecs = embeddings.tolist()
            for key, vec in zip(uncached_keys, vecs):
                self._cache_put(key, vec)
                for target_idx in uncached_map[key]:
                    results[target_idx] = list(vec)

            with self._cache_lock:
                self._total_texts_embedded += len(uncached_texts)
                self._total_batches += 1
                self._total_encode_ms += elapsed_ms

        return [r if r is not None else [0.0] * self.get_dimension() for r in results]

    def embed_query(self, query: str) -> List[float]:
        with self._cache_lock:
            self._total_queries_embedded += 1
        return self.embed_text(query)

    def get_stats(self) -> Dict[str, Any]:
        with self._cache_lock:
            total_lookups = self._cache_hits + self._cache_misses
            hit_rate = round((self._cache_hits / total_lookups), 4) if total_lookups > 0 else 0.0
            avg_encode_ms = (
                round(self._total_encode_ms / self._total_texts_embedded, 3)
                if self._total_texts_embedded > 0
                else 0.0
            )
            return {
                "model_name": self.model_name,
                "model_loaded": self._model is not None,
                "model_load_ms": self._model_load_ms,
                "embedding_dimension": self.get_dimension(),
                "cache_size": len(self._cache),
                "max_cache_size": self.max_cache_size,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_hit_rate": hit_rate,
                "total_texts_embedded": self._total_texts_embedded,
                "total_queries_embedded": self._total_queries_embedded,
                "total_batches": self._total_batches,
                "avg_encode_ms_per_text": avg_encode_ms,
            }


# Singleton instance
embedding_service = SentenceTransformerEmbeddingService()
