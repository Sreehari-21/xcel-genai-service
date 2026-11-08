import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException

from app.core.config import settings
from app.core.logging import log_event
from app.api.upload import router as legacy_upload_router
from app.api.query import router as legacy_query_router
from app.api.documents import router as legacy_documents_router

from app.api.v1.documents import router as v1_documents_router
from app.api.v1.query import router as v1_query_router
from app.api.v1.health import router as v1_health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("GENERAL", f"Xcel RAG GenAI Microservice v{settings.service_version} starting up")
    log_event("GENERAL", f"Configured Embedding Model: {settings.embedding_model}")
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        active_model = f"Ollama ({settings.ollama_model}) at {settings.ollama_base_url}"
    elif provider in ["claude", "anthropic"]:
        active_model = f"Claude ({settings.claude_model})"
    else:
        active_model = f"OpenAI ({settings.openai_model})"
    log_event("GENERAL", f"Active LLM: {active_model}")
    log_event("GENERAL", f"Vector Store directory: {settings.chroma_dir}")
    log_event("GENERAL", f"Service Auth Enabled: {bool(settings.service_api_key)}")
    yield

app = FastAPI(
    title="Xcel RAG Service — Multi-Modal Knowledge Engine (PDF + CSV)",
    description="Production-ready GenAI microservice supporting PDF and CSV ingestion, structure-aware chunking, hybrid semantic & relational retrieval, and multi-provider LLM generation (OpenAI, Claude, Ollama).",
    version=settings.service_version,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    log_event("WARN", f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log_event("WARN", f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed", "errors": exc.errors()}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_event("ERROR", f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred while processing the request."}
    )

# Include v1 Standardized Endpoints
app.include_router(v1_health_router)
app.include_router(v1_documents_router)
app.include_router(v1_query_router)

# Include Legacy Endpoints for Frontend & Backwards Compatibility
app.include_router(legacy_upload_router)
app.include_router(legacy_query_router)
app.include_router(legacy_documents_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
