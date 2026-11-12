import os
import json
import threading
import time
from typing import List, Optional, Dict
from app.core.config import settings
from app.core.logging import log_event
from app.models.document import DocumentMetadata
from app.services.vector_store import vector_store
from app.services.structured_data_retriever import structured_retriever


class DocumentRegistryService:
    """
    Thread-safe, atomic JSON registry tracking ingested PDF/CSV documents,
    content hashes for deduplication, and processing lifecycles.
    """

    def __init__(self, registry_file: Optional[str] = None):
        self._explicit_registry_file = registry_file
        self._lock = threading.RLock()
        self._registry: Dict[str, DocumentMetadata] = {}
        self._load()

    @property
    def registry_file(self) -> str:
        if self._explicit_registry_file:
            return self._explicit_registry_file
        return os.path.join(settings.processed_dir, "registry.json")

    def _load(self) -> None:
        with self._lock:
            self._registry.clear()
            if os.path.exists(self.registry_file):
                try:
                    with open(self.registry_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for doc_id, doc_dict in data.items():
                            self._registry[doc_id] = DocumentMetadata(**doc_dict)
                except Exception as e:
                    log_event("ERROR", f"Failed to load document registry: {str(e)}")

    def _save(self) -> None:
        with self._lock:
            os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
            tmp_file = f"{self.registry_file}.{threading.get_ident()}.tmp"
            try:
                data = {doc_id: doc.model_dump() for doc_id, doc in self._registry.items()}
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                # Atomic replace with brief retry on Windows file contention
                for attempt in range(5):
                    try:
                        os.replace(tmp_file, self.registry_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.02 * (attempt + 1))
            except Exception as e:
                log_event("ERROR", f"Failed to save document registry: {str(e)}")
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except OSError:
                        pass

    def reload(self) -> None:
        """Reload registry state directly from disk."""
        self._load()

    def register_document(self, doc: DocumentMetadata) -> None:
        with self._lock:
            self._registry[doc.document_id] = doc
            self._save()
        log_event("UPLOAD", f"Document registered: {doc.file_name} ({doc.document_id})")

    def update_document(self, doc_id: str, **kwargs) -> Optional[DocumentMetadata]:
        with self._lock:
            if doc_id in self._registry:
                doc = self._registry[doc_id]
                updated_data = doc.model_dump()
                updated_data.update(kwargs)
                self._registry[doc_id] = DocumentMetadata(**updated_data)
                self._save()
                return self._registry[doc_id]
        return None

    def get_document(self, doc_id: str) -> Optional[DocumentMetadata]:
        with self._lock:
            return self._registry.get(doc_id)

    def find_by_hash(self, content_hash: str) -> Optional[DocumentMetadata]:
        """Find an already completed document matching the given SHA-256 content hash."""
        if not content_hash:
            return None
        with self._lock:
            for doc in self._registry.values():
                if doc.content_hash == content_hash and doc.processing_status == "completed":
                    return doc
        return None

    def list_documents(self) -> List[DocumentMetadata]:
        with self._lock:
            return list(self._registry.values())

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id not in self._registry:
                return False
            doc = self._registry.pop(doc_id)
            self._save()

        # Invalidate structured CSV cache and purge from vector store
        structured_retriever.invalidate_cache(doc_id)
        vector_store.delete_by_document_id(doc_id)

        # Clean up files in uploads and processed
        for folder in [settings.upload_dir, settings.processed_dir]:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.startswith(doc_id):
                        try:
                            os.remove(os.path.join(folder, f))
                        except Exception:
                            pass

        log_event("UPLOAD", f"Document {doc.file_name} ({doc_id}) deleted successfully")
        return True


document_service = DocumentRegistryService()
