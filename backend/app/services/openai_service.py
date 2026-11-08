import os
from typing import List, Dict, Any, Optional
import openai
from app.core.config import settings
from app.core.logging import log_event
from app.services.llm_base import BaseLLMService, SYSTEM_PROMPT
from app.services.trace_service import trace_service

class ConversationManager:
    """Manages multi-turn conversation messages with SQLite persistence."""
    def __init__(self, max_history_turns: int = 6):
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        self.max_history_turns = max_history_turns

    def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        if conversation_id not in self.conversations:
            # Load from persistent SQLite
            loaded = trace_service.get_conversation_history(conversation_id, self.max_history_turns)
            self.conversations[conversation_id] = loaded
        return self.conversations.get(conversation_id, [])

    def add_turn(self, conversation_id: str, user_msg: str, assistant_msg: str):
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append({"role": "user", "content": user_msg})
        self.conversations[conversation_id].append({"role": "assistant", "content": assistant_msg})
        
        # Persist to SQLite
        trace_service.save_conversation_turn(conversation_id, "user", user_msg)
        trace_service.save_conversation_turn(conversation_id, "assistant", assistant_msg)

        # Keep within max history limit
        if len(self.conversations[conversation_id]) > self.max_history_turns * 2:
            self.conversations[conversation_id] = self.conversations[conversation_id][-(self.max_history_turns * 2):]

    def clear(self, conversation_id: str):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

class OpenAIService(BaseLLMService):
    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(self, model: str = settings.openai_model):
        self.model = model
        self.conversation_manager = ConversationManager()

    def _get_client(self) -> Optional[openai.OpenAI]:
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.strip() == "" or api_key.startswith("your_key"):
            return None
        return openai.OpenAI(api_key=api_key)

    def generate_answer(
        self,
        query: str,
        context: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate answer via OpenAI API with multi-turn history and retrieved context.
        """
        client = self._get_client()

        # Build context prompt
        context_block = context if context.strip() else "No relevant documents or records were found in the database."
        user_prompt_with_context = f"""Retrieved Context:
{context_block}

User Question:
{query}"""

        # Prepare messages
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        if conversation_id:
            history = self.conversation_manager.get_history(conversation_id)
            for turn in history:
                messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_prompt_with_context})

        log_event(
            "QUERY",
            f"Sending request to OpenAI model: {self.model} with {len(messages)} messages"
        )

        if not client:
            # Fallback when API key is not yet set
            log_event(
                "ERROR",
                "OPENAI_API_KEY is not set or invalid. Providing informative guidance response."
            )
            fallback_answer = (
                "⚠️ **OpenAI API Key Required**\n\n"
                "The RAG system retrieved the relevant context chunks successfully, but your `OPENAI_API_KEY` is not configured in `.env`.\n\n"
                "**Retrieved Context Summary:**\n"
                f"{context[:400]}...\n\n"
                "To enable OpenAI responses, add your API key to `.env`:\n"
                "```env\nOPENAI_API_KEY=sk-proj-...\nOPENAI_MODEL=gpt-4o\n```"
            )
            return {
                "answer": fallback_answer,
                "model_used": "mock-fallback",
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=1500
            )

            answer_text = response.choices[0].message.content or ""
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            log_event(
                "QUERY",
                f"Received response from OpenAI ({self.model}). Tokens: in={input_tokens}, out={output_tokens}"
            )

            # Record turn in conversation manager
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

        except openai.AuthenticationError as e:
            err_msg = f"OpenAI authentication failed: {str(e)}. Please check your OPENAI_API_KEY."
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}
        except openai.RateLimitError as e:
            err_msg = f"OpenAI rate limit or quota exceeded: {str(e)}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}
        except openai.APIConnectionError as e:
            err_msg = f"Connection error to OpenAI API: {str(e)}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}
        except openai.APIStatusError as e:
            err_msg = f"OpenAI API status error ({e.status_code}): {e.message}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}
        except Exception as e:
            err_msg = f"Unexpected error while calling OpenAI API: {str(e)}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}

openai_service = OpenAIService()
# Alias for generic LLM service
llm_service = openai_service
