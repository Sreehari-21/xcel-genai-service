# Xcel RAG — Multi-Modal GenAI Microservice (PDF + CSV)

A production-ready, modular **Retrieval-Augmented Generation (RAG) Microservice** engineered to ingest, parse, chunk, index, retrieve, and reason over both **unstructured PDF documents** and **structured CSV datasets** with hybrid retrieval, lexical re-ranking, and multi-provider LLM generation (**OpenAI GPT-4o**, **Claude 3.5 Sonnet**, and **Local Ollama**).

---

## 1. System Architecture

```text
                           ┌───────────────────────────────────────────────┐
                           │          External Backend / Web Client        │
                           └───────────────────────┬───────────────────────┘
                                                   │ HTTP REST (/api/v1)
                                                   ▼
                           ┌───────────────────────────────────────────────┐
                           │       Xcel RAG FastAPI Microservice (8000)    │
                           │   Service Auth (X-API-Key / Bearer Token)     │
                           └───────────────────────┬───────────────────────┘
                                                   │
                         ┌─────────────────────────┴─────────────────────────┐
                         ▼                                                   ▼
              ┌─────────────────────┐                             ┌─────────────────────┐
              │ Document Ingestion  │                             │   Query Pipeline    │
              │  (PDF / CSV Unified)│                             │  & Hybrid Retrieval │
              └──────────┬──────────┘                             └──────────┬──────────┘
                         │                                                   │
        ┌────────────────┴────────────────┐                 ┌────────────────┴────────────────┐
        ▼                                 ▼                 ▼                                 ▼
┌──────────────┐                  ┌──────────────┐   ┌──────────────┐                  ┌──────────────┐
│ PyMuPDF PDF  │                  │  Pandas CSV  │   │  ChromaDB    │                  │ Structured   │
│ Structure-   │                  │  Schema &    │   │ (3 Vector    │                  │ Pandas       │
│ Aware Parser │                  │  Row Chunks  │   │ Collections) │                  │ Filter Engine│
└───────┬──────┘                  └───────┬──────┘   └──────┬───────┘                  └──────┬───────┘
        │                                 │                 │                                 │
        └────────────────┬────────────────┘                 └────────────────┬────────────────┘
                         ▼                                                   ▼
              ┌─────────────────────┐                             ┌─────────────────────┐
              │   all-MiniLM-L6-v2  │                             │  Modular Reranker   │
              │ Dense Embeddings    │                             │ (Dense+Lexical+Row) │
              └─────────────────────┘                             └──────────┬──────────┘
                                                                             │
                                                                             ▼
                                                                  ┌─────────────────────┐
                                                                  │ LLM Provider Engine │
                                                                  │ (OpenAI / Claude /  │
                                                                  │   Local Ollama)     │
                                                                  └──────────┬──────────┘
                                                                             │
                                                                             ▼
                                                                  ┌─────────────────────┐
                                                                  │ Grounded Answer +   │
                                                                  │ Exact Page & Row    │
                                                                  │ Source Citations    │
                                                                  └─────────────────────┘
```

---

## 2. Key Capabilities

- **Unified Document Ingestion (`POST /api/v1/documents/upload`)**: Single endpoint supporting both PDF documents and structured CSV datasets with automatic file validation, heading extraction, table conversion, and row serialization.
- **Hybrid Numerical / Relational Filtering**: Directly parses operators (`>`, `<`, `==`, `above 90`, `scored 95`) and queries cached DataFrames via Pandas, eliminating vector drift on strict quantitative queries.
- **Multi-Provider LLM Abstraction**: Easily switch between **OpenAI (GPT-4o)**, **Anthropic Claude (Sonnet 3.5)**, and **Local Ollama (Llama 3.2)** via environment configuration.
- **Persistent Trace & Conversation Store**: Stores sanitized query execution traces in SQLite accessible via `GET /api/v1/query/{request_id}/trace` for developer diagnostics and observability.
- **Internal Service Authentication**: Configurable `SERVICE_API_KEY` supporting `X-API-Key` or `Authorization: Bearer <key>` headers to protect service-to-service communication.
- **Backend Integration Ready**: Includes a reference Python client (`integration/backend_client_example.py`) demonstrating health checks, uploads, hybrid queries, and trace inspection for other backend teams.
- **Interactive Web Dashboard**: React 18 + Vite dark-mode glassmorphic interface with drag-and-drop ingestion, source citation badges, and developer pipeline modal.

