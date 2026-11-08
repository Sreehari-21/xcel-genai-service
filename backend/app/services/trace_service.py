import os
import json
import sqlite3
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging import log_event

class TraceService:
    """Persistent SQLite store for query execution traces and diagnostics."""

    def __init__(self, db_path: str = settings.sqlite_db_path):
        self.db_path = db_path
        Path(os.path.dirname(self.db_path)).mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_traces (
                    request_id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    scope TEXT,
                    created_at TEXT NOT NULL,
                    total_latency_ms REAL,
                    llm_provider TEXT,
                    llm_model TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    trace_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_id ON conversation_turns(conversation_id)")
            conn.commit()

    def sanitize_trace(self, trace_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy and sanitize trace to ensure no sensitive tokens or secrets are exposed."""
        sanitized = json.loads(json.dumps(trace_dict))

        # Redact any accidental keys or headers
        def redact(obj):
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    if any(secret in k.lower() for secret in ["key", "token", "secret", "password", "auth"]):
                        obj[k] = "[REDACTED]"
                    else:
                        redact(v)
            elif isinstance(obj, list):
                for item in obj:
                    redact(item)

        redact(sanitized)
        return sanitized

    def save_trace(
        self,
        request_id: str,
        query: str,
        scope: str,
        trace_dict: Dict[str, Any],
        latency_ms: float = 0.0,
        llm_provider: str = "",
        llm_model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> None:
        """Persist sanitized trace into SQLite."""
        try:
            sanitized = self.sanitize_trace(trace_dict)
            created_at = datetime.datetime.utcnow().isoformat()
            trace_json = json.dumps(sanitized)

            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO query_traces (
                        request_id, query, scope, created_at,
                        total_latency_ms, llm_provider, llm_model,
                        input_tokens, output_tokens, trace_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id, query, scope, created_at,
                        latency_ms, llm_provider, llm_model,
                        input_tokens, output_tokens, trace_json
                    )
                )
                conn.commit()

            log_event("QUERY", f"Saved persistent trace for request_id: {request_id}")
        except Exception as e:
            log_event("ERROR", f"Failed to persist trace for request_id {request_id}: {str(e)}")

    def get_trace(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve trace by request_id."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM query_traces WHERE request_id = ?",
                    (request_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None

                trace_data = json.loads(row["trace_json"])
                return {
                    "request_id": row["request_id"],
                    "query": row["query"],
                    "scope": row["scope"],
                    "created_at": row["created_at"],
                    "total_latency_ms": row["total_latency_ms"],
                    "llm_provider": row["llm_provider"],
                    "llm_model": row["llm_model"],
                    "tokens_usage": {
                        "input_tokens": row["input_tokens"],
                        "output_tokens": row["output_tokens"]
                    },
                    "trace": trace_data
                }
        except Exception as e:
            log_event("ERROR", f"Failed to load trace {request_id}: {str(e)}")
            return None

    def save_conversation_turn(self, conversation_id: str, role: str, content: str) -> None:
        """Persist conversation message turn."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO conversation_turns (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (conversation_id, role, content, datetime.datetime.utcnow().isoformat())
                )
                conn.commit()
        except Exception as e:
            log_event("ERROR", f"Failed to save conversation turn for {conversation_id}: {str(e)}")

    def get_conversation_history(self, conversation_id: str, max_turns: int = 6) -> List[Dict[str, str]]:
        """Retrieve recent conversation turns from SQLite."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT role, content FROM conversation_turns
                    WHERE conversation_id = ?
                    ORDER BY id ASC
                    """,
                    (conversation_id,)
                )
                rows = cursor.fetchall()
                history = [{"role": r["role"], "content": r["content"]} for r in rows]
                if len(history) > max_turns * 2:
                    history = history[-(max_turns * 2):]
                return history
        except Exception as e:
            log_event("ERROR", f"Failed to retrieve conversation history for {conversation_id}: {str(e)}")
            return []

trace_service = TraceService()

