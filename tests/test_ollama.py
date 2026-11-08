import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
import httpx
from app.services.ollama_service import ollama_service

def test_ollama_service_prompt_construction_and_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "According to students.csv (Row 3), Anu scored 95 in DBMS."},
        "prompt_eval_count": 65,
        "eval_count": 25
    }

    with patch("httpx.Client.post", return_value=mock_response):
        result = ollama_service.generate_answer(
            query="Which student scored 95?",
            context="SOURCE 1\nType: CSV\nFile: students.csv\nRow: 3\nContent:\nName: Anu | Marks: 95",
            conversation_id="conv_ollama_1"
        )

        assert "Anu" in result["answer"]
        assert result["usage"]["input_tokens"] == 65
        assert result["usage"]["output_tokens"] == 25
        assert result.get("error") is None or result.get("error") is False

def test_ollama_service_connection_error_raises_502():
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(HTTPException) as exc_info:
            ollama_service.generate_answer(
                query="What is normalization?",
                context="Some test context"
            )
        assert exc_info.value.status_code == 502
        assert "Cannot connect to Ollama" in exc_info.value.detail

def test_ollama_service_timeout_raises_504():
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(HTTPException) as exc_info:
            ollama_service.generate_answer(
                query="What is normalization?",
                context="Some test context"
            )
        assert exc_info.value.status_code == 504
        assert "timed out" in exc_info.value.detail.lower()

