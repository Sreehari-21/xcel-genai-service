import os
from typing import List, Dict, Any, Optional
import anthropic
from app.core.config import settings
from app.core.logging import log_event
from app.services.llm_base import BaseLLMService, SYSTEM_PROMPT

class ConversationManager:
    """Manages multi-turn conversation messages by conversation_id."""
    def __init__(self, max_history_turns: int = 6):
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        self.max_history_turns = max_history_turns

    def get_history(self, conversation_id: str) -> List[Dict[str, str]]:
        return self.conversations.get(conversation_id, [])

    def add_turn(self, conversation_id: str, user_msg: str, assistant_msg: str):
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append({"role": "user", "content": user_msg})
        self.conversations[conversation_id].append({"role": "assistant", "content": assistant_msg})
        
        # Keep within max history limit
        if len(self.conversations[conversation_id]) > self.max_history_turns * 2:
            self.conversations[conversation_id] = self.conversations[conversation_id][-(self.max_history_turns * 2):]

    def clear(self, conversation_id: str):
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

class ClaudeService(BaseLLMService):
    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(self, model: str = settings.claude_model):
        self.model = model
        self.conversation_manager = ConversationManager()

    def _get_client(self) -> Optional[anthropic.Anthropic]:
        api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key.strip() == "" or api_key.startswith("your_key"):
            return None
        return anthropic.Anthropic(api_key=api_key)

    def generate_answer(
        self,
        query: str,
        context: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate answer via Claude API with multi-turn history and retrieved context.
        """
        client = self._get_client()

        # Build context prompt
        context_block = context if context.strip() else "No relevant documents or records were found in the database."
        user_prompt_with_context = f"""Retrieved Context:
{context_block}

User Question:
{query}"""

        # Prepare messages
        messages = []
        if conversation_id:
            history = self.conversation_manager.get_history(conversation_id)
            for turn in history:
                messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_prompt_with_context})

        log_event(
            "CLAUDE REQUEST",
            f"Sending request to Claude model: {self.model} with {len(messages)} messages"
        )

        if not client:
            # Fallback when API key is not yet set
            log_event(
                "ERROR",
                "ANTHROPIC_API_KEY is not set or invalid. Providing informative guidance response."
            )
            fallback_answer = (
                "⚠️ **Anthropic Claude API Key Required**\n\n"
                "The RAG system retrieved the relevant context chunks successfully, but your `ANTHROPIC_API_KEY` is not set in `.env`.\n\n"
                "**Retrieved Context Summary:**\n"
                f"{context[:400]}...\n\n"
                "To enable Claude responses, add your API key to `.env`:\n"
                "```env\nANTHROPIC_API_KEY=sk-ant-api03-...\n```"
            )
            return {
                "answer": fallback_answer,
                "model_used": "mock-fallback",
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=self.SYSTEM_PROMPT,
                messages=messages
            )

            # Extract response text
            answer_text = ""
            for block in response.content:
                if block.type == "text":
                    answer_text += block.text

            log_event("CLAUDE RESPONSE", f"Received response from Claude. Tokens: in={response.usage.input_tokens}, out={response.usage.output_tokens}")

            # Record turn in conversation manager
            if conversation_id:
                # Store the user's base query rather than the huge context injection to keep history clean
                self.conversation_manager.add_turn(conversation_id, query, answer_text)

            return {
                "answer": answer_text,
                "model_used": self.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }

        except anthropic.APIConnectionError as e:
            err_msg = f"Network connection error to Claude API: {str(e)}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}
        except anthropic.RateLimitError as e:
            err_msg = f"Claude API rate limit reached: {str(e)}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}
        except anthropic.APIStatusError as e:
            err_msg = f"Claude API returned status code {e.status_code}: {e.message}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}
        except Exception as e:
            err_msg = f"Unexpected error while calling Claude API: {str(e)}"
            log_event("ERROR", err_msg)
            return {"answer": f"⚠️ {err_msg}", "error": True}

claude_service = ClaudeService()
