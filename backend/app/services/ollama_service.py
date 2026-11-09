from typing import List, Dict, Any, Optional
from fastapi import HTTPException
import httpx
from app.core.config import settings
from app.core.logging import log_event
from app.services.llm_base import BaseLLMService, SYSTEM_PROMPT, ConversationManager

class OllamaService(BaseLLMService):
    """Local LLM service powered by Ollama REST API (qwen2.5:7b)."""

    def __init__(
        self,
        base_url: str = settings.ollama_base_url or "http://localhost:11434",
        model: str = settings.ollama_model or "qwen2.5:7b"
    ):
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.model = model or "qwen2.5:7b"
        self.conversation_manager = ConversationManager()

    def verify_model_loaded(self) -> bool:
        """Verify that the model is loaded and accessible in Ollama."""
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name", "") for m in res.json().get("models", [])]
                    is_loaded = any(self.model in m or m.startswith(self.model) for m in models)
                    if is_loaded:
                        log_event("OLLAMA", f"Verified model '{self.model}' is loaded in Ollama at {self.base_url}.")
                        return True
                    else:
                        log_event("WARN", f"Model '{self.model}' not found in Ollama tags: {models}")
                        return False
        except Exception as e:
            log_event("WARN", f"Could not verify Ollama models at {self.base_url}: {e}")
            return False

    def generate_answer(
        self,
        query: str,
        context: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate answer using local Ollama model (qwen2.5:7b) passing retrieved context."""
        context_block = context if context.strip() else "No relevant documents or records were found in the database."
        user_prompt_with_context = f"""Retrieved Context:
{context_block}

User Question:
{query}"""

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if conversation_id:
            history = self.conversation_manager.get_history(conversation_id)
            for turn in history:
                messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_prompt_with_context})

        log_event(
            "OLLAMA",
            f"Sending generation request to Ollama ({self.base_url}) with model: {self.model}"
        )

        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": 0.1
                        }
                    }
                )

                if res.status_code != 200:
                    err_msg = f"Ollama API returned HTTP {res.status_code}: {res.text}"
                    log_event("ERROR", err_msg)
                    # Requirement 7: Do not return HTTP 200 with error disguised as answer
                    raise HTTPException(status_code=502, detail=f"Ollama generation failed: {err_msg}")

                data = res.json()
                answer_text = data.get("message", {}).get("content", "").strip()
                if not answer_text:
                    raise HTTPException(status_code=502, detail="Ollama returned an empty response.")

                input_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", 0)

                log_event(
                    "OLLAMA",
                    f"Generated answer via Ollama ({self.model}). Input tokens: {input_tokens}, Output tokens: {output_tokens}"
                )

                if conversation_id:
                    self.conversation_manager.add_turn(conversation_id, query, answer_text)

                return {
                    "answer": answer_text,
                    "model_used": self.model,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens
                    }
                }

        except httpx.ConnectError as e:
            err_msg = f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running (`ollama serve`)."
            log_event("ERROR", err_msg)
            raise HTTPException(status_code=502, detail=err_msg)

        except httpx.TimeoutException as e:
            err_msg = f"Request to Ollama model '{self.model}' timed out after 60 seconds."
            log_event("ERROR", err_msg)
            raise HTTPException(status_code=504, detail=err_msg)

ollama_service = OllamaService()
