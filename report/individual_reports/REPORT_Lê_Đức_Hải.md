# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Lê Đức Hải
- **Student ID**: 2A202600470
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

| File | Vai trò |
|------|---------|
| `src/telemetry/logger.py` | Fix encoding tiếng Việt (`ensure_ascii=False`) |
| `src/telemetry/metrics.py` | Wire `tracker.track_request()` vào agent loop |
| `tests/test_agent.py` | 3-phase comparative test runner, tự động sinh report |

### Code Highlights
**1. Fix encoding tiếng Việt — `src/telemetry/logger.py`**

```python
 def __init__(self, name: str = "AI-Lab-Agent", log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # File Handler (JSON) — utf-8 to support all Unicode characters
        log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")

        # Console Handler — utf-8 to avoid cp1252 UnicodeEncodeError on Windows
        console_handler = logging.StreamHandler()
        console_handler.stream = open(
            console_handler.stream.fileno(), mode="w", encoding="utf-8", closefd=False
        )
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
```
Điểm đáng chú ý: Cấu hình logger chuẩn production: log ra file theo ngày và console cùng lúc, hỗ trợ Unicode/UTF‑8 đầy đủ, đặc biệt fix lỗi UnicodeEncodeError.
**2. Wire `tracker.track_request()` vào agent loop — `src/telemetry/metrics.py`**
```python
def __init__(self):
        self.session_metrics = []

    def track_request(self, provider: str, model: str, usage: Dict[str, int], latency_ms: int):
        """
        Logs a single request metric to our telemetry.
        """
        metric = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "cost_estimate": self._calculate_cost(model, usage) # Mock cost calculation
        }
        self.session_metrics.append(metric)
        logger.log_event("LLM_METRIC", metric)

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        TODO: Implement real pricing logic.
        For now, returns a dummy constant.
        """
        return (usage.get("total_tokens", 0) / 1000) * 0.01
```
Điểm đáng chú ý: Thu thập telemetry cho mỗi request LLM: `provider`, `model`, `token usage`, `latency`, `cost`, lưu metric theo session (in‑memory) và emit event qua logger.log_event, tính chi phí giả lập dựa trên total tokens (TODO: thay bằng pricing thật).

---
### Cách code tương tác với ReAct loop
    Nhận input → Reason / Plan → Gọi LLM → Nhận output → Act → Lặp lại
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

Việc sử dụng block Thought khiến mô hình tách riêng quá trình suy luận ra bên ngoài trước khi thực hiện hành động, thay vì đi thẳng đến câu trả lời cuối cùng. Cách tiếp cận này tạo ra một điểm kiểm soát có thể quan sát và phân tích được, giúp theo dõi rõ trong log mô hình đang lập luận như thế nào trước khi gọi tool. Ngược lại, với Chatbot thuần, toàn bộ quá trình reasoning diễn ra hoàn toàn ẩn bên trong quá trình suy luận nội tại của model, không thể quan sát, ghi vết hay can thiệp khi cần.

### 2. Reliability: Khi nào Agent tệ hơn Chatbot?

**Case 5 (Samsung S25 Ultra)** là minh chứng rõ ràng cho việc Agent v1 có thể cho kết quả kém hơn Chatbot thuần trong một số tình huống:

| Phase | Answer |
|-------|--------|
| Single LLM | "Samsung Galaxy S25 Ultra chưa được công bố chính thức" — trả lời đúng trong phạm vi kiến thức, không suy đoán thêm |
| Agent v1 | "giá thường rơi vào khoảng 1,000–1,500 USD" — **hallucinate số liệu** dù tool đã trả về không có kết quả |

Nguyên nhân khiến Agent v1 thất bại nằm ở thiết kế prompt. Sau khi nhận được
- Observation: Không tìm thấy, prompt v1 không có ràng buộc cứng buộc model phải dừng lại hoặc trả về trạng thái “không có dữ liệu”. Do đó, model tự động bù thông tin bằng kiến thức học được trong training data, dẫn đến việc suy đoán giá và tạo ra số liệu không được grounding.
- Trong khi đó, Chatbot thuần dù không có khả năng truy xuất kho, lại vô tình “an toàn hơn” ở case này vì chỉ trả lời trong giới hạn kiến thức chung, không cố gắng suy luận hay bịa thêm dữ liệu khi thiếu nguồn xác thực.

### 3. Observation: Feedback từ môi trường ảnh hưởng thế nào?

    Observation đóng vai trò như một tín hiệu grounding bắt buộc, giúp kéo agent quay về dữ liệu thực sau mỗi bước suy luận. Khi `search_inventory` trả về danh sách cụ thể từ file JSON, thông tin này được đưa trực tiếp vào context window, qua đó giới hạn không gian suy luận của model và ngăn việc tiếp tục hallucinate dựa trên kiến thức huấn luyện chung.
---

## IV. Future Improvements (5 Points)

### Scalability

- Hiện tại agent thực thi các tool theo chuỗi tuần tự, dẫn đến độ trễ cao trong kịch bản multi-tool.
- Với các tool độc lập (search inventory, price history, promotion API), các lời gọi này có thể chạy song song để tối ưu latency.
Giải pháp là refactor agent sang async ReAct loop, sử dụng asyncio.gather() cho mỗi bước action.
- Mỗi tool call cần gắn timeout riêng để tránh block toàn bộ vòng lặp.

**Thiết kế này giúp cải thiện hiệu năng và sẵn sàng cho môi trường production.**

### Safety

Prompt v2 áp dụng rule cứng, nhưng việc tuân thủ vẫn phụ thuộc vào hành vi của model. Một hướng tiếp cận robust hơn là bổ sung **Guardrail layer** sau bước `_execute_tool`. Nếu câu trả lời cuối cùng chứa thông tin ngoài phạm vi dữ liệu tool trả về (chỉ gồm `{tên sản phẩm, giá, stock}`), hệ thống có thể dùng một LLM phụ hoặc rule-based (regex) để phát hiện và chặn. Các trường hợp bị flag sẽ được chuyển sang human review trước khi trả kết quả cho người dùng. Cách này giúp giảm rủi ro hallucination ở tầng hệ thống, không chỉ dựa vào prompt.
### Performance

- Với kho hàng lớn (>10.000 sản phẩm), việc filter JSON in-memory gây chi phí O(n) cho mỗi truy vấn.
- Cần dùng Vector DB (như ChromaDB) để semantic search, đồng thời xử lý tốt vấn đề chuẩn hóa từ khóa (khuyen mai vs khuyến mãi).
- Khi số tool tăng (>20), nên áp dụng tool retrieval dựa trên embedding để chỉ inject top‑k tool liên quan vào context.
**Cách này giúp giảm token input, latency và chi phí trong môi trường production.**

---

> **Source**: Toàn bộ số liệu trong report được lấy từ `logs/2026-04-06.log` và `report/comparative_report_20260406_172235.md` sinh ra từ test runner thực tế.
