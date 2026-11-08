# Xcel RAG GenAI Microservice — API Specification (v1)

**Service Version:** 2.0.0  
**Base URL:** `http://localhost:8000`  
**OpenAPI / Interactive Swagger UI:** `http://localhost:8000/docs`  
**ReDoc Documentation:** `http://localhost:8000/redoc`  

---

## 1. Overview & Architecture

The **Xcel RAG GenAI Microservice** is a decoupled, standalone FastAPI service engineered for ingestion, vectorization, hybrid retrieval, and grounded answer generation across **PDF documents** and **structured CSV datasets**.

External applications (such as a core enterprise backend) communicate with the GenAI microservice over HTTP REST. The core backend never connects directly to ChromaDB or the local embedding models.

```
┌─────────────────┐       HTTP REST       ┌───────────────────────┐
│  Core Backend   │ ────────────────────> │  Xcel RAG Service     │
│  (FastAPI/Node) │ <──────────────────── │  (Port 8000)          │
└─────────────────┘                       └───────────┬───────────┘
                                                      │
                                        ┌─────────────┴─────────────┐
                                        ▼                           ▼
                             ┌─────────────────────┐     ┌─────────────────────┐
                             │  ChromaDB Vectors   │     │ LLM Provider Engine │
                             │  (Local Persistent) │     │ OpenAI/Claude/Ollama│
                             └─────────────────────┘     └─────────────────────┘
```

---

## 2. Authentication & Security

Internal service-to-service authentication is controlled via the `SERVICE_API_KEY` environment variable.

* **Development Mode (Default)**: If `SERVICE_API_KEY` is empty, requests are accepted without authorization headers.
* **Production / Microservice Mode**: When `SERVICE_API_KEY` is configured in `.env`, callers must supply the key using either:
  1. Header: `X-API-Key: <your-service-api-key>`
  2. Header: `Authorization: Bearer <your-service-api-key>`

### Unauthorized Error Response (HTTP 401)
```json
{
  "detail": "Unauthorized: Invalid or missing API key. Provide via 'X-API-Key' or 'Authorization: Bearer <key>'."
}
```

---

## 3. Standard API Endpoints

### A. Health & Dependency Status

#### `GET /api/v1/health` (also accessible at `/health`)
Health check probe for orchestrators, load balancers, and backend clients. Does not require authentication.

**Response (HTTP 200 OK):**
```json
{
  "status": "healthy",
  "service": "xcel-rag",
  "version": "2.0.0",
  "llm_provider": "openai",
  "configured_model": "gpt-4o",
  "openai_model": "gpt-4o",
  "openai_api_key_configured": true,
  "anthropic_api_key_configured": false,
  "embedding_model": "all-MiniLM-L6-v2",
  "auth_enabled": false,
  "vector_store": {
    "type": "chromadb",
    "stats": {
      "pdf_documents": 12,
      "csv_records": 48,
      "csv_schemas": 2
    }
  },
  "total_documents": 2
}
```

---

### B. Document Ingestion

#### `POST /api/v1/documents/upload`
Uploads and indexes either a PDF document or a structured CSV dataset in a single unified endpoint.

* **Content-Type**: `multipart/form-data`
* **Form Field**: `file` (Binary file content, `.pdf` or `.csv`)
* **Maximum Allowed Size**: `50 MB` (configurable via `MAX_FILE_SIZE_MB`)

**Processing Pipeline:**
- **PDF**: PyMuPDF extracts text blocks, typography heading levels, and tables. Chunks are generated recursively with page preservation and indexed into `pdf_documents`.
- **CSV**: Pandas normalizes headers, generates a dataset schema summary indexed into `csv_schemas`, and formats row records indexed into `csv_records`. Raw DataFrame is cached for numerical filtering.

**Success Response (HTTP 200 OK):**
```json
{
  "document_id": "doc_e4c831fa2b",
  "file_name": "dbms_handbook.pdf",
  "file_type": "pdf",
  "processing_status": "completed",
  "page_count": 14,
  "row_count": null,
  "chunk_count": 28,
  "file_size": 245192,
  "upload_time": "2026-11-08T14:20:00.123456"
}
```

**CSV Success Response (HTTP 200 OK):**
```json
{
  "document_id": "csv_7b82f18391",
  "file_name": "students_semester6.csv",
  "file_type": "csv",
  "processing_status": "completed",
  "page_count": null,
  "row_count": 150,
  "chunk_count": 150,
  "file_size": 8920,
  "upload_time": "2026-11-08T14:21:00.654321"
}
```

**Validation Error Response (HTTP 400 Bad Request):**
```json
{
  "detail": "Unsupported file format '.docx'. Only .pdf and .csv files are supported."
}
```

---

### C. Document Registry & Deletion

#### `GET /api/v1/documents`
Lists all currently indexed documents along with chunk counts, row counts, and page numbers.

**Response (HTTP 200 OK):**
```json
{
  "documents": [
    {
      "document_id": "doc_e4c831fa2b",
      "file_name": "dbms_handbook.pdf",
      "file_type": "pdf",
      "file_size": 245192,
      "upload_time": "2026-11-08T14:20:00.123456",
      "processing_status": "completed",
      "chunk_count": 28,
      "page_count": 14,
      "row_count": null,
      "error_message": null,
      "schema_summary": null
    }
  ],
  "total_count": 1
}
```

#### `DELETE /api/v1/documents/{document_id}`
Safely purges a document, its raw files, cached DataFrames, and all associated vector embeddings across ChromaDB collections.

**Response (HTTP 200 OK):**
```json
{
  "status": "success",
  "message": "Document 'doc_e4c831fa2b' and all associated vector embeddings deleted successfully."
}
```

