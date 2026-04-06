"""
Baseline Chatbot — Lab 3 (E403 Group 5)

This is the SIMPLEST possible chatbot: a stateful wrapper around any LLMProvider.
It maintains a full conversation history and forwards each turn to the LLM.

Key limitations (intentional — used to motivate the ReAct agent):
  - Cannot call tools or look things up — purely relies on the model's training data.
  - Cannot break a complex query into sub-steps.
  - Every turn re-sends the full history (no summarisation / memory management).
"""

from typing import Dict, Any, List, Optional

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


class BaselineChatbot:
    """
    A turn-based chatbot that wraps any LLMProvider.

    Conversation history is stored as a plain list of {"role": ..., "content": ...}
    dicts.  On every call to ``chat()``, the full history is serialised into a
    single prompt string and sent to the provider.  The assistant's reply is
    appended before returning so the next call has context.
    """

    # System prompt that describes the chatbot's persona.
    DEFAULT_SYSTEM_PROMPT = (
        "You are a helpful, honest, and concise AI assistant. "
        "Answer the user's questions clearly. "
        "If you do not know something, say so rather than guessing."
    )

    def __init__(
        self,
        llm: LLMProvider,
        system_prompt: Optional[str] = None,
    ):
        """
        Args:
            llm: Any concrete LLMProvider (OpenAI, Gemini, Local …).
            system_prompt: Override the default persona / instructions.
        """
        self.llm = llm
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        # Conversation history: list of {"role": "user"|"assistant", "content": str}
        self.history: List[Dict[str, str]] = []

        logger.log_event(
            "CHATBOT_INIT",
            {"model": self.llm.model_name, "provider": type(self.llm).__name__},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """
        Send a user message and return the assistant's reply.

        The method:
          1. Appends the user turn to ``self.history``.
          2. Builds a single prompt string from the full history.
          3. Calls ``llm.generate()`` with the constructed prompt.
          4. Records telemetry (latency, token usage).
          5. Appends the assistant reply to ``self.history``.
          6. Returns the reply text.

        Args:
            user_message: Raw text typed by the user.

        Returns:
            The assistant's reply as a plain string.
        """
        # 1. Record the user turn.
        self.history.append({"role": "user", "content": user_message})

        logger.log_event(
            "CHATBOT_USER",
            {"turn": len(self.history), "message": user_message},
        )

        # 2. Serialize history into a prompt the provider understands.
        prompt = self._build_prompt()

        # 3. Call the LLM (non-streaming).
        response: Dict[str, Any] = self.llm.generate(
            prompt=prompt,
            system_prompt=self.system_prompt,
        )

        # 4. Extract reply and track telemetry.
        reply: str = response.get("content", "").strip()
        usage: Dict[str, int] = response.get("usage", {})
        latency_ms: int = response.get("latency_ms", 0)
        provider: str = response.get("provider", type(self.llm).__name__)

        tracker.track_request(
            provider=provider,
            model=self.llm.model_name,
            usage=usage,
            latency_ms=latency_ms,
        )

        logger.log_event(
            "CHATBOT_ASSISTANT",
            {
                "turn": len(self.history) + 1,
                "latency_ms": latency_ms,
                "tokens": usage,
                "reply_preview": reply[:120],
            },
        )

        # 5. Record the assistant turn.
        self.history.append({"role": "assistant", "content": reply})

        return reply

    def stream_chat(self, user_message: str):
        """
        Streaming variant of ``chat()``.

        Yields text chunks as they arrive from the provider.
        After the generator is exhausted the complete reply is added to history.

        Usage::

            for chunk in bot.stream_chat("Hello!"):
                print(chunk, end="", flush=True)
        """
        self.history.append({"role": "user", "content": user_message})

        logger.log_event(
            "CHATBOT_USER_STREAM",
            {"turn": len(self.history), "message": user_message},
        )

        prompt = self._build_prompt()
        full_reply: List[str] = []

        for chunk in self.llm.stream(prompt=prompt, system_prompt=self.system_prompt):
            full_reply.append(chunk)
            yield chunk

        # Commit the completed reply to history.
        reply = "".join(full_reply).strip()
        self.history.append({"role": "assistant", "content": reply})

        logger.log_event(
            "CHATBOT_ASSISTANT_STREAM",
            {"turn": len(self.history), "reply_preview": reply[:120]},
        )

    def reset(self):
        """Clear conversation history, starting a fresh session."""
        self.history.clear()
        logger.log_event("CHATBOT_RESET", {"model": self.llm.model_name})

    def get_history(self) -> List[Dict[str, str]]:
        """Return a copy of the current conversation history."""
        return list(self.history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_prompt(self) -> str:
        """
        Serialise ``self.history`` into a plain text prompt.

        Format used::

            User: <message>
            Assistant: <reply>
            User: <next message>

        The system prompt is handled separately — it is passed straight to
        ``llm.generate()`` so that each provider can embed it correctly.
        """
        lines: List[str] = []
        for turn in self.history:
            role = turn["role"].capitalize()  # "User" | "Assistant"
            lines.append(f"{role}: {turn['content']}")
        return "\n".join(lines)
