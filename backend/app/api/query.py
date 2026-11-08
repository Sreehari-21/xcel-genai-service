from fastapi import APIRouter
from app.models.query import QueryRequest, QueryResponse
from app.api.v1.query import execute_query

router = APIRouter(prefix="", tags=["Query (Legacy)"])

@router.post("/query", response_model=QueryResponse)
async def handle_query(req: QueryRequest):
    """
    Unified query endpoint supporting hybrid multi-modal retrieval across PDF and CSV datasets.
    Delegates to the standardized query execution engine.
    """
    return await execute_query(req)
