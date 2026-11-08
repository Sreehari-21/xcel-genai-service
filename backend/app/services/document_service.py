import os
import json
import threading
from typing import List, Optional, Dict
from app.core.config import settings
from app.core.logging import log_event
from app.models.document import DocumentMetadata
from app.services.vector_store import vector_store

class DocumentRegistryService:
    def __init__(self, registry_file: str = os.path.join(settings.processed_dir, "registry.json")):
        self.registry_file = registry_file
        self._lock = threading.Lock()
        self._registry: Dict[str, DocumentMetadata] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for doc_id, doc_dict in data.items():
                        self._registry[doc_id] = DocumentMetadata(**doc_dict)
            except Exception as e:
                log_event("ERROR", f"Failed to load document registry: {str(e)}")

    def _save(self):
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                data = {doc_id: doc.model_dump() for doc_id, doc in self._registry.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            log_event("ERROR", f"Failed to save document registry: {str(e)}")

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
        return self._registry.get(doc_id)

    def list_documents(self) -> List[DocumentMetadata]:
        return list(self._registry.values())

    def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id not in self._registry:
                return False
            doc = self._registry.pop(doc_id)
            self._save()

        # Delete from vector database
        vector_store.delete_by_document_id(doc_id)

        # Clean up files in uploads and processed
        for folder in [settings.upload_dir, settings.processed_dir]:
            for f in os.listdir(folder):
                if f.startswith(doc_id):
                    try:
                        os.remove(os.path.join(folder, f))
                    except Exception:
                        pass

        log_event("UPLOAD", f"Document {doc.file_name} ({doc_id}) deleted successfully")
        return True

document_service = DocumentRegistryService()
