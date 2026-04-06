# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Đặng Anh Quân
- **Student ID**: SE173035
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

### Modules Implemented

| File | Vai trò |
|------|---------|
| `src/agent/agent.py` | Implement ReAct loop, fix bug `tool_args`, tích hợp metrics |
| `src/agent/prompts.py` | Hệ thống versioned prompt (v1/v2) |
| `src/tools/inventory_tools.py` | 3 tools: `search_inventory`, `update_inventory`, `delete_inventory` |
| `src/tools/inventory_tools_v2.py` | Mở rộng v1 với `list_all_inventory` |
| `src/telemetry/logger.py` | Fix encoding tiếng Việt (`ensure_ascii=False`) |
| `src/telemetry/metrics.py` | Wire `tracker.track_request()` vào agent loop |
| `tests/test_agent.py` | 3-phase comparative test runner, tự động sinh report |

### Code Highlights

**1. ReAct loop — `src/agent/agent.py:run()`**

```python
while steps < self.max_steps:
    result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
    response_text = result["content"]
    tracker.track_request(...)  # metrics per LLM call

    final_match = re.search(r"Final Answer:\s*(.*)", response_text, re.DOTALL)
    if final_match:
        return final_match.group(1).strip()

    action_match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", response_text)
    if action_match:
        tool_name = action_match.group(1).strip()
        tool_args = action_match.group(2).strip().strip('"\'')
        observation = self._execute_tool(tool_name, tool_args)
        current_prompt = f"{current_prompt}\n{response_text}\nObservation: {observation}"
```

Điểm đáng chú ý: regex đổi từ `(.*?)` sang `([^)]*)` để tránh bị cắt sai khi args có ký tự đặc biệt. Args được strip dấu nháy trước khi truyền vào tool vì LLM hay sinh `Action: search_inventory("iPhone 15")` thay vì `search_inventory(iPhone 15)`.

**2. Versioned prompt — `src/agent/prompts.py`**

```python
_REGISTRY = {"v1": _V1, "v2": _V2}

def get_system_prompt(version: str, tool_descriptions: str) -> str:
    template = _REGISTRY.get(version)
    if template is None:
        raise ValueError(f"Unknown prompt version '{version}'.")
    return template.format(tool_descriptions=tool_descriptions)
```

Thiết kế registry cho phép thêm v3, v4 mà không chạm vào `agent.py`. Prompt v2 bổ sung 3 rule cứng chống hallucination.

**3. Unicode normalization — `src/tools/inventory_tools.py`**

```python
def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().strip()

def search_inventory(query: str) -> str:
    query = _normalize(query.strip('"\''))
    matches = [item for item in items if query in _normalize(item["name"])]
```

Chuẩn hóa cả query lẫn tên sản phẩm về NFC trước khi so sánh.

### Cách code tương tác với ReAct loop

```
user_input
    │
    ▼
agent.run()
    │── llm.generate(prompt, system_prompt=get_system_prompt(version))
    │        └── tracker.track_request(usage, latency)   ← metrics
    │
    ├── parse "Final Answer:" → return
    │
    └── parse "Action: tool(args)"
             └── _execute_tool(tool_name, args)
                      └── tool['func'](args)              ← inventory tools
                               └── logger.log_event(TOOL_RESULT)
```

---

## II. Debugging Case Study (10 Points)

### Bug: `NameError: name 'tool_args' is not defined`

**Mô tả**: Sau khi implement xong ReAct loop, mọi tool call đều thất bại dù agent parse được đúng Action.

**Log thực tế** (`logs/2026-04-06.log`):

```json
{"timestamp": "2026-04-06T08:52:58.084249", "event": "TOOL_CALL",
 "data": {"tool": "search_inventory", "args": "chuột logitech",
          "result": "Error calling search_inventory: name 'tool_args' is not defined"}}

{"timestamp": "2026-04-06T08:52:58.778736", "event": "TOOL_CALL",
 "data": {"tool": "search_inventory", "args": "\"chuột logitech\"",
          "result": "Error calling search_inventory: name 'tool_args' is not defined"}}
```

Agent thử lại 2 lần rồi trả về lỗi. LLM nhìn thấy Observation lỗi nên tự bịa câu trả lời.

**Chẩn đoán**: Trong `_execute_tool(self, tool_name: str, args: str)`, khi gọi `func(tool_args)` đã dùng nhầm tên biến `tool_args` (không tồn tại) thay vì tham số `args`. Python raise `NameError` ngay tại runtime, không bị bắt tại compile time.

```python
# BUG
def _execute_tool(self, tool_name: str, args: str) -> str:
    ...
    return str(func(tool_args))   # ← tool_args không được định nghĩa ở đây
```

**Fix**:

```python
# FIX
result = str(func(args))          # ← đúng tên tham số
```

**Bài học**: Lỗi này không bị IDE bắt vì `tool_args` có thể là biến global ở nơi khác. Việc có structured log `TOOL_CALL` với field `result` là yếu tố then chốt để phát hiện — nếu chỉ print ra console hoặc log ở mức INFO chung thì rất khó trace.

---

### Bug thứ 2: Tiếng Việt bị parse sai do Unicode normalization

