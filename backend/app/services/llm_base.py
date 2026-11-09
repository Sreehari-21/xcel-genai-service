from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.services.trace_service import trace_service

SYSTEM_PROMPT = """You are a retrieval-augmented AI assistant specialized in analyzing PDF documents and structured CSV datasets.

Answer the user's question using the provided retrieved context.

Rules:
1. Use the retrieved context as the primary source of truth.
2. Do not fabricate facts or invent details not present in the context.
3. If the retrieved context does not contain enough information to answer the question, clearly state that the provided documents do not contain the answer.
4. For PDF information, cite the document name and page number (e.g., [Document: dbms.pdf, Page: 42]).
5. For CSV information, cite the file name and row number when applicable (e.g., [File: students.csv, Row: 105]).
6. When combining information from both PDF and CSV sources, clearly distinguish between them.
7. For numerical questions, preserve the original values accurately.
8. If a calculation is required, calculate it explicitly and accurately using the given numbers.
9. Do not claim that information exists if it was not retrieved.
10. Provide concise, well-structured, and helpful answers formatted in clean Markdown."""

class ConversationManager:
    """Manages multi-turn conversation messages with SQLite persistence."""
    def __init__(self, max_history_turns: int = 6):
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        self.max_history_turns = max_history_turns

    def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        if conversation_id not in self.conversations:
            # Load from persistent SQLite
            loaded = trace_service.get_conversation_history(conversation_id, self.max_history_turns)
            self.conversations[conversation_id] = loaded
        return self.conversations.get(conversation_id, [])

    def add_turn(self, conversation_id: str, user_msg: str, assistant_msg: str):
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append({"role": "user", "content": user_msg})
        self.conversations[conversation_id].append({"role": "assistant", "content": assistant_msg})
        
        # Persist to SQLite
        trace_service.save_conversation_turn(conversation_id, "user", user_msg)
        trace_service.save_conversation_turn(conversation_id, "assistant", assistant_msg)

        # Keep within max history limit
        if len(self.conversations[conversation_id]) > self.max_history_turns * 2:
            self.conversations[conversation_id] = self.conversations[conversation_id][-(self.max_history_turns * 2):]

    def clear(self, conversation_id: str):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

class BaseLLMService(ABC):
    """Abstract Base Class for LLM providers."""

    @abstractmethod
    def generate_answer(
        self,
        query: str,
        context: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate answer via LLM given retrieved context and optional multi-turn conversation ID.
        Must return a dict:
        {
            "answer": str,
            "model_used": str,
            "usage": {"input_tokens": int, "output_tokens": int},
            "error": bool (optional)
        }
        """
        pass

