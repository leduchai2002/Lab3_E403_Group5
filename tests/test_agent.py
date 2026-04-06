"""
3-Phase Comparative Test Runner
Runs the same 5 use cases across:
  Phase 1 — Single LLM (BaselineChatbot, no tools)
  Phase 2 — ReAct Agent v1 (tools + prompt v1)
  Phase 3 — ReAct Agent v2 (tools v2 + prompt v2, grounded)

Produces a Markdown report with per-case comparison and conclusions.
"""

import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from src.agent.agent import ReActAgent
from src.chatbot.chatbot import BaselineChatbot
from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.core.local_provider import LocalProvider
from src.telemetry.metrics import tracker
from src.tools.inventory_tools import INVENTORY_TOOLS
from src.tools.inventory_tools_v2 import INVENTORY_TOOLS_V2

# ── Use cases ──────────────────────────────────────────────────────────────────

USE_CASES = [
    {
        "id": 1,
        "name": "Gia iPhone 15",
        "prompt": (
            "Gia cua chiec Iphone 15 la bao nhieu ? "
            "Hay su dung du lieu cua kho hang va uu tien goi tool search_inventory de tra loi."
        ),
        "expected": "Tra ve gia chinh xac cua iPhone 15 tu du lieu kho.",
    },
    {
        "id": 2,
        "name": "iPhone tot nhat trong 10 trieu",
        "prompt": (
            "Toi co 10 trieu dong, lieu toi co the mua duoc mot chiec iphone tot nhat trong tam gia khong? "
            "Hay dua tren du lieu ton kho va gia trong kho, nho goi tool search_inventory."
        ),
        "expected": "Goi y iPhone phu hop nhat trong tam gia 10 trieu dua tren du lieu thuc te.",
    },
    {
        "id": 3,
        "name": "Chuong trinh khuyen mai",
        "prompt": (
            "Cua hang hien tai co chuong trinh giam gia nao khong? "
            "Hay tim trong du lieu kho bang tool search_inventory voi tu khoa khuyen mai."
        ),
        "expected": "Liet ke cac chuong trinh khuyen mai dang co trong kho.",
    },
    {
        "id": 4,
        "name": "Ton kho iPhone 14",
        "prompt": (
            "Chiec Iphone 14 co con hang khong ? "
            "Hay kiem tra ton kho bang tool search_inventory truoc khi ket luan."
        ),
        "expected": "Tra ve trang thai ton kho chinh xac cua iPhone 14.",
    },
    {
        "id": 5,
        "name": "San pham ngoai du lieu (Samsung S25)",
        "prompt": (
            "Gia cua chiec Samsung s25 ultra la bao nhieu ? "
            "Hay tim trong kho bang tool search_inventory; neu khong co thi tra loi thong tin ngoai du lieu."
        ),
        "expected": "Bao san pham khong co trong kho, khong tu y bịa gia.",
    },
]

# ── Provider factory ────────────────────────────────────────────────────────────

def build_provider() -> Any:
    provider = os.getenv("DEFAULT_PROVIDER", "openai").strip().lower()
    model = os.getenv("DEFAULT_MODEL", "").strip()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing in .env")
        return OpenAIProvider(model_name=model or "gpt-4o-mini", api_key=api_key)

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

    raise ValueError(f"Unsupported DEFAULT_PROVIDER: '{provider}'")


# ── Phase runners ───────────────────────────────────────────────────────────────

def _run_single_case_chatbot(bot: BaselineChatbot, case: Dict) -> Dict:
    """Run one use case through the baseline chatbot."""
    t0 = time.time()
    try:
        # Fresh history per case — avoid cross-contamination
        bot.reset()
        answer = bot.chat(case["prompt"])
        status = "COMPLETED"
        error = None
    except Exception as exc:
        answer = ""
        status = "ERROR"
        error = str(exc)
    return {
        "id": case["id"],
        "name": case["name"],
        "prompt": case["prompt"],
        "expected": case["expected"],
        "answer": answer,
        "status": status,
        "error": error,
        "duration_ms": int((time.time() - t0) * 1000),
    }


