import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "stage": getattr(record, "stage", "GENERAL"),
            "message": record.getMessage(),
        }
        
        # Include custom attributes if passed in extra
        details = getattr(record, "details", None)
        if details and isinstance(details, dict):
            # Sanitize any accidental sensitive keys
            sanitized = {}
            for k, v in details.items():
                if any(sec in k.lower() for sec in ["key", "secret", "password", "token", "auth"]):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = v
            log_obj["details"] = sanitized
            
        return json.dumps(log_obj)

def get_logger(name: str = "rag_pipeline") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger

logger = get_logger("rag_pipeline")

def log_event(stage: str, message: str, details: Optional[Dict[str, Any]] = None, level: int = logging.INFO):
    """
    Log structured event conforming to standard RAG pipeline stages:
    UPLOAD, PDF EXTRACTION, CSV PROCESSING, CHUNKING, EMBEDDING,
    VECTOR INSERTION, QUERY, RETRIEVAL, RERANKING, CLAUDE REQUEST,
    CLAUDE RESPONSE, ERROR
    """
    logger.log(level, message, extra={"stage": stage, "details": details or {}})
