"""
Smoke test for LocalProvider (Phi-3-mini via llama-cpp).
Verifies the local model can load and produce streaming output.
"""

import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from src.core.local_provider import LocalProvider

PROMPT = "Explain what an AI Agent is in one sentence."


def test_local_provider():
    model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf").strip()

    print(f"Model path : {model_path}")

    if not os.path.exists(model_path):
        print(f"[SKIP] Model file not found at '{model_path}'.")
        print("Download it from Hugging Face and place it in the models/ folder.")
        return

    try:
        provider = LocalProvider(model_path=model_path)
        print(f"Prompt    : {PROMPT}")
        print("Response  : ", end="", flush=True)
        for chunk in provider.stream(PROMPT):
            print(chunk, end="", flush=True)
        print("\n[OK] LocalProvider is working.")
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    test_local_provider()
