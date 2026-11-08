from typing import Optional
from app.core.config import settings
from app.services.llm_base import BaseLLMService
from app.services.openai_service import openai_service
from app.services.claude_service import claude_service
from app.services.ollama_service import ollama_service

def get_llm_service(provider: Optional[str] = None) -> BaseLLMService:
    """
    Factory function returning the active LLM provider service.
    Supported: 'openai', 'claude' (or 'anthropic'), 'ollama'.
    Defaults to settings.llm_provider.
    """
    selected = (provider or settings.llm_provider).lower().strip()
    if selected == "ollama":
        return ollama_service
    elif selected in ["claude", "anthropic"]:
        return claude_service
    else:
        return openai_service
