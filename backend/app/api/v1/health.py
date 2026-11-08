from fastapi import APIRouter
from app.core.config import settings
from app.services.document_service import document_service
from app.services.vector_store import vector_store

router = APIRouter(tags=["Health"])

def get_health_status():
    vector_stats = vector_store.get_stats()
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        active_model = settings.ollama_model
    elif provider in ["claude", "anthropic"]:
        active_model = settings.claude_model
    else:
        active_model = settings.openai_model

    return {
        "status": "healthy",
        "service": "xcel-rag",
        "version": settings.service_version,
        "llm_provider": settings.llm_provider,
        "configured_model": active_model,
        "openai_model": settings.openai_model,
        "openai_api_key_configured": bool(settings.openai_api_key and not settings.openai_api_key.startswith("your_key")),
        "anthropic_api_key_configured": bool(settings.anthropic_api_key and not settings.anthropic_api_key.startswith("your_key")),
        "embedding_model": settings.embedding_model,
        "auth_enabled": bool(settings.service_api_key and settings.service_api_key.strip()),
        "vector_store": {
            "type": "chromadb",
            "stats": vector_stats
        },
        "total_documents": len(document_service.list_documents())
    }

@router.get("/health")
async def health_check_root():
    """System health inspection and vector store diagnostic statistics."""
    return get_health_status()

@router.get("/api/v1/health")
async def health_check_v1():
    """Versioned health check endpoint for microservice health probes."""
    return get_health_status()

