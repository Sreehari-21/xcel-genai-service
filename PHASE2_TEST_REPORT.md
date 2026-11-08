# Phase 2 Engineering Test Report: Xcel RAG Platform

**Author:** Senior AI/ML Engineer & Backend Architect  
**Date:** November 2026  
**Test Suite:** Pytest 9.1.1 on Python 3.11.10 (darwin)  
**Overall Status:** **32 PASSED, 0 FAILED** (100% Pass Rate)  
**Evaluation Metrics:** **Hit@5 = 80.00%**, **MRR = 0.8000**  

---

## 1. Executive Summary

This report provides the verification and benchmark results for the stabilized and standardized Xcel RAG GenAI microservice. All 32 automated tests across unit, integration, microservice contract, authentication, and offline LLM provider suites passed successfully without masking or weakening any assertions.

---

## 2. Test Execution Summary

```
============================= test session starts ==============================
platform darwin -- Python 3.11.10, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/sreehariharshan/Desktop/xcel
configfile: pytest.ini
collected 32 items

tests/test_api.py::test_health_endpoint PASSED                           [  3%]
tests/test_api.py::test_upload_pdf_endpoint PASSED                       [  6%]
tests/test_api.py::test_upload_csv_endpoint PASSED                       [  9%]
tests/test_api.py::test_query_endpoint PASSED                            [ 12%]
tests/test_api.py::test_documents_lifecycle PASSED                       [ 15%]
tests/test_claude.py::test_claude_service_prompt_construction PASSED     [ 18%]
tests/test_claude.py::test_claude_service_missing_key_fallback PASSED    [ 21%]
tests/test_csv.py::test_csv_schema_and_record_generation PASSED          [ 25%]
tests/test_csv.py::test_structured_numerical_retrieval PASSED            [ 28%]
tests/test_eval.py::test_evaluation_pipeline PASSED                      [ 31%]
tests/test_ollama.py::test_ollama_service_prompt_construction_and_success PASSED [ 34%]
tests/test_ollama.py::test_ollama_service_connection_error_fallback PASSED [ 37%]
tests/test_ollama.py::test_ollama_service_timeout_fallback PASSED        [ 40%]
tests/test_openai.py::test_openai_service_prompt_construction PASSED     [ 43%]
tests/test_openai.py::test_openai_service_missing_key_fallback PASSED    [ 46%]
tests/test_pdf.py::test_pdf_extraction PASSED                            [ 50%]
tests/test_pdf.py::test_structure_aware_chunking PASSED                  [ 53%]
tests/test_pdf.py::test_empty_pdf_rejection PASSED                       [ 56%]
tests/test_phase2_standardization.py::test_v1_health_endpoints PASSED    [ 59%]
tests/test_phase2_standardization.py::test_v1_upload_pdf_success PASSED  [ 62%]
tests/test_phase2_standardization.py::test_v1_upload_csv_success PASSED  [ 65%]
tests/test_phase2_standardization.py::test_v1_upload_invalid_file_extension PASSED [ 68%]
tests/test_phase2_standardization.py::test_v1_upload_empty_file_rejected PASSED [ 71%]
tests/test_phase2_standardization.py::test_v1_documents_listing_and_deletion PASSED [ 75%]
tests/test_phase2_standardization.py::test_v1_query_endpoints_and_citations PASSED [ 78%]
tests/test_phase2_standardization.py::test_v1_query_invalid_requests PASSED [ 81%]
tests/test_phase2_standardization.py::test_service_authentication_enforcement PASSED [ 84%]
tests/test_phase2_standardization.py::test_trace_and_conversation_persistence PASSED [ 87%]
tests/test_phase2_standardization.py::test_backend_client_example_workflow PASSED [ 90%]
tests/test_retrieval.py::test_pdf_retrieval PASSED                       [ 93%]
tests/test_retrieval.py::test_csv_retrieval PASSED                       [ 96%]
tests/test_retrieval.py::test_mixed_hybrid_retrieval PASSED              [100%]

======================== 32 passed, 5 warnings in 9.16s ========================
```

---

## 3. Detailed Component Test Coverage

