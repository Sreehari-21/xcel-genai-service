from typing import Optional
from app.core.config import settings
from app.services.llm_base import BaseLLMService
from app.services.ollama_service import ollama_service
from app.services.claude_service import claude_service

def get_llm_service(provider: Optional[str] = None) -> BaseLLMService:
    """
    Factory function returning the active LLM provider service.
    Active provider: Ollama (qwen2.5:7b) at localhost:11434.
    OpenAI has been removed from the active generation execution path.
    """
    selected = (provider or settings.llm_provider).lower().strip()
    if selected in ["claude", "anthropic"]:
        return claude_service
    # Default active provider is Ollama with qwen2.5:7b
    return ollama_service