**Not Found Response (HTTP 404 Not Found):**
```json
{
  "detail": "Document with ID 'doc_e4c831fa2b' not found."
}
```

---

### D. Hybrid Natural Language Query

#### `POST /api/v1/query`
Executes hybrid retrieval across PDF text chunks, CSV rows, and CSV schemas, followed by grounded LLM answer synthesis.

**Request Payload:**
```json
{
  "query": "Which students scored above 90 in DBMS according to the database and dataset?",
  "top_k": 5,
  "scope": "hybrid",
  "conversation_id": "session_student_advisor_99"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | **Yes** | Natural language query. Supports relational syntax (`marks > 90`, `scored 95`). |
| `top_k` | integer | No | Maximum number of candidates to rerank and provide into LLM context (default: `8`). |
| `scope` | string | No | Search scope: `"hybrid"` (default), `"pdf"`, or `"csv"`. |
| `conversation_id` | string | No | Unique session key for multi-turn conversational context. |
| `filters` | object | No | Optional attribute filters (e.g., `{"file_name": "students.csv"}`). |

**Success Response (HTTP 200 OK):**
```json
{
  "request_id": "req_8a39e1f2b4c1",
  "answer": "Based on the records in students.csv, the following students scored above 90 in DBMS:\n- **Anu**: Scored 95 [File: students.csv, Row: 3]\n- **Sneha**: Scored 92 [File: students.csv, Row: 5]\n- **Kavya**: Scored 96 [File: students.csv, Row: 7]",
  "sources": [
    {
      "source_type": "csv",
      "file_name": "students.csv",
      "document_id": "csv_hybrid_data",
      "page": null,
      "row": 3,
      "chunk_id": "csv_hybrid_data_row_3",
      "snippet": "File: students.csv | Row 3\nStudent Id: 103\nName: Anu\nSemester: 6\nSubject: DBMS\nMarks: 95",
      "score": 0.98
    },
    {
      "source_type": "pdf",
      "file_name": "dbms.pdf",
      "document_id": "doc_hybrid_pdf",
      "page": 1,
      "row": null,
      "chunk_id": "doc_hybrid_pdf_chunk_1",
      "snippet": "Database Normalization Theory\nSection: Normalization\nNormalization decomposes tables to eliminate data redundancy...",
      "score": 0.8421
    }
  ],
  "retrieval_metadata": {
    "retrieval_count": 5,
    "scope": "hybrid",
    "query_type": "numerical",
    "pdf_candidates_count": 4,
    "csv_candidates_count": 4,
    "structured_candidates_count": 3
  },
  "execution_metrics": {
    "total_latency_ms": 118.4,
    "llm_provider": "openai",
    "llm_model": "gpt-4o",
    "tokens_usage": {
      "input_tokens": 420,
      "output_tokens": 85
    }
  },
  "conversation_id": "session_student_advisor_99"
}
```

---

### E. Developer Pipeline Diagnostics

#### `GET /api/v1/query/{request_id}/trace`
Retrieves execution diagnostics for authorized developers and performance tracing. Secrets and keys are automatically sanitized.

**Response (HTTP 200 OK):**
```json
{
  "request_id": "req_8a39e1f2b4c1",
  "query": "Which students scored above 90 in DBMS?",
  "scope": "hybrid",
  "created_at": "2026-11-08T14:22:15.123456",
  "total_latency_ms": 118.4,
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "tokens_usage": {
    "input_tokens": 420,
    "output_tokens": 85
  },
  "trace": {
    "query": "Which students scored above 90 in DBMS?",
    "analysis": {
      "query_type": "numerical",
      "has_numerical_filter": true,
      "detected_keywords": ["students", "marks", "above 90"]
    },
    "pdf_candidates_count": 4,
    "csv_candidates_count": 4,
    "structured_candidates_count": 3,
    "retrieved_candidates": [
      {
        "id": "csv_hybrid_data_row_3",
        "score": 0.98,
        "source_type": "csv",
        "document": "students.csv",
        "row": 3,
        "snippet": "File: students.csv | Row 3\nName: Anu | Marks: 95..."
      }
    ]
  }
}
```

---

## 4. Standard HTTP Error Codes

| Status Code | Reason | Example Detail |
|---|---|---|
| `400 Bad Request` | Invalid query string, unsupported file extension, empty file. | `{"detail": "Query cannot be empty."}` |
| `401 Unauthorized` | Missing or invalid `X-API-Key` / `Bearer` token. | `{"detail": "Unauthorized: Invalid or missing API key."}` |
| `404 Not Found` | Requested document or trace ID does not exist. | `{"detail": "Diagnostic trace for request_id '...' not found."}` |
| `422 Unprocessable` | Malformed multipart body or corrupted PDF/CSV file. | `{"detail": "Failed to process PDF: ..."}` |
| `500 Internal Error`| Unhandled runtime error. | `{"detail": "An internal server error occurred while processing the request."}` |

---

## 5. Backward Compatibility (Legacy Routes)

For existing frontend components and scripts, the following legacy routes remain fully functional:

| Legacy Route | Modern v1 Equivalent |
|---|---|
| `POST /upload/pdf` | `POST /api/v1/documents/upload` |
| `POST /upload/csv` | `POST /api/v1/documents/upload` |
| `POST /upload/sample/{name}` | Quick loader for sample datasets |
| `POST /query` | `POST /api/v1/query` |
| `GET /documents` | `GET /api/v1/documents` |
| `DELETE /documents/{id}` | `DELETE /api/v1/documents/{id}` |
| `GET /health` | `GET /api/v1/health` |
