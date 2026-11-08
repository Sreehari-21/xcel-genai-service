import io
from fastapi.testclient import TestClient
import pymupdf
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "vector_store" in data

def test_upload_pdf_endpoint():
    # Create sample PDF in memory
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "API Test PDF Content: Normalization theory explained in detail.")
    pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/upload/pdf",
        files={"file": ("api_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "api_test.pdf"
    assert data["file_type"] == "pdf"
    assert data["processing_status"] == "completed"
    assert data["chunk_count"] > 0

def test_upload_csv_endpoint():
    csv_content = b"student_id,name,score\n1,Alice,90\n2,Bob,80\n"
    response = client.post(
        "/upload/csv",
        files={"file": ("api_test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "api_test.csv"
    assert data["file_type"] == "csv"
    assert data["row_count"] == 2


def test_query_endpoint():
    response = client.post(
        "/query",
        json={"query": "What is normalization?", "top_k": 3}
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "retrieved_chunks" in data
    assert "metadata" in data

def test_documents_lifecycle():
    # 1. Get documents list
    res = client.get("/documents")
    assert res.status_code == 200
    docs = res.json()["documents"]
    assert len(docs) > 0

    target_id = docs[0]["document_id"]
    # 2. Delete document
    del_res = client.delete(f"/documents/{target_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # 3. Confirm deletion
    res_after = client.get("/documents")
    remaining_ids = [d["document_id"] for d in res_after.json()["documents"]]
    assert target_id not in remaining_ids
