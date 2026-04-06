# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: E403 Group 5
- **Team Members**: [Update member names]
- **Deployment Date**: 2026-04-06

---

## 1. Executive Summary

This project implements a ReAct inventory assistant for phone-store queries using local inventory tools and structured telemetry logs. We evaluated the agent on 5 predefined use cases (price lookup, budget recommendation, promotions, stock check, and out-of-dataset handling).

- **Success Rate**: 2/5 strict-match (40%) on current v1 criteria
- **Key Outcome**: The agent can reliably call tools for product lookups, but still fails in rule-constrained outputs (promotion normalization, strict stock-policy answer, and out-of-scope fallback wording).

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

The agent follows the loop:
1. Generate `Thought` + `Action`
2. Parse action from LLM output (`Action: tool_name(args)`)
3. Execute tool and append `Observation`
4. Repeat until `Final Answer` or max steps

Implementation details:
- File: `src/agent/agent.py`
- Loop control: `max_steps=5`
- Telemetry events logged at each LLM step and tool call

### 2.2 Tool Definitions (Inventory)

| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `search_inventory` | `string` | Search products/promotions by keyword in `data/inventory.json`. |
| `update_inventory` | `"<id>, price=<value>, stock=<value>"` | Update product price/stock. |
| `delete_inventory` | `"<id>"` | Remove inventory item by id. |

### 2.3 LLM Providers Used

- **Primary**: OpenAI `gpt-4o`
- **Secondary (Backup)**: Gemini provider exists in codebase (not primary in this run)

---

## 3. Telemetry & Performance Dashboard

Metrics were calculated from the latest 5-case run logs.

- **Average Latency (P50 per task)**: 2142ms
- **Max Latency (observed peak)**: 3098ms
- **Average Tokens per Task**: 697 tokens
- **Total Cost of Test Suite (estimate from logs)**: $0.03483

Per-case summary:

| Case | Total Latency | Total Tokens | Cost Estimate |
| :--- | :--- | :--- | :--- |
| Case 1 | 1864ms | 645 | $0.00645 |
| Case 2 | 3097ms | 1179 | $0.01179 |
| Case 3 | 2088ms | 501 | $0.00501 |
| Case 4 | 2142ms | 636 | $0.00636 |
| Case 5 | 3098ms | 522 | $0.00522 |

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study A: Promotion query mismatch
- **Input**: "Cua hang hien tai co chuong trinh giam gia nao khong?"
- **Observation**: Agent queried `search_inventory("khuyến mãi")`, inventory data used non-accented strings (`Khuyen mai ...`), resulting in no match.
- **Root Cause**: Tool search is case-insensitive but not accent-normalized; lexical mismatch between query accents and stored data.

### Case Study B: Out-of-dataset policy drift
- **Input**: "Gia cua chiec Samsung s25 ultra la bao nhieu?"
- **Observation**: Tool returned no match, but model still added outside knowledge instead of strict fallback.
- **Root Cause**: Prompt guardrails not strict enough for "dataset-only" response policy.

### Case Study C: Expected stock answer mismatch
- **Input**: "Chiec Iphone 14 co con hang khong?"
- **Observation**: Agent correctly found stock > 0 from data, but expected test answer required "sold out".
- **Root Cause**: Data-test expectation misalignment (dataset content contradicts expected answer).

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs Prompt v2 (tool-first prompting)
- **Diff**: Added prompt clauses in test runner to force tool usage (`search_inventory`) before answering.
- **Result**: Tool-call rate improved; fewer generic LLM answers like "I don't have real-time data".

### Experiment 2: Chatbot vs Agent (same 5 scenarios)

| Case | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| Price lookup (iPhone 15) | Hallucination risk | Grounded by inventory tool | **Agent** |
| Budget recommendation (10M) | Generic suggestion | Data-grounded recommendation | **Agent** |
| Promotion lookup | Inconsistent/no data grounding | Tool used but text-normalization issue | Draw |
| Stock check | Generic | Correctly grounded to stock data | **Agent** |
| Out-of-dataset | Often confident guess | Partial fallback, but policy drift remains | Draw |

---

## 6. Production Readiness Review

- **Security**: Validate and sanitize tool arguments before execution.
- **Guardrails**: Enforce strict "dataset-only" fallback policy for unknown products.
- **Data Quality**: Normalize text (accent-insensitive search) and keep expected answers aligned with data snapshots.
- **Reliability**: Add regression tests for exact business policies (e.g., sold-out wording, unknown-item response template).
- **Scalability**: Split inventory and promotions into separate datasets/tools for cleaner reasoning paths.

---

## 7. Action Items for v2

1. Add accent-insensitive normalization in `search_inventory`.
2. Add a dedicated `search_promotions` tool.
3. Add policy-constrained final answer template for unknown products.
4. Freeze evaluation dataset version before testing to avoid expectation drift.
5. Re-run 5-case suite and target >=80% strict-match.
