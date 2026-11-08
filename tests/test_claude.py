from unittest.mock import patch, MagicMock
from app.services.claude_service import claude_service

def test_claude_service_prompt_construction():
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "According to DBMS.pdf (page 42), normalization eliminates redundancy."
    mock_response.content = [mock_block]
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 20

    with patch.object(claude_service, "_get_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_client_factory.return_value = mock_client

        result = claude_service.generate_answer(
            query="What is normalization?",
            context="SOURCE 1\nType: PDF\nDocument: DBMS.pdf\nPage: 42\nContent:\nNormalization decomposes tables to avoid redundancy.",
            conversation_id="conv_123"
        )

        assert "normalization" in result["answer"].lower()
        assert result["usage"]["input_tokens"] == 50
        assert result["usage"]["output_tokens"] == 20
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "Normalization decomposes tables" in call_kwargs["messages"][0]["content"]

def test_claude_service_missing_key_fallback():
    with patch.object(claude_service, "_get_client", return_value=None):
        result = claude_service.generate_answer(
            query="What is normalization?",
            context="Some test context"
        )
        assert "Anthropic Claude API Key Required" in result["answer"]