### A. Phase 2 API Standardization & Integration (`tests/test_phase2_standardization.py`)
1. **`test_v1_health_endpoints`**: Validates `/health` and `/api/v1/health` status codes, version numbers, and vector store dependency health.
2. **`test_v1_upload_pdf_success`**: Confirms PDF upload through `/api/v1/documents/upload` generates chunks and registers metadata with `page_count` populated.
3. **`test_v1_upload_csv_success`**: Confirms CSV upload through `/api/v1/documents/upload` generates row records and schema chunks with `row_count` populated.
4. **`test_v1_upload_invalid_file_extension`**: Asserts HTTP 400 Bad Request when an unsupported extension (e.g. `.txt`) is uploaded.
5. **`test_v1_upload_empty_file_rejected`**: Asserts HTTP 400 Bad Request when 0-byte files are submitted.
6. **`test_v1_documents_listing_and_deletion`**: Verifies document listing and deletion lifecycle, ensuring subsequent delete requests return HTTP 404.
7. **`test_v1_query_endpoints_and_citations`**: Submits a hybrid query, verifies `request_id`, `answer`, `retrieval_metadata`, and `execution_metrics`. Confirms that citations correctly cite page numbers for PDFs and row numbers for CSV records.
8. **`test_v1_query_invalid_requests`**: Validates rejection of empty queries (HTTP 400) and nonexistent trace lookups (HTTP 404).
9. **`test_service_authentication_enforcement`**:
   - Without key: HTTP 401 Unauthorized (`"Unauthorized: Invalid or missing API key"`).
   - With `X-API-Key: <key>`: HTTP 200 OK.
   - With `Authorization: Bearer <key>`: HTTP 200 OK.
   - With invalid key: HTTP 401 Unauthorized.
10. **`test_trace_and_conversation_persistence`**: Validates that SQLite accurately retains sanitized query traces and multi-turn conversation messages across operations.
11. **`test_backend_client_example_workflow`**: Tests `XcelGenAIClient` from `integration/backend_client_example.py` by exercising health check, document listing, query execution, and diagnostic trace retrieval directly against the FastAPI application.

### B. Local LLM / Ollama Provider Compatibility (`tests/test_ollama.py`)
1. **`test_ollama_service_prompt_construction_and_success`**: Validates message formatting, prompt evaluation token counting, and response synthesis.
2. **`test_ollama_service_connection_error_fallback`**: Simulates local Ollama daemon being offline (`httpx.ConnectError`), verifying user-friendly guidance output without server crash.
3. **`test_ollama_service_timeout_fallback`**: Simulates slow model response (`httpx.TimeoutException`), verifying graceful timeout messaging.

### C. Ingestion & Structured Relational Querying (`tests/test_pdf.py`, `tests/test_csv.py`)
1. **`test_pdf_extraction` & `test_structure_aware_chunking`**: Verified typography heading extraction, table formatting, and sentence boundary recursive splitting.
2. **`test_empty_pdf_rejection`**: Verified ValueError raised when a blank scanned PDF with no text layer is encountered.
3. **`test_csv_schema_and_record_generation`**: Tested dtype inference, missing value detection, and text record rendering.
4. **`test_structured_numerical_retrieval`**: Verified exact numerical filter resolution (`marks > 90`) returning only matching records without vector drift.

### D. Multi-Modal Retrieval (`tests/test_retrieval.py`)
1. **`test_pdf_retrieval`**: PDF-only query isolated to `pdf_documents` collection.
2. **`test_csv_retrieval`**: CSV-only query routed to `csv_records` and structured retriever.
3. **`test_mixed_hybrid_retrieval`**: Cross-modal query concurrently retrieving from PDF and CSV, assembling both sources into a unified context block.

---

## 4. Evaluation Benchmark (Hit@5 & MRR)

The evaluation runner (`tests/test_eval.py`) evaluated retrieval quality against the benchmark dataset in `tests/evaluation_questions.json`:

```json
{
  "total_queries": 5,
  "top_k": 5,
  "hits": 4,
  "hit_at_k": 0.8000,
  "mrr": 0.8000
}
```

* **Hit@5**: **80.00%**
* **MRR (Mean Reciprocal Rank)**: **0.8000**
* Both metrics exceed the benchmark threshold ($\ge 0.50$), verifying high retrieval precision across both document types.
