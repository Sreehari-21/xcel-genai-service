import io
import os
import pytest
from fastapi.testclient import TestClient
import pymupdf

from app.main import app
from app.core.config import settings
from app.services.trace_service import trace_service
from app.services.document_service import document_service
from integration.backend_client_example import XcelGenAIClient

client = TestClient(app)

def test_v1_health_endpoints():
    # Root health
    res_root = client.get("/health")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["status"] == "healthy"
    assert data_root["service"] == "xcel-rag"
    assert "version" in data_root

    # Versioned health
    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200
    data_v1 = res_v1.json()
    assert data_v1["status"] == "healthy"
    assert data_v1["version"] == data_root["version"]

def test_v1_upload_pdf_success():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Phase 2 Standardization PDF: Testing unified document upload pipeline.")
    pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("phase2_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "phase2_test.pdf"
    assert data["file_type"] == "pdf"
    assert data["processing_status"] == "completed"
    assert data["chunk_count"] > 0
    assert data["page_count"] == 1
    assert "document_id" in data
    # Cleanup to preserve test isolation
    client.delete(f"/api/v1/documents/{data['document_id']}")

def test_v1_upload_csv_success():
    csv_bytes = b"student_id,name,score,subject\n201,Kavya,96,DBMS\n202,Arun,82,DBMS\n"
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("phase2_students.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "phase2_students.csv"
    assert data["file_type"] == "csv"
    assert data["row_count"] == 2
    assert data["chunk_count"] == 2
    assert "document_id" in data
    # Cleanup to preserve test isolation
    client.delete(f"/api/v1/documents/{data['document_id']}")

def test_v1_upload_invalid_file_extension():
    txt_content = b"Some plain text file content."
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("unsupported.txt", io.BytesIO(txt_content), "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

def test_v1_upload_empty_file_rejected():
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_v1_documents_listing_and_deletion():
    # 1. Listing
    res = client.get("/api/v1/documents")
    assert res.status_code == 200
    docs = res.json()["documents"]
    assert len(docs) > 0
    doc_id = docs[0]["document_id"]

    # 2. Deletion
    del_res = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # 3. Not found on repeat delete
    del_res_repeat = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res_repeat.status_code == 404

def test_v1_query_endpoints_and_citations():
    # Execute query
    req_payload = {
        "query": "Which student scored above 90 in DBMS?",
        "top_k": 5,
        "scope": "hybrid",
        "conversation_id": "test_conv_p2"
    }
    response = client.post("/api/v1/query", json=req_payload)
    assert response.status_code == 200
    data = response.json()

    assert "request_id" in data
    assert data["request_id"].startswith("req_")
    assert "answer" in data
    assert "sources" in data
    assert "retrieval_metadata" in data
    assert "execution_metrics" in data
    assert data["conversation_id"] == "test_conv_p2"

    # Verify citation structure
    for src in data["sources"]:
        assert "source_type" in src
        assert "file_name" in src
        if src["source_type"] == "pdf":
            assert src.get("page") is not None
        elif src["source_type"] == "csv":
            assert src.get("row") is not None
        elif src["source_type"] == "csv_schema":
            assert src.get("file_name") is not None

    # Test trace diagnostics endpoint
    request_id = data["request_id"]
    trace_res = client.get(f"/api/v1/query/{request_id}/trace")
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert trace_data["request_id"] == request_id
    assert "trace" in trace_data
    assert "total_latency_ms" in trace_data

def test_v1_query_invalid_requests():
    # Empty query
    res_empty = client.post("/api/v1/query", json={"query": "   ", "top_k": 5})
    assert res_empty.status_code == 400
    assert "cannot be empty" in res_empty.json()["detail"].lower()

    # Non-existent trace
    res_trace_404 = client.get("/api/v1/query/req_non_existent/trace")
    assert res_trace_404.status_code == 404

def test_service_authentication_enforcement(monkeypatch):
    test_key = "secure-internal-team-key-12345"
    monkeypatch.setattr(settings, "service_api_key", test_key)

    # 1. Unauthenticated request should fail with 401
    res_unauth = client.get("/api/v1/documents")
    assert res_unauth.status_code == 401
    assert "Unauthorized" in res_unauth.json()["detail"]

    # 2. Authenticated via X-API-Key should succeed
    res_auth_header = client.get(
        "/api/v1/documents",
        headers={"X-API-Key": test_key}
    )
    assert res_auth_header.status_code == 200

    # 3. Authenticated via Bearer token should succeed
    res_auth_bearer = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {test_key}"}
    )
    assert res_auth_bearer.status_code == 200

    # 4. Invalid key should fail with 401
    res_invalid_key = client.get(
        "/api/v1/documents",
        headers={"X-API-Key": "wrong-key"}
    )
    assert res_invalid_key.status_code == 401

def test_trace_and_conversation_persistence():
    test_req_id = "req_persistence_test_999"
    trace_service.save_trace(
        request_id=test_req_id,
        query="Test persistence query?",
        scope="hybrid",
        trace_dict={"analysis": {"query_type": "hybrid_test"}},
        latency_ms=120.5,
        llm_provider="openai",
        llm_model="gpt-4o",
        input_tokens=100,
        output_tokens=50
    )

    loaded_trace = trace_service.get_trace(test_req_id)
    assert loaded_trace is not None
    assert loaded_trace["request_id"] == test_req_id
    assert loaded_trace["total_latency_ms"] == 120.5
    assert loaded_trace["tokens_usage"]["input_tokens"] == 100

    # Test conversation turn persistence
    conv_id = "conv_persist_test"
    trace_service.save_conversation_turn(conv_id, "user", "Hello RAG!")
    trace_service.save_conversation_turn(conv_id, "assistant", "Hello! How can I assist you?")

    history = trace_service.get_conversation_history(conv_id)
    assert len(history) >= 2
    assert history[-2]["role"] == "user"
    assert history[-2]["content"] == "Hello RAG!"
    assert history[-1]["role"] == "assistant"

def test_backend_client_example_workflow():
    # Pass existing FastAPI TestClient directly to XcelGenAIClient
    genai_client = XcelGenAIClient(base_url="http://testserver", http_client=client)

    # 1. Health check via client
    health = genai_client.check_health()
    assert health["status"] == "healthy"
    assert health["service"] == "xcel-rag"

    # 2. List documents via client
    docs = genai_client.list_documents()
    assert isinstance(docs, list)

    # 3. Query via client
    query_res = genai_client.query("What is database normalization?", top_k=3, scope="pdf")
    assert "request_id" in query_res
    assert "answer" in query_res
    assert "sources" in query_res

    # 4. Fetch trace via client
    trace_res = genai_client.get_query_trace(query_res["request_id"])
    assert trace_res["request_id"] == query_res["request_id"]
    assert "trace" in trace_res
