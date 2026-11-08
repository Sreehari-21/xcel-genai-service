from abc import ABC, abstractmethod
from typing import List
import threading
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
    def __init__(self, model_name: str = settings.embedding_model):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    log_event("EMBEDDING", f"Loading embedding model: {self.model_name}")
                    self._model = SentenceTransformer(self.model_name)
                    log_event("EMBEDDING", f"Embedding model {self.model_name} loaded successfully")
        return self._model

    def embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        log_event("EMBEDDING", f"Generating embeddings for {len(texts)} document chunks")
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        return self.embed_text(query)

# Singleton instance
embedding_service = SentenceTransformerEmbeddingService()