def _run_single_case_agent(agent: ReActAgent, case: Dict) -> Dict:
    """Run one use case through a ReActAgent."""
    t0 = time.time()
    try:
        answer = agent.run(case["prompt"])
        status = "COMPLETED"
        error = None
    except Exception as exc:
        answer = ""
        status = "ERROR"
        error = str(exc)
    return {
        "id": case["id"],
        "name": case["name"],
        "prompt": case["prompt"],
        "expected": case["expected"],
        "answer": answer,
        "status": status,
        "error": error,
        "duration_ms": int((time.time() - t0) * 1000),
    }


def _slice_metrics(start_idx: int) -> List[Dict]:
    return tracker.session_metrics[start_idx:]


def run_phase_chatbot(llm) -> tuple[List[Dict], List[Dict]]:
    print("\n" + "=" * 60)
    print("PHASE 1 — Single LLM (no tools)")
    print("=" * 60)
    bot = BaselineChatbot(llm=llm)
    start_idx = len(tracker.session_metrics)
    results = []
    for case in USE_CASES:
        print(f"\n  [{case['id']}] {case['name']}")
        r = _run_single_case_chatbot(bot, case)
        print(f"  Answer  : {r['answer'][:120]}{'...' if len(r['answer']) > 120 else ''}")
        print(f"  Status  : {r['status']}  ({r['duration_ms']} ms)")
        results.append(r)
    return results, _slice_metrics(start_idx)


def run_phase_agent_v1(llm) -> tuple[List[Dict], List[Dict]]:
    print("\n" + "=" * 60)
    print("PHASE 2 — ReAct Agent v1")
    print("=" * 60)
    agent = ReActAgent(llm=llm, tools=INVENTORY_TOOLS, max_steps=5, prompt_version="v1")
    start_idx = len(tracker.session_metrics)
    results = []
    for case in USE_CASES:
        print(f"\n  [{case['id']}] {case['name']}")
        r = _run_single_case_agent(agent, case)
        print(f"  Answer  : {r['answer'][:120]}{'...' if len(r['answer']) > 120 else ''}")
        print(f"  Status  : {r['status']}  ({r['duration_ms']} ms)")
        results.append(r)
    return results, _slice_metrics(start_idx)


def run_phase_agent_v2(llm) -> tuple[List[Dict], List[Dict]]:
    print("\n" + "=" * 60)
    print("PHASE 3 — ReAct Agent v2 (grounded, list_all tool)")
    print("=" * 60)
    agent = ReActAgent(llm=llm, tools=INVENTORY_TOOLS_V2, max_steps=5, prompt_version="v2")
    start_idx = len(tracker.session_metrics)
    results = []
    for case in USE_CASES:
        print(f"\n  [{case['id']}] {case['name']}")
        r = _run_single_case_agent(agent, case)
        print(f"  Answer  : {r['answer'][:120]}{'...' if len(r['answer']) > 120 else ''}")
        print(f"  Status  : {r['status']}  ({r['duration_ms']} ms)")
        results.append(r)
    return results, _slice_metrics(start_idx)


# ── Report writer ───────────────────────────────────────────────────────────────

def _phase_metric_summary(metrics: List[Dict]) -> Dict:
    if not metrics:
        return {"llm_calls": 0, "total_tokens": 0, "total_cost": 0.0, "total_latency_ms": 0}
    return {
        "llm_calls": len(metrics),
        "total_tokens": sum(m.get("total_tokens", 0) for m in metrics),
        "total_cost": sum(m.get("cost_estimate", 0.0) for m in metrics),
        "total_latency_ms": sum(m.get("latency_ms", 0) for m in metrics),
    }