---

## 3. Directory Structure

```text
xcel/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI microservice entrypoint & CORS
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── health.py               # /api/v1/health & /health
│   │   │   │   ├── documents.py            # /api/v1/documents, upload, and delete
│   │   │   │   └── query.py                # /api/v1/query & /api/v1/query/{id}/trace
│   │   │   ├── upload.py                   # Legacy /upload/* routes (backwards compatible)
│   │   │   ├── query.py                    # Legacy /query route
│   │   │   └── documents.py                # Legacy /documents routes
│   │   ├── services/
│   │   │   ├── ingestion_service.py        # Unified PDF/CSV ingestion pipeline
│   │   │   ├── pdf_service.py              # PyMuPDF extractor (headings, tables, text)
│   │   │   ├── chunking_service.py         # Structure-aware recursive chunker
│   │   │   ├── csv_service.py              # Schema detection & row serializer
│   │   │   ├── structured_data_retriever.py# Pandas numerical & condition engine
│   │   │   ├── embedding_service.py        # Sentence-Transformers (all-MiniLM-L6-v2)
│   │   │   ├── vector_store.py             # ChromaDB multi-collection manager
│   │   │   ├── retrieval_service.py        # Multi-stage query analyzer & retriever
│   │   │   ├── reranking_service.py        # Lexical & semantic re-ranking engine
│   │   │   ├── llm_base.py                 # Abstract Base Class & common prompts
│   │   │   ├── llm_factory.py              # Factory for active LLM provider
│   │   │   ├── openai_service.py           # OpenAI API client (GPT-4o)
│   │   │   ├── claude_service.py           # Anthropic Claude SDK client
│   │   │   ├── ollama_service.py           # Local Ollama REST client
│   │   │   ├── trace_service.py            # SQLite persistent trace & history store
│   │   │   └── document_service.py         # Document registry and storage lifecycle
│   │   ├── models/
│   │   │   ├── document.py                 # Document metadata & upload models
│   │   │   ├── chunk.py                    # Chunk and ChunkMetadata models
│   │   │   └── query.py                    # Standardized QueryRequest & Response
│   │   └── core/
│   │       ├── auth.py                     # Service API Key verification
│   │       ├── config.py                   # Pydantic v2 application settings
│   │       └── logging.py                  # Structured stage-based logger
│   └── requirements.txt                    # Python dependencies
│
├── frontend/                               # React 18 + Vite Web Dashboard
│   ├── src/
│   │   ├── components/                     # Sidebar, ChatArea, SourceCard, Visualizer
│   │   ├── services/api.js                 # API client wrapper with trace fetch
│   │   ├── App.jsx                         # Main dashboard orchestrator
│   │   └── index.css                       # Dark-mode styling
│   └── vite.config.js                      # Vite proxy to backend
│
├── integration/
│   └── backend_client_example.py           # Reference client for other backend teams
│
├── data/
│   ├── uploads/                            # Stored uploaded files
│   ├── chroma/                             # Persistent ChromaDB vector collections
│   ├── processed/                          # SQLite DB, DataFrames, and registry JSON
│   └── samples/                            # Sample dbms.pdf & students.csv datasets
│
├── tests/                                  # 32 automated unit, integration & eval tests
│   ├── test_phase2_standardization.py      # Standardized v1 endpoints, auth, persistence
│   ├── test_ollama.py                      # Local Ollama provider tests
│   ├── test_pdf.py                         # PDF parsing & chunking tests
│   ├── test_csv.py                         # CSV schema detection & filtering tests
│   ├── test_retrieval.py                   # Hybrid multi-source retrieval tests
│   ├── test_openai.py                      # OpenAI client tests
│   ├── test_claude.py                      # Claude client tests
│   ├── test_api.py                         # Legacy API tests
│   ├── test_eval.py                        # Hit@K and MRR evaluation runner
│   └── evaluation_questions.json           # Benchmark evaluation dataset
│
├── API_DOCUMENTATION.md                    # Complete REST API specification
├── PHASE2_AUDIT.md                         # Architecture audit report
├── PHASE2_TEST_REPORT.md                   # Verification and test run report
├── .env.example                            # Configuration environment template
├── .env                                    # Active environment configuration
└── README.md
```

