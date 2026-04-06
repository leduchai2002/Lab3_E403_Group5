# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Le Hoang Minh
- **Student ID**: 2A202600471
- **Date**: 2026-04-06
- **Github repo**: https://github.com/leduchai2002/Lab3_E403_Group5

---

## I. Technical Contribution (15 Points)

I focused on test-data construction, scenario-based test execution, and failure diagnosis from telemetry logs.

- **Modules Implemented**:
  - `tests/test_agent.py`
  - `data/inventory.json`
  

- **Contribution Highlights**:
  - Create mock dataset based on the test scenario
  - Tạo file test_agent.py từ 5 test case, để ReAct agent đọc dataset và chỉ trả lời dựa trên thông tin của dataset

- **Documentation of interaction with ReAct loop**:
  - The test runner sends structured prompts into `src/agent/agent.py`.
  - The agent generates `Thought -> Action`, calls inventory tools from `src/tools/inventory_tools.py`, receives `Observation`, then finalizes `Final Answer`.
  - This workflow is captured in runtime telemetry logs used for debugging in `2026-04-06.log`.

---

## II. Debugging Case Study (10 Points)

### Problem Description

The ReAct agent v1 produced partially correct but inconsistent outputs for store-specific policies.

Main issues observed:
1. Promotion query returned no promotion although promotion records existed.
2. Out-of-dataset query (Samsung S25 Ultra) did not strictly follow fallback policy.
3. Output language/style drifted from expected fixed-format responses.

### Log Source

- `2026-04-06.log`
- `tests/test_agent.py`

### Evidence from Trace

1. Promotion case:
- Agent called `Action: search_inventory("khuyến mãi")`.
- Observation returned: no matching item.
- Then final answer said no active promotion.

2. Out-of-dataset case:
- Agent called inventory tool and correctly got no match.
- But final answer still included external speculation: "chua cong bo chinh thuc", instead of strict fallback phrase.

### Diagnosis

Root causes are mainly in prompt/tool-spec alignment and normalization:

1. **Query normalization gap**:
- Inventory promotions are written mostly in non-accented text (`Khuyen mai ...`), but model sometimes searches with accented text (`khuyến mãi`).
- Simple lowercase matching in search tool is not accent-insensitive, so false negatives occur.

2. **Policy guardrail gap**:
- ReAct system prompt does not strongly enforce strict fallback when item is missing in tool results.
- The model occasionally injects prior knowledge after receiving "not found" observation.

3. **Expectation-data mismatch**:
- Some expected outputs assume specific business states (for example, sold-out status or exact promotion wording), but current dataset may not exactly encode those assumptions.

### Solution Implemented / Proposed

Implemented:
1. Created explicit test prompts in `tests/test_agent.py` that force tool-first behavior and reduce free-form answering.
2. Built richer inventory data to cover the intended business scenarios.

Proposed v2 fixes:
1. Add accent-insensitive normalization in inventory search (Unicode normalization and diacritic removal).
2. Add strict fallback instruction in system prompt: if tool says not found, answer with policy template only.
3. Separate promotions into dedicated records/tool for deterministic retrieval.
4. Add assertion-based tests for exact expected wording when required by rubric.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**:
- The `Thought` block improves traceability because we can see why a tool was selected.
- In debugging, this is much better than a direct chatbot answer because each tool call is inspectable in logs.

2. **Reliability**:
- ReAct performs better for grounded tasks (price and stock lookup) because it uses `search_inventory`.
- ReAct can still be worse when guardrails are weak: it may over-generate external knowledge after a failed tool lookup.

3. **Observation feedback effect**:
- Observation strongly influences the next step. When observation is clean and matched to expected schema, answers are stable.
- When observation has lexical mismatch (accented vs non-accented query), the loop proceeds with incorrect assumptions and final answer quality drops.

---

## IV. Future Improvements (5 Points)

- **Scalability**:
  - Split inventory features into domain tools (`search_products`, `search_promotions`, `check_stock`) and move to typed outputs for easier parsing.

- **Safety**:
  - Enforce policy template for out-of-dataset answers, and block unsupported external speculation after "not found" observations.

- **Performance**:
  - Add lightweight cache for repeated inventory queries in the same session and reduce extra loops by early-final-answer conditions.

---

## Appendix: Files Referenced

- `tests/test_agent.py`
- `src/agent/agent.py`
- `src/tools/inventory_tools.py`
- `data/inventory.json`
- `2026-04-06.log`