**Mô tả**: `search_inventory("chuột")` không tìm thấy gì dù kho có sản phẩm tên "Chuột Logitech".

**Log**:

```json
{"event": "TOOL_RESULT", "data": {"tool": "search_inventory",
 "result": "Không tìm thấy sản phẩm nào khớp với '\"\"'."}}
```

**Chẩn đoán**: Hai nguyên nhân:
1. LLM sinh `search_inventory("")` với dấu nháy → query trở thành literal `'""'` thay vì empty string.
2. Tiếng Việt có thể encode theo NFD (decomposed) từ LLM hoặc NFC (composed) từ JSON file — `in` operator trong Python so sánh byte-by-byte nên `"ộ"` NFD ≠ `"ộ"` NFC.

**Fix**: Normalize cả hai về NFC và strip dấu nháy:

```python
def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().strip()

query = _normalize(query.strip('"\''))
matches = [item for item in items if query in _normalize(item["name"])]
```

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning: `Thought` block giúp gì?

Block `Thought` buộc model phải "externalize" chain-of-thought trước khi hành động thay vì trả lời trực tiếp. Điều này tạo ra một **checkpoint có thể quan sát được** — trong log thấy rõ model đang nghĩ gì trước khi gọi tool. Với Chatbot, toàn bộ reasoning diễn ra ẩn bên trong forward pass và không thể can thiệp.

Thực tế từ Case 1: Chatbot trả lời "tôi không thể truy cập kho hàng" — đúng về khả năng nhưng vô ích với user. Agent v1 sinh ra:
```
Thought: Cần tìm giá iPhone 15 trong kho.
Action: search_inventory(iPhone 15)
Observation: [IP004] iPhone 15 128GB | Giá: 18,990,000 VND | Tồn kho: 9
Final Answer: Giá của chiếc iPhone 15 128GB là 18,990,000 VND.
```

### 2. Reliability: Khi nào Agent tệ hơn Chatbot?

**Case 5 (Samsung S25 Ultra)** là ví dụ điển hình cho agent v1 tệ hơn chatbot:

| Phase | Answer |
|-------|--------|
| Single LLM | "Samsung Galaxy S25 Ultra chưa được công bố chính thức" — trả lời đúng giới hạn kiến thức |
| Agent v1 | "giá thường rơi vào khoảng 1,000–1,500 USD" — **hallucinate số liệu** dù tool đã báo không có |

Agent v1 tệ hơn vì: sau khi nhận `Observation: Không tìm thấy`, prompt v1 không cấm model dùng kiến thức ngoài, nên model tự "bù" bằng training data và đưa ra số liệu sai.

**Case 3 (khuyến mãi)**: Agent v1 tìm `"khuyen mai"` (không dấu) trong database lưu `"Khuyen mai"` (không dấu) → match được. Nhưng nếu user hỏi bằng tiếng Việt có dấu mà tool chưa normalize hoàn toàn, agent thất bại trong khi chatbot có thể trả lời chung chung.

### 3. Observation: Feedback từ môi trường ảnh hưởng thế nào?

Observation đóng vai trò **grounding signal** — kéo agent về thực tế sau mỗi bước. Khi `search_inventory` trả về danh sách thực từ JSON, model không thể tiếp tục hallucinate vì context window đã chứa dữ liệu cụ thể.

Tuy nhiên, quan sát từ Case 3: agent v1 nhận Observation `"Không tìm thấy sản phẩm nào khớp với 'khuyen mai'"` và kết luận sai "cửa hàng không có chương trình giảm giá". Model không thử lại với từ khóa khác. Đây là điểm yếu của single-pass ReAct: **observation sai input → kết luận sai**, không có retry logic.

---

## IV. Future Improvements (5 Points)

### Scalability

Hiện tại agent xử lý tuần tự từng tool call. Trong kịch bản multi-tool (vừa search inventory vừa check price history vừa fetch promotion API), các tool call độc lập nhau có thể **chạy song song** bằng `asyncio.gather()`. Agent cần được refactor sang async loop với timeout per tool call.

### Safety

Prompt v2 dùng rule cứng nhưng vẫn dựa vào model tự tuân thủ. Một hướng robust hơn là thêm **Guardrail layer** sau `_execute_tool`: nếu answer cuối cùng chứa thông tin ngoài tập `{tên sản phẩm, giá, stock}` từ kết quả tool, một LLM phụ (hoặc regex rule) có thể flag để human review trước khi trả về user.

### Performance

Với kho hàng lớn (>10,000 sản phẩm), `search_inventory` hiện đọc toàn bộ JSON rồi filter in-memory — O(n) mỗi call. Production cần:
1. **Vector DB** (e.g. ChromaDB) để semantic search thay vì substring match — giải quyết luôn vấn đề "khuyen mai" vs "Khuyến mãi".
2. **Tool retrieval**: Khi có >20 tools, thay vì list tất cả trong system prompt, dùng embedding để chỉ inject top-k tools liên quan vào context — giảm token input đáng kể.

---

> **Source**: Toàn bộ số liệu trong report được lấy từ `logs/2026-04-06.log` và `report/comparative_report_20260406_172235.md` sinh ra từ test runner thực tế.