---

## 4. Setup & Installation

### Step 1: Set Up Python Virtual Environment

```bash
cd xcel
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Step 2: Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

The template is pre-configured for local **Ollama** using `qwen2.5:7b` (no cloud API keys required).

#### Option A: Ollama (Local / Offline - Recommended Default)
1. **Install Ollama:**
   - **macOS:** `brew install ollama`
   - **Linux:** `curl -fsSL https://ollama.com/install.sh | sh`
   - **Windows:** Download from [https://ollama.com/download](https://ollama.com/download)
2. **Start Daemon & Pull Model:**
   ```bash
   ollama serve
   ollama pull qwen2.5:7b
   ```
3. **Environment Settings (`.env`):**
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

#### Option B: OpenAI (Cloud Alternative)
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-your-openai-key-here
OPENAI_MODEL=gpt-4o
```

#### Option C: Anthropic Claude (Cloud Alternative)
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key-here
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

#### Microservice Authentication (Optional)
To require backend authentication, set a key:
```env
SERVICE_API_KEY=your-secure-internal-team-key
```

### Step 3: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

---

## 5. Running the Application

### Start the GenAI Microservice (Backend)

```bash
source .venv/bin/activate
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

* Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
* Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Start the Frontend Web UI

```bash
cd frontend
npm run dev
```

* Dashboard UI: [http://localhost:5173](http://localhost:5173)

---

## 6. How Backend Teams Can Integrate with Xcel RAG

A complete, standalone Python client is provided in `integration/backend_client_example.py`.

```python
from integration.backend_client_example import XcelGenAIClient

# Initialize client
client = XcelGenAIClient(
    base_url="http://127.0.0.1:8000",
    api_key="your-secure-internal-team-key"  # Optional
)

# 1. Health Probe
health = client.check_health()
print(f"Status: {health['status']}, Documents: {health['total_documents']}")

# 2. Upload Document
upload_res = client.upload_document("./data/samples/students.csv")
print(f"Uploaded {upload_res['file_name']}, ID: {upload_res['document_id']}")

# 3. Query Knowledge Core
response = client.query(
    query="Which students scored above 90 in DBMS?",
    top_k=5,
    scope="hybrid"
)
print("Answer:", response["answer"])
print("Citations:", response["sources"])
print("Request ID:", response["request_id"])

# 4. Fetch Execution Trace
trace = client.get_query_trace(response["request_id"])
print("Latency:", trace["total_latency_ms"], "ms")
```

---

## 7. Running the Test Suite

Execute all 32 automated tests:

```bash
source .venv/bin/activate
pytest tests/ -v
```

Run retrieval evaluation benchmark (Hit@5 and MRR):

```bash
pytest tests/test_eval.py -s
```
*(Current results: **Hit@5 = 80.00%**, **MRR = 0.8000**)*

---

## 8. Summary of API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service status, active LLM, vector store stats |
| `POST` | `/api/v1/documents/upload` | Standardized multipart upload for PDF and CSV |
| `GET` | `/api/v1/documents` | List all indexed documents with page/row metadata |
| `DELETE`| `/api/v1/documents/{document_id}` | Purge document and remove vector embeddings |
| `POST` | `/api/v1/query` | Standardized multi-modal hybrid retrieval & LLM generation |
| `GET` | `/api/v1/query/{request_id}/trace` | Diagnostic candidate scores, prompt context, and token usage |
| `POST` | `/upload/pdf`, `/upload/csv` | Legacy upload endpoints (backwards compatible) |
| `POST` | `/query` | Legacy query endpoint (backwards compatible) |
