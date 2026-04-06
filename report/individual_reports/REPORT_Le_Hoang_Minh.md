# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Le Hoang Minh
- **Student ID**: 2A202600471
- **Date**: 2026-04-06
- **Github repo**: https://github.com/leduchai2002/Lab3_E403_Group5

---

## I. Technical Contribution (15 Points)

I focused on test-data construction, scenario-based execution, and log-based analysis that fed directly into the final comparative report.

- **Modules Implemented**:
  - `tests/test_agent.py`
  - `data/inventory.json`

- **Contribution Highlights**:
  - Built and expanded inventory mock data for phone-store scenarios (price lookup, budget recommendation, promotion, stock status, out-of-dataset query).
  - Implemented `tests/test_agent.py` to run the same 5 use cases consistently across phases (Single LLM, Agent v1, Agent v2).
  - Collected and compared per-case outputs, latency, tokens, and cost for model comparison in the group report.

- **Documentation of interaction with ReAct loop**:
  - The test runner sends structured prompts into `src/agent/agent.py`.
  - The agent generates `Thought -> Action`, calls inventory tools from `src/tools/inventory_tools.py`, receives `Observation`, then finalizes `Final Answer`.
  - This workflow is captured in runtime telemetry logs and summarized in the comparative report metrics table.

---

## II. Debugging Case Study (10 Points)

### Problem Description

The comparative run showed that completion status was high across all phases, but answer quality diverged by case and by policy constraints.

Main issues observed:
1. Promotion query still failed to retrieve active promotion information (Case 3).
2. Out-of-dataset query (Samsung S25 Ultra) was handled safely by Agent v2, but Agent v1 still injected external knowledge (Case 5).
3. Recommendation behavior differed between v1 and v2 (Case 2), where v1 produced a grounded recommendation while v2 returned a strict "not in stock" response.

### Evidence Source

- `2026-04-06.log`
- `tests/test_agent.py`
- `report/GROUP_REPORT_E403_GROUP5.md`

### Evidence from Trace

1. Case 2 (best iPhone under 10M):
- Agent v1 returned grounded recommendation: iPhone 13 128GB at 9,990,000 VND.
- Agent v2 returned "Sản phẩm không có trong kho." for the same request.

2. Case 3 (promotion lookup):
- All three phases failed to return active promotion details from inventory.

3. Case 5 (Samsung S25):
- Agent v2 returned strict fallback (not in stock), while Agent v1 and Single LLM added outside information.

4. Phase metrics (from final comparative table):
- Single LLM: 5 calls, 827 tokens, $0.0083, 6,742 ms.
- Agent v1: 9 calls, 3,328 tokens, $0.0333, 12,868 ms.
- Agent v2: 7 calls, 2,460 tokens, $0.0246, 8,367 ms.

### Diagnosis

Root causes are mainly in prompt-policy tradeoffs and retrieval normalization:

1. **Normalization gap (Case 3)**:
- Promotion retrieval is sensitive to lexical variation, causing missed matches.

2. **Policy vs flexibility tradeoff (Cases 2 and 5)**:
- Looser policy (v1) improves recommendation flexibility but risks external knowledge leakage.
- Stricter policy (v2) improves safety on unknown items but can over-reject borderline recommendation queries.

3. **Business-rule ambiguity**:
- The same retrieval pipeline is used for both recommendation and strict policy fallback, which needs clearer separation.

### Solution Implemented / Proposed

Implemented:
1. Created a repeatable 5-case test runner (`tests/test_agent.py`) for consistent comparison.
2. Prepared inventory data to support grounded price, stock, and recommendation checks.
3. Consolidated per-case findings into the final comparative/group report.

Proposed v2 fixes:
1. Add accent-insensitive normalization for promotion retrieval.
2. Separate recommendation intent from strict "not found" policy path.
3. Keep strict fallback only for truly out-of-dataset items.
4. Add regression assertions per case for groundedness and policy compliance.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**:
- ReAct provides traceable `Thought -> Action -> Observation` steps, making error analysis practical.
- Single LLM is simpler and faster but cannot ground answers in inventory data.

2. **Reliability**:
- Based on the final comparison, Single LLM produced 0/5 grounded answers, while Agent v1 and Agent v2 each produced 3/5 grounded answers.
- Agent v1 was stronger on recommendation quality (Case 2), while Agent v2 was stronger on safety for unknown products (Case 5).

3. **Observation feedback effect**:
- Observation quality directly controls final output quality.
- Retrieval mismatch in promotion queries shows that tool-grounded systems still depend on robust search normalization.

---

## IV. Future Improvements (5 Points)

- **Scalability**:
  - Split inventory features into domain tools (`search_products`, `search_promotions`, `check_stock`) and use typed outputs.

- **Safety**:
  - Keep strict unknown-item fallback for out-of-dataset queries, and prevent external speculation.

- **Performance**:
  - Reduce extra reasoning loops; current metrics already show v2 improves over v1 (calls, tokens, cost, latency).

---

## Appendix: Files Referenced

- `tests/test_agent.py`
- `src/agent/agent.py`
- `src/tools/inventory_tools.py`
- `data/inventory.json`
- `2026-04-06.log`
