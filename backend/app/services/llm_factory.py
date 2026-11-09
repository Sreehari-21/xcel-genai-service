from typing import Optional
from app.core.config import settings
from app.services.llm_base import BaseLLMService
from app.services.ollama_service import ollama_service

def get_llm_service(provider: Optional[str] = None) -> BaseLLMService:
    """
    Factory function returning the active LLM provider service.
    Active provider: Ollama (qwen2.5:7b) at localhost:11434.
    100% Local Ollama architecture.
    """
    return ollama_service
