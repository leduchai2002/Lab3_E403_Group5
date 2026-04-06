"""
src/chatbot/runner.py — Provider factory + interactive CLI loop.

All chatbot-orchestration logic lives here so that the project root
``main.py`` is just a thin entry-point shim.
"""

import os
import sys
import argparse
from typing import Optional

from dotenv import load_dotenv

from src.core.llm_provider import LLMProvider
from src.chatbot.chatbot import BaselineChatbot
from src.telemetry.logger import logger


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def build_provider(provider_name: str) -> LLMProvider:
    """
    Instantiate the correct LLMProvider based on the given name.

    Reads API keys and model settings from environment variables
    (loaded from .env by the caller before this function is invoked).

    Args:
        provider_name: One of ``"openai"``, ``"google"``/``"gemini"``, or ``"local"``.

    Returns:
        A ready-to-use LLMProvider instance.

    Raises:
        ValueError: Unrecognised provider name or missing API key.
        FileNotFoundError: Local model GGUF file not found at the configured path.
    """
    from src.core.openai_provider import OpenAIProvider
    from src.core.gemini_provider import GeminiProvider

    provider_name = provider_name.lower().strip()

    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in your .env file.")
        model = os.getenv("DEFAULT_MODEL", "gpt-4o")
        print(f"[Provider] OpenAI  •  model: {model}")
        return OpenAIProvider(model_name=model, api_key=api_key)

    elif provider_name in ("google", "gemini"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in your .env file.")
        model = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
        print(f"[Provider] Gemini  •  model: {model}")
        return GeminiProvider(model_name=model, api_key=api_key)

    elif provider_name == "local":
        # Import only when needed — llama-cpp is a heavy optional dependency.
        from src.core.local_provider import LocalProvider

        model_path = os.getenv(
            "LOCAL_MODEL_PATH",
            "./models/Phi-3-mini-4k-instruct-q4.gguf",
        )
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Local model not found at '{model_path}'.\n"
                "Set LOCAL_MODEL_PATH in .env to point to your .gguf file."
            )
        print(f"[Provider] Local (llama-cpp)  •  model: {os.path.basename(model_path)}")
        return LocalProvider(model_path=model_path)

    else:
        raise ValueError(
            f"Unknown provider '{provider_name}'. "
            "Choose from: openai | google | local"
        )


# ---------------------------------------------------------------------------
# Interactive CLI loop
# ---------------------------------------------------------------------------

def run_chat_loop(chatbot: BaselineChatbot, stream: bool = False) -> None:
    """
    Interactive REPL for the chatbot.

    Built-in commands (type at the ``You:`` prompt):
        ``/reset``    — clear conversation history
        ``/history``  — print the full conversation so far
        ``/quit``     — exit the loop

    Args:
        chatbot: Initialised BaselineChatbot instance.
        stream:  If True, print tokens as they arrive (streaming mode).
    """
    print("\n" + "=" * 60)
    print("  Baseline Chatbot — Lab 3  (E403 Group 5)")
    print("  Commands: /reset | /history | /quit")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Chatbot] Session ended.")
            break

        if not user_input:
            continue

        # ---- Built-in commands ----
        if user_input.lower() == "/quit":
            print("[Chatbot] Goodbye!")
            break

        elif user_input.lower() == "/reset":
            chatbot.reset()
            print("[Chatbot] Conversation history cleared.\n")
            continue

        elif user_input.lower() == "/history":
            history = chatbot.get_history()
            if not history:
                print("[Chatbot] No history yet.\n")
            else:
                print("\n--- Conversation History ---")
                for i, turn in enumerate(history, 1):
                    role = turn["role"].capitalize()
                    print(f"[{i}] {role}: {turn['content']}\n")
            continue

        # ---- LLM call ----
        print("Assistant: ", end="", flush=True)

        try:
            if stream:
                for chunk in chatbot.stream_chat(user_input):
                    print(chunk, end="", flush=True)
                print()  # newline after stream ends
            else:
                reply = chatbot.chat(user_input)
                print(reply)

        except Exception as exc:
            logger.error(f"Error during LLM call: {exc}")
            print(f"\n[ERROR] {exc}")

        print()  # blank line between turns


# ---------------------------------------------------------------------------
# Argument parser (shared so main.py stays trivial)
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Return parsed CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Lab 3 — Baseline Chatbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Commands inside the chat loop:\n"
            "  /reset    — clear conversation history\n"
            "  /history  — show conversation history\n"
            "  /quit     — exit\n"
        ),
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="LLM provider: openai | google | local  (overrides DEFAULT_PROVIDER in .env)",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        default=False,
        help="Enable streaming output.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Standalone entry (python -m src.chatbot.runner)
# ---------------------------------------------------------------------------

def main() -> None:
    """Load .env, build provider, and start the interactive loop."""
    # Ensure project root is on sys.path when run directly.
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    load_dotenv()

    args = parse_args()
    provider_name = args.provider or os.getenv("DEFAULT_PROVIDER", "openai")

    try:
        llm = build_provider(provider_name)
    except (ValueError, FileNotFoundError) as err:
        print(f"[FATAL] {err}")
        sys.exit(1)

    bot = BaselineChatbot(llm=llm)
    run_chat_loop(chatbot=bot, stream=args.stream)


if __name__ == "__main__":
    main()
