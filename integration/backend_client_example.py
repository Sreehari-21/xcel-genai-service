"""
Xcel RAG GenAI Microservice — Backend Integration Client Example
================================================================
This module illustrates how another backend service (e.g. FastAPI, Django, Flask, or Node)
can integrate with the independent Xcel RAG GenAI microservice via standard HTTP REST calls.

Architecture:
Frontend --> Main Backend App --> XcelGenAIClient --> Xcel RAG Microservice (:8000)
"""

import os
import sys
import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import httpx

class GenAIClientError(Exception):
    """Base exception for GenAI client operations."""
    pass

class GenAIAuthenticationError(GenAIClientError):
    """Raised when authentication fails (HTTP 401)."""
    pass

class GenAITimeoutError(GenAIClientError):
    """Raised when an API request exceeds the configured timeout."""
    pass

class GenAIAPIError(GenAIClientError):
    """Raised when the GenAI service returns a 4xx or 5xx HTTP error."""
    def __init__(self, status_code: int, message: str, details: Optional[Any] = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.details = details

class XcelGenAIClient:
    """
    HTTP Client for consuming the Xcel RAG GenAI Microservice.
    Provides methods for health checking, document management, hybrid queries,
    and developer diagnostics.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: Optional[str] = None,
        timeout: float = 45.0,
        http_client: Optional[httpx.Client] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._http_client = http_client

    @contextmanager
    def _client_session(self, timeout: float):
        if self._http_client:
            yield self._http_client
        else:
            with httpx.Client(timeout=timeout) as client:
                yield client

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "MainBackendApp/1.0"
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def check_health(self) -> Dict[str, Any]:
        """
        Check liveness and inspect vector store and LLM provider statistics.
        GET /api/v1/health
        """
        url = f"{self.base_url}/api/v1/health"
        try:
            with self._client_session(timeout=10.0) as client:
                res = client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    return res.json()
                raise GenAIAPIError(res.status_code, res.text)
        except httpx.ConnectError as e:
            raise GenAIClientError(f"Cannot connect to GenAI service at {self.base_url}: {e}")
        except httpx.TimeoutException:
            raise GenAITimeoutError(f"Health check timed out after 10.0 seconds")

    def upload_document(self, file_path: str) -> Dict[str, Any]:
        """
        Upload and index a PDF or CSV document.
        POST /api/v1/documents/upload
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Local file not found: {file_path}")

        file_name = os.path.basename(file_path)
        ext = file_name.split(".")[-1].lower()
        mime_type = "application/pdf" if ext == "pdf" else "text/csv"

        url = f"{self.base_url}/api/v1/documents/upload"
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_name, f, mime_type)}
                with self._client_session(timeout=self.timeout) as client:
                    res = client.post(url, files=files, headers=self._get_headers())

                    if res.status_code == 200:
                        return res.json()
                    elif res.status_code == 401:
                        raise GenAIAuthenticationError("Authentication failed: invalid or missing API key.")
                    else:
                        error_detail = res.json().get("detail", res.text) if res.headers.get("content-type") == "application/json" else res.text
                        raise GenAIAPIError(res.status_code, error_detail)

        except httpx.TimeoutException:
            raise GenAITimeoutError(f"Document upload timed out after {self.timeout}s")
        except httpx.ConnectError as e:
            raise GenAIClientError(f"Connection failed: {e}")

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all indexed documents with page/row and chunk counts.
        GET /api/v1/documents
        """
        url = f"{self.base_url}/api/v1/documents"
        try:
            with self._client_session(timeout=15.0) as client:
                res = client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    return res.json().get("documents", [])
                elif res.status_code == 401:
                    raise GenAIAuthenticationError("Authentication failed.")
                raise GenAIAPIError(res.status_code, res.text)
        except httpx.TimeoutException:
            raise GenAITimeoutError("Listing documents timed out")

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and purge all associated vector embeddings.
        DELETE /api/v1/documents/{document_id}
        """
        url = f"{self.base_url}/api/v1/documents/{document_id}"
        try:
            with self._client_session(timeout=15.0) as client:
                res = client.delete(url, headers=self._get_headers())
                if res.status_code == 200:
                    return True
                elif res.status_code == 404:
                    return False
                elif res.status_code == 401:
                    raise GenAIAuthenticationError("Authentication failed.")
                raise GenAIAPIError(res.status_code, res.text)
        except httpx.TimeoutException:
            raise GenAITimeoutError("Delete operation timed out")

    def query(
        self,
        query: str,
        top_k: int = 5,
        scope: str = "hybrid",
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit a natural language question across indexed PDF & CSV datasets.
        POST /api/v1/query
        """
        url = f"{self.base_url}/api/v1/query"
        payload = {
            "query": query,
            "top_k": top_k,
            "scope": scope,
            "conversation_id": conversation_id
        }

        try:
            with self._client_session(timeout=self.timeout) as client:
                res = client.post(url, json=payload, headers=self._get_headers())

                if res.status_code == 200:
                    return res.json()
                elif res.status_code == 401:
                    raise GenAIAuthenticationError("Authentication failed.")
                else:
                    err_msg = res.json().get("detail", res.text) if res.headers.get("content-type") == "application/json" else res.text
                    raise GenAIAPIError(res.status_code, err_msg)

        except httpx.TimeoutException:
            raise GenAITimeoutError(f"Query execution timed out after {self.timeout}s")
        except httpx.ConnectError as e:
            raise GenAIClientError(f"Connection failed: {e}")

    def get_query_trace(self, request_id: str) -> Dict[str, Any]:
        """
        Retrieve developer pipeline diagnostics for a given request_id.
        GET /api/v1/query/{request_id}/trace
        """
        url = f"{self.base_url}/api/v1/query/{request_id}/trace"
        try:
            with self._client_session(timeout=15.0) as client:
                res = client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    return res.json()
                elif res.status_code == 404:
                    raise GenAIAPIError(404, f"Trace for request {request_id} not found.")
                elif res.status_code == 401:
                    raise GenAIAuthenticationError("Authentication failed.")
                raise GenAIAPIError(res.status_code, res.text)
        except httpx.TimeoutException:
            raise GenAITimeoutError("Trace retrieval timed out")


def demonstrate_integration():
    """Example workflow demonstrating how another backend team interacts with Xcel RAG."""
    client = XcelGenAIClient(base_url="http://127.0.0.1:8000", api_key=os.getenv("SERVICE_API_KEY"))

    print("=" * 60)
    print("Xcel RAG Microservice Integration Demonstration")
    print("=" * 60)

    # 1. Health Probe
    try:
        health = client.check_health()
        print(f"[✓] Microservice Status: {health.get('status')}")
        print(f"    Version: {health.get('version')}")
        print(f"    Active LLM: {health.get('llm_provider')} ({health.get('configured_model')})")
        print(f"    Total Documents Indexed: {health.get('total_documents')}")
    except GenAIClientError as e:
        print(f"[!] Health check failed: {e}")
        return

    # 2. Document Upload Example
    sample_pdf = "./data/samples/dbms.pdf"
    if os.path.exists(sample_pdf):
        try:
            print(f"\n[+] Uploading sample document: {sample_pdf}...")
            upload_res = client.upload_document(sample_pdf)
            print(f"[✓] Document Uploaded: {upload_res['file_name']} (ID: {upload_res['document_id']})")
            print(f"    Chunks Indexed: {upload_res['chunk_count']}, Pages: {upload_res.get('page_count')}")
        except GenAIClientError as e:
            print(f"[!] Upload error: {e}")

    # 3. Query Execution Example
    test_query = "What is database normalization and what are the benefits of 2NF and 3NF?"
    print(f"\n[+] Executing Query: '{test_query}'...")
    try:
        response = client.query(query=test_query, top_k=5, scope="hybrid")
        request_id = response["request_id"]
        print(f"[✓] Query Success (Request ID: {request_id})")
        print(f"\nGenerated Answer:\n{response['answer']}\n")

        print("Citations:")
        for src in response.get("sources", []):
            page_or_row = f"Page {src['page']}" if src.get("page") else f"Row {src.get('row')}"
            print(f"  - [{src['source_type'].upper()}] {src['file_name']} ({page_or_row}) — Match: {src.get('score')}")

        print(f"\nMetrics:")
        print(f"  Latency: {response.get('execution_metrics', {}).get('total_latency_ms')} ms")
        print(f"  Tokens: {response.get('execution_metrics', {}).get('tokens_usage')}")

        # 4. Diagnostics Trace Retrieval
        print(f"\n[+] Fetching Developer Diagnostic Trace for {request_id}...")
        trace_data = client.get_query_trace(request_id)
        print(f"[✓] Trace Retrieved:")
        print(f"    Query Type Classified: {trace_data.get('trace', {}).get('analysis', {}).get('query_type')}")
        print(f"    Candidates Retrieved: {len(trace_data.get('trace', {}).get('retrieved_candidates', []))}")

    except GenAIClientError as e:
        print(f"[!] Query failed: {e}")

if __name__ == "__main__":
    demonstrate_integration()
