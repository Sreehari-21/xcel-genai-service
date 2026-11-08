from unittest.mock import patch, MagicMock
from app.services.openai_service import openai_service

def test_openai_service_prompt_construction():
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "According to DBMS.pdf (page 42), normalization eliminates redundancy."
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 55
    mock_response.usage.completion_tokens = 22

    with patch.object(openai_service, "_get_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_factory.return_value = mock_client

        result = openai_service.generate_answer(
            query="What is normalization?",
            context="SOURCE 1\nType: PDF\nDocument: DBMS.pdf\nPage: 42\nContent:\nNormalization decomposes tables to avoid redundancy.",
            conversation_id="conv_openai_123"
        )

        assert "normalization" in result["answer"].lower()
        assert result["usage"]["input_tokens"] == 55
        assert result["usage"]["output_tokens"] == 22
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "Normalization decomposes tables" in call_kwargs["messages"][-1]["content"]

def test_openai_service_missing_key_fallback():
    with patch.object(openai_service, "_get_client", return_value=None):
        result = openai_service.generate_answer(
            query="What is normalization?",
            context="Some test context"
        )
        assert "OpenAI API Key Required" in result["answer"]
