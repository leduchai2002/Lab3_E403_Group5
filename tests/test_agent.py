import os
import sys
from typing import Dict, List

from dotenv import load_dotenv

# Add project root to import path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.agent.agent import ReActAgent
from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.core.local_provider import LocalProvider
from src.tools.inventory_tools import INVENTORY_TOOLS


load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _clean_arg(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _build_test_tools():
    """
    Keep original tool names but sanitize quoted args produced by LLM, e.g. "iPhone 15".
    This avoids false negatives caused by wrapping quotes in Action arguments.
    """
    tools = []

    for tool in INVENTORY_TOOLS:
        name = tool.get("name")
        func = tool.get("func")
        desc = tool.get("description", "")

        if not callable(func):
            tools.append(tool)
            continue

        def _wrap(fn):
            def _inner(args: str):
                return fn(_clean_arg(args))

            return _inner

        tools.append({"name": name, "description": desc, "func": _wrap(func)})

    return tools


def build_provider():
    provider = os.getenv("DEFAULT_PROVIDER", "openai").strip().lower()
    model = os.getenv("DEFAULT_MODEL", "").strip()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing in .env")
        return OpenAIProvider(model_name=model or "gpt-4o", api_key=api_key)

    if provider in ("google", "gemini"):
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing in .env")
        return GeminiProvider(model_name=model or "gemini-1.5-flash", api_key=api_key)

    if provider == "local":
        model_path = os.getenv("LOCAL_MODEL_PATH", "").strip()
        if not model_path:
            raise ValueError("LOCAL_MODEL_PATH is missing in .env")
        return LocalProvider(model_path=model_path)

    raise ValueError(f"Unsupported DEFAULT_PROVIDER: {provider}")


def run_use_cases() -> List[Dict[str, str]]:
    agent = ReActAgent(llm=build_provider(), tools=_build_test_tools(), max_steps=5)

    use_cases = [
        {
            "name": "Case 1 - Gia iPhone 15",
            "prompt": (
                "Gia cua chiec Iphone 15 la bao nhieu ? "
                "Hay su dung du lieu cua kho hang va uu tien goi tool search_inventory de tra loi."
            ),
            "expect_response": "Gia cua chiec Iphone 15 la xx trieu dong.",
        },
        {
            "name": "Case 2 - iPhone tot nhat trong 10 trieu",
            "prompt": (
                "Toi co 10 trieu dong, lieu toi co the mua duoc mot chiec iphone tot nhat trong tam gia khong? "
                "Hay dua tren du lieu ton kho va gia trong kho, nho goi tool search_inventory."
            ),
            "expect_response": "Voi so tien hien tai, ban co the mua duoc mot chiec iPhone phu hop trong tam gia.",
        },
        {
            "name": "Case 3 - Chuong trinh giam gia",
            "prompt": (
                "Cua hang hien tai co chuong trinh giam gia nao khong? "
                "Hay tim trong du lieu kho bang tool search_inventory voi tu khoa khuyen mai."
            ),
            "expect_response": "Hien tai cua hang dang co chuong trinh giam gia cho iPhone.",
        },
        {
            "name": "Case 4 - Ton kho iPhone 14",
            "prompt": (
                "Chiec Iphone 14 co con hang khong ? "
                "Hay kiem tra ton kho bang tool search_inventory truoc khi ket luan."
            ),
            "expect_response": "He thong tra ve trang thai ton kho cua iPhone 14.",
        },
        {
            "name": "Case 5 - Ngoai du lieu",
            "prompt": (
                "Gia cua chiec Samsung s25 ultra la bao nhieu ? "
                "Hay tim trong kho bang tool search_inventory; neu khong co thi tra loi thong tin ngoai du lieu."
            ),
            "expect_response": "Thong tin nam ngoai kha nang hieu biet cua toi.",
        },
    ]

    results = []
    for idx, case in enumerate(use_cases, start=1):
        print(f"\n=== {case['name']} ===")
        print(f"Prompt: {case['prompt']}")
        answer = agent.run(case["prompt"])
        print(f"Agent: {answer}")
        print(f"Expected response: {case['expect_response']}")

        results.append(
            {
                "case": str(idx),
                "name": case["name"],
                "prompt": case["prompt"],
                "answer": answer,
                "expected_response": case["expect_response"],
            }
        )

    return results


def main():
    print("=== Inventory Agent Use-Case Runner ===")
    print("Provider/model are read from .env (DEFAULT_PROVIDER, DEFAULT_MODEL).")

    try:
        results = run_use_cases()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    print("\n=== Summary ===")
    for row in results:
        print(f"Case {row['case']}: {row['name']}")


if __name__ == "__main__":
    main()
