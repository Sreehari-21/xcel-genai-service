import time
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Security
from app.core.config import settings
from app.core.logging import log_event
from app.core.auth import verify_api_key
from app.models.query import QueryRequest, QueryResponse, QueryTraceResponse
from app.services.retrieval_service import retrieval_service
from app.services.llm_factory import get_llm_service
from app.services.trace_service import trace_service

router = APIRouter(prefix="/api/v1/query", tags=["Query (v1)"])

@router.post("", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
async def execute_query(req: QueryRequest):
    """
    Standardized GenAI Query endpoint supporting multi-modal hybrid retrieval
    across PDF documents and structured CSV datasets.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    start_time = time.time()
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    log_event("QUERY", f"[{request_id}] Received query: '{req.query}' (scope={req.scope})")

    # Harmonize scope with internal filters
    filters = dict(req.filters or {})
    scope = (req.scope or "hybrid").lower().strip()
    if scope == "pdf":
        filters["source_type"] = "pdf"
    elif scope in ["csv", "csv_records"]:
        filters["source_type"] = "csv"

    try:
        # Step 1: Hybrid Retrieval across collections & Pandas engine
        retrieved_chunks, formatted_context, citations, pipeline_trace = retrieval_service.retrieve(
            query=req.query,
            top_k=req.top_k,
            filters=filters
        )

        # Step 2: Active LLM synthesis
        active_llm = get_llm_service()
        llm_result = active_llm.generate_answer(
            query=req.query,
            context=formatted_context,
            conversation_id=req.conversation_id
        )

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        # Structure diagnostics & metrics
        llm_model = llm_result.get("model_used", "unknown")
        token_usage = llm_result.get("usage", {"input_tokens": 0, "output_tokens": 0})
        query_type = pipeline_trace.get("analysis", {}).get("query_type", "general")

        pipeline_trace["request_id"] = request_id
        pipeline_trace["llm_provider"] = settings.llm_provider
        pipeline_trace["llm_model"] = llm_model
        pipeline_trace["tokens_usage"] = token_usage
        pipeline_trace["total_latency_ms"] = elapsed_ms

        retrieval_meta = {
            "retrieval_count": len(retrieved_chunks),
            "scope": scope,
            "query_type": query_type,
            "pdf_candidates_count": pipeline_trace.get("pdf_candidates_count", 0),
            "csv_candidates_count": pipeline_trace.get("csv_candidates_count", 0),
            "structured_candidates_count": pipeline_trace.get("structured_candidates_count", 0),
        }

        execution_metrics = {
            "total_latency_ms": elapsed_ms,
            "llm_provider": settings.llm_provider,
            "llm_model": llm_model,
            "tokens_usage": token_usage,
        }

        # Step 3: Persist trace asynchronously / synchronously to SQLite
        trace_service.save_trace(
            request_id=request_id,
            query=req.query,
            scope=scope,
            trace_dict=pipeline_trace,
            latency_ms=elapsed_ms,
            llm_provider=settings.llm_provider,
            llm_model=llm_model,
            input_tokens=token_usage.get("input_tokens", 0),
            output_tokens=token_usage.get("output_tokens", 0)
        )

        return QueryResponse(
            request_id=request_id,
            answer=llm_result["answer"],
            sources=citations,
            retrieval_metadata=retrieval_meta,
            execution_metrics=execution_metrics,
            conversation_id=req.conversation_id,
            retrieved_chunks=retrieved_chunks,
            metadata={
                "latency_ms": elapsed_ms,
                "retrieval_count": len(retrieved_chunks),
                "model": llm_model,
                "query_type": query_type
            },
            pipeline_trace=pipeline_trace
        )

    except Exception as e:
        log_event("ERROR", f"[{request_id}] Query processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")

@router.get("/{request_id}/trace", response_model=QueryTraceResponse, dependencies=[Depends(verify_api_key)])
async def get_query_trace(request_id: str):
    """
    Retrieve diagnostic execution trace and candidate retrieval details for authorized developers.
    Sensitive tokens and internal secrets are strictly sanitized.
    """
    trace_data = trace_service.get_trace(request_id)
    if not trace_data:
        raise HTTPException(
            status_code=404,
            detail=f"Diagnostic trace for request_id '{request_id}' not found."
        )

    return QueryTraceResponse(
        request_id=trace_data["request_id"],
        query=trace_data["query"],
        scope=trace_data["scope"],
        created_at=trace_data["created_at"],
        total_latency_ms=trace_data["total_latency_ms"],
        llm_provider=trace_data["llm_provider"],
        llm_model=trace_data["llm_model"],
        tokens_usage=trace_data["tokens_usage"],
        trace=trace_data["trace"]
    )
