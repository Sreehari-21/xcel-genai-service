import os
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import log_event
from app.services.llm_base import BaseLLMService, SYSTEM_PROMPT
from app.services.openai_service import ConversationManager

class OllamaService(BaseLLMService):
    """Local LLM service powered by Ollama REST API."""

    def __init__(self, base_url: str = settings.ollama_base_url, model: str = settings.ollama_model):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.conversation_manager = ConversationManager()

    def generate_answer(
        self,
        query: str,
        context: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate answer using local Ollama model."""
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
            "QUERY",
            f"Sending request to Ollama ({self.base_url}) with model: {self.model}"
        )

        try:
            with httpx.Client(timeout=45.0) as client:
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
                    return {
                        "answer": f"⚠️ {err_msg}",
                        "model_used": self.model,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                        "error": True
                    }

                data = res.json()
                answer_text = data.get("message", {}).get("content", "")
                input_tokens = data.get("prompt_eval_count", 0)
                output_tokens = data.get("eval_count", 0)

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

        except httpx.ConnectError:
            err_msg = (
                f"⚠️ **Ollama Service Unavailable**\n\n"
                f"Could not connect to Ollama at `{self.base_url}`.\n\n"
                f"To use local LLM inference:\n"
                f"1. Start Ollama: `ollama serve`\n"
                f"2. Pull the model: `ollama pull {self.model}`\n"
                f"3. Or switch `LLM_PROVIDER=openai` in `.env`."
            )
            log_event("ERROR", f"Cannot connect to Ollama at {self.base_url}")
            return {
                "answer": err_msg,
                "model_used": self.model,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "error": True
            }
        except httpx.TimeoutException:
            err_msg = f"⚠️ Request to Ollama model `{self.model}` timed out after 45 seconds."
            log_event("ERROR", err_msg)
            return {
                "answer": err_msg,
                "model_used": self.model,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "error": True
            }
        except Exception as e:
            err_msg = f"Unexpected error while calling Ollama: {str(e)}"
            log_event("ERROR", err_msg)
            return {
                "answer": f"⚠️ {err_msg}",
                "model_used": self.model,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "error": True
            }

ollama_service = OllamaService()