def write_report(
    llm_results: List[Dict],
    v1_results: List[Dict],
    v2_results: List[Dict],
    llm_metrics: List[Dict],
    v1_metrics: List[Dict],
    v2_metrics: List[Dict],
    model_name: str,
    provider_name: str,
) -> str:
    now = datetime.now()
    report_dir = os.path.join(PROJECT_ROOT, "report")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(
        report_dir, f"comparative_report_{now.strftime('%Y%m%d_%H%M%S')}.md"
    )

    lm = _phase_metric_summary(llm_metrics)
    v1m = _phase_metric_summary(v1_metrics)
    v2m = _phase_metric_summary(v2_metrics)

    llm_errors = sum(1 for r in llm_results if r["status"] == "ERROR")
    v1_errors  = sum(1 for r in v1_results  if r["status"] == "ERROR")
    v2_errors  = sum(1 for r in v2_results  if r["status"] == "ERROR")

    lines = [
        "# Comparative Test Report — Single LLM vs Agent v1 vs Agent v2",
        "",
        f"- **Date**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Provider**: {provider_name}  |  **Model**: {model_name}",
        f"- **Total use cases**: {len(USE_CASES)}",
        "",
        "---",
        "",
        "## Phase Metrics Summary",
        "",
        "| Metric | Single LLM | Agent v1 | Agent v2 |",
        "|--------|-----------|---------|---------|",
        f"| LLM calls | {lm['llm_calls']} | {v1m['llm_calls']} | {v2m['llm_calls']} |",
        f"| Total tokens | {lm['total_tokens']:,} | {v1m['total_tokens']:,} | {v2m['total_tokens']:,} |",
        f"| Estimated cost | ${lm['total_cost']:.4f} | ${v1m['total_cost']:.4f} | ${v2m['total_cost']:.4f} |",
        f"| Total LLM latency | {lm['total_latency_ms']:,} ms | {v1m['total_latency_ms']:,} ms | {v2m['total_latency_ms']:,} ms |",
        f"| Errors | {llm_errors} | {v1_errors} | {v2_errors} |",
        "",
        "---",
        "",
        "## Per-Case Results",
        "",
        "| # | Case | Single LLM | Agent v1 | Agent v2 |",
        "|---|------|-----------|---------|---------|",
    ]

    for i in range(len(USE_CASES)):
        lr = llm_results[i]
        v1r = v1_results[i]
        v2r = v2_results[i]
        lines.append(
            f"| {lr['id']} | {lr['name']} "
            f"| {lr['status']} ({lr['duration_ms']} ms) "
            f"| {v1r['status']} ({v1r['duration_ms']} ms) "
            f"| {v2r['status']} ({v2r['duration_ms']} ms) |"
        )

    lines += [
        "",
        "---",
        "",
        "## Case-by-Case Comparison",
        "",
    ]

    for i in range(len(USE_CASES)):
        lr  = llm_results[i]
        v1r = v1_results[i]
        v2r = v2_results[i]
        lines += [
            f"### Case {lr['id']} — {lr['name']}",
            "",
            f"> **Prompt:** {lr['prompt']}",
            f"> **Expected:** {lr['expected']}",
            "",
            "| Phase | Answer | Duration |",
            "|-------|--------|----------|",
            f"| Single LLM | {lr['answer'].replace(chr(10), ' ') or '*(error)*'} | {lr['duration_ms']} ms |",
            f"| Agent v1   | {v1r['answer'].replace(chr(10), ' ') or '*(error)*'} | {v1r['duration_ms']} ms |",
            f"| Agent v2   | {v2r['answer'].replace(chr(10), ' ') or '*(error)*'} | {v2r['duration_ms']} ms |",
            "",
        ]
        if lr.get("error") or v1r.get("error") or v2r.get("error"):
            if lr.get("error"):
                lines.append(f"**LLM Error**: `{lr['error']}`  ")
            if v1r.get("error"):
                lines.append(f"**v1 Error**: `{v1r['error']}`  ")
            if v2r.get("error"):
                lines.append(f"**v2 Error**: `{v2r['error']}`  ")
            lines.append("")
        lines.append("---")
        lines.append("")

    # ── Analysis ────────────────────────────────────────────────────────────────
    avg_llm_ms = lm['total_latency_ms'] // max(lm['llm_calls'], 1)
    avg_v1_ms  = v1m['total_latency_ms'] // max(v1m['llm_calls'], 1)
    avg_v2_ms  = v2m['total_latency_ms'] // max(v2m['llm_calls'], 1)

    v1_calls_per_case = v1m['llm_calls'] / max(len(USE_CASES), 1)
    v2_calls_per_case = v2m['llm_calls'] / max(len(USE_CASES), 1)

    lines += [
        "## Conclusions",
        "",
        "### Phase 1 — Single LLM: What can it do?",
        "",
        "- Trả lời dựa hoàn toàn vào **training data** của model, không có dữ liệu thực tế.",
        "- Không biết tồn kho, giá hiện tại, hay khuyến mãi — dễ **hallucinate** số liệu.",
        f"- Mỗi câu hỏi chỉ tốn **1 LLM call**, latency trung bình {avg_llm_ms:,} ms.",
        "- Phù hợp cho câu hỏi chung, không phù hợp cho nghiệp vụ cần dữ liệu thực.",
        "",
        "### Phase 2 — Agent v1: ReAct thêm được gì?",
        "",
        "- Có thể **gọi tool** để lấy dữ liệu thực từ kho hàng trước khi trả lời.",
        f"- Trung bình **{v1_calls_per_case:.1f} LLM calls/case** do cần thêm bước Thought → Action → Observation.",
        f"- Latency trung bình tăng lên {avg_v1_ms:,} ms/call, tổng token tăng lên {v1m['total_tokens']:,}.",
        "- Nhược điểm: prompt v1 không cấm dùng kiến thức ngoài → vẫn có thể hallucinate",
        "  khi tool không trả về kết quả (thấy rõ ở Case 5 — Samsung S25).",
        "",
        "### Phase 3 — Agent v2: Fix được gì so với v1?",
        "",
        "- **Prompt v2** thêm rule cứng: chỉ trả lời từ kết quả tool, không dùng kiến thức ngoài.",
        "- **Tool `list_all_inventory`** cho phép liệt kê toàn bộ kho mà không cần từ khóa.",
        f"- Tổng token: {v2m['total_tokens']:,} (so với v1: {v1m['total_tokens']:,})",
        f"- Chi phí ước tính: ${v2m['total_cost']:.4f} (so với v1: ${v1m['total_cost']:.4f})",
        "- Case 5 (Samsung S25): v2 phải báo không có trong kho, không tự bịa giá.",
        "",
        "### Tổng hợp",
        "",
        "| Tiêu chí | Single LLM | Agent v1 | Agent v2 |",
        "|----------|-----------|---------|---------|",
        "| Dùng dữ liệu thực | Không | Có | Có |",
        "| Chống hallucination | Không | Một phần | Có (rule cứng) |",
        f"| LLM calls / case | 1 | ~{v1_calls_per_case:.1f} | ~{v2_calls_per_case:.1f} |",
        f"| Chi phí / session | ${lm['total_cost']:.4f} | ${v1m['total_cost']:.4f} | ${v2m['total_cost']:.4f} |",
        "| List toàn bộ kho | Không | Không (cần từ khóa) | Có (`list_all_inventory`) |",
        "",
    ]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


# ── Entry point ─────────────────────────────────────────────────────────────────

def main():
    print("=== 3-Phase Comparative Test Runner ===")
    print("Single LLM  →  Agent v1  →  Agent v2\n")

    try:
        llm = build_provider()
    except ValueError as exc:
        print(f"[CONFIG ERROR] {exc}")
        sys.exit(1)

    llm_results, llm_metrics = run_phase_chatbot(llm)
    v1_results,  v1_metrics  = run_phase_agent_v1(llm)
    v2_results,  v2_metrics  = run_phase_agent_v2(llm)

    report_path = write_report(
        llm_results, v1_results, v2_results,
        llm_metrics, v1_metrics, v2_metrics,
        model_name=llm.model_name,
        provider_name=llm.__class__.__name__,
    )

    print(f"\n{'=' * 60}")
    print(f"Report saved: {report_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
