# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Huỳnh Khải Huy
- **Student ID**: 2A202600082
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

### Modules Implemented

| File | Vai trò |
|------|---------|
| `src/chatbot/chatbot.py` | Implement `BaselineChatbot`: vòng lặp turn-based, quản lý history, tích hợp telemetry |
| `src/chatbot/runner.py` | Provider factory `build_provider()` + interactive CLI loop `run_chat_loop()` |
| `main.py` | Unified CLI launcher: argparse `--mode chatbot/agent`, interactive menu, EOFError handling |
| `app.py` | Streamlit UI hỗ trợ cả Chatbot và ReAct Agent trên cùng một giao diện |
| `src/telemetry/logger.py` | Fix encoding: `FileHandler(encoding="utf-8")` + reopen StreamHandler stream UTF-8 |

### Code Highlights

**1. BaselineChatbot turn loop — `src/chatbot/chatbot.py:chat()`**

```python
def chat(self, user_message: str) -> str:
    # 1. Record the user turn.
    self.history.append({"role": "user", "content": user_message})
    logger.log_event("CHATBOT_USER", {"turn": len(self.history), "message": user_message})

    # 2. Serialize full history into a single prompt string.
    prompt = self._build_prompt()

    # 3. Call LLM (non-streaming).
    response = self.llm.generate(prompt=prompt, system_prompt=self.system_prompt)

    # 4. Extract reply and push metrics.
    reply = response.get("content", "").strip()
    tracker.track_request(
        provider=response.get("provider", type(self.llm).__name__),
        model=self.llm.model_name,
        usage=response.get("usage", {}),
        latency_ms=response.get("latency_ms", 0),
    )
    # 5. Append assistant turn, return reply.
    self.history.append({"role": "assistant", "content": reply})
    return reply
```

Điểm quan trọng: toàn bộ `self.history` được re-serialize mỗi turn để model có context đầy đủ. Đây cũng là nhược điểm chính của Chatbot — token tăng tuyến tính theo chiều dài hội thoại, không có memory summarisation.

**2. Provider factory — `src/chatbot/runner.py:build_provider()`**

```python
def build_provider(provider_name: str) -> LLMProvider:
    provider_name = provider_name.lower().strip()
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in your .env file.")
        return OpenAIProvider(model_name=os.getenv("DEFAULT_MODEL", "gpt-4o"), api_key=api_key)
    elif provider_name in ("google", "gemini"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in your .env file.")
        return GeminiProvider(model_name=os.getenv("DEFAULT_MODEL", "gemini-1.5-flash"), api_key=api_key)
    elif provider_name == "local":
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Local model not found at '{model_path}'.")
        return LocalProvider(model_path=model_path)
    else:
        raise ValueError(f"Unknown provider '{provider_name}'. Choose from: openai | google | local")
```

Factory pattern cho phép thay đổi provider hoàn toàn qua biến môi trường `DEFAULT_PROVIDER` mà không thay đổi code. Agent và Chatbot đều gọi cùng interface `LLMProvider.generate()`.

**3. EOFError handling trong CLI — `main.py`**

```python
try:
    choice = input("Select option [1/2/q]: ").strip().lower()
except EOFError:
    # stdin không có TTY (e.g. conda run trong CI/non-interactive)
    print("[INFO] No interactive input available.\n"
          "To run directly, use:\n"
          "  conda run -n ve01 python main.py --mode chatbot\n"
          "  conda run -n ve01 python main.py --mode agent\n")
    sys.exit(0)   # exit 0 để conda run không báo lỗi
```

Khi `conda run` không có TTY, `input()` raise `EOFError`. Phiên bản gốc gọi `sys.exit(1)` khiến `conda run` báo failure dù chương trình chạy đúng. Đổi sang `sys.exit(0)` là cần thiết.

**4. Streamlit UI — `app.py`**

```python
# Lazy-init agent, capture stdout để hiển thị reasoning steps
captured = io.StringIO()
sys.stdout = captured
try:
    reply = st.session_state.agent.run(prompt)
finally:
    sys.stdout = sys.__stdout__

steps = captured.getvalue()
st.write(reply)
if steps.strip():
    with st.expander("🔍 Agent reasoning steps", expanded=True):
        st.code(steps, language="text")
```

UI redirect `sys.stdout` để bắt log intermediate từ `_execute_tool()` (vốn in ra console) và hiển thị trong expander "Agent reasoning steps". Không cần sửa agent code.

### Cách code tương tác với kiến trúc tổng thể

```
app.py / main.py
    │
    ├── build_provider(name)
    │       └── OpenAIProvider / GeminiProvider / LocalProvider
    │                └── .generate(prompt, system_prompt) → {content, usage, latency_ms}
    │
    ├── BaselineChatbot.chat(user_input)
    │       ├── _build_prompt()    ← serialize full history
    │       ├── llm.generate(...)
    │       └── tracker.track_request(...)
    │
    └── ReActAgent.run(user_input)   ← (implemented by Đặng Anh Quân)
            └── llm.generate(...)   ← same LLMProvider interface
```

---

## II. Debugging Case Study (10 Points)

### Bug: `UnicodeEncodeError` khi log tiếng Việt trên Windows

**Mô tả**: Khi chạy chatbot chế độ CLI (`python main.py`) và nhập tiếng Việt có dấu (ví dụ "Chào bạn"), chương trình in ra `--- Logging error ---` và crash với traceback, dù response vẫn được hiển thị.

**Log thực tế** (`logs/2026-04-06.log`):

```
--- Logging error ---
Traceback (most recent call last):
  File "<conda>\Lib\logging\__init__.py", line 1163, in emit
    stream.write(msg + self.terminator)
  File "<conda>\Lib\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'charmap' codec can't encode character '\u1ea1' in position 107: character maps to <undefined>
Call stack:
  ...
Message: '{"event": "CHATBOT_USER", "data": {"message": "Chào bạn"}}'
```

Lỗi chỉ xảy ra khi message chứa ký tự ngoài ASCII (tiếng Việt, tiếng Nhật...) chứ không tái hiện khi nhập tiếng Anh.

**Chẩn đoán**:

Trong `src/telemetry/logger.py`, `IndustryLogger.__init__()` tạo handler mà không chỉ định encoding:

```python
# TRƯỚC — mặc định dùng encoding của hệ điều hành
file_handler = logging.FileHandler(log_file)         # Windows → cp1252
console_handler = logging.StreamHandler()             # Windows stdout → cp1252
```

`log_event()` gọi `json.dumps(payload, ensure_ascii=False)` để giữ nguyên Unicode (đúng). Nhưng cả hai handler đều dùng encoding `cp1252` của Windows, không hỗ trợ ký tự UTF-8 ngoài Latin-1. Khi `StreamHandler.emit()` cố ghi `"ạ"` (`\u1ea1`) vào stream cp1252 → `UnicodeEncodeError`.

Vấn đề là logger hoạt động đúng khi test bằng tiếng Anh nên không bị phát hiện sớm. Chỉ khi user thực sự nhập tiếng Việt mới lộ.

**Fix** (`src/telemetry/logger.py`):

```python
# SAU — ép cả hai handler dùng utf-8
file_handler = logging.FileHandler(log_file, encoding="utf-8")

console_handler = logging.StreamHandler()
console_handler.stream = open(
    console_handler.stream.fileno(), mode="w", encoding="utf-8", closefd=False
)
```

`FileHandler` hỗ trợ kwarg `encoding` trực tiếp. `StreamHandler` không có kwarg đó nên cần reopen underlying file descriptor với `encoding="utf-8"` và `closefd=False` (để không đóng fd gốc của stdout).

**Bài học**: Khi dùng `ensure_ascii=False` trong JSON serialization, handler phải tương ứng dùng UTF-8. Thiết lập encoding mặc định là không an toàn trên Windows vì cp1252 rất hạn chế so với UTF-8. Nên cấu hình encoding tường minh cho mọi handler ngay khi khởi tạo logger.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning: `Thought` block giúp gì?

Chatbot gửi toàn bộ history lên LLM trong một prompt duy nhất và nhận reply trong một lần. Khi được hỏi "Giá iPhone 15 bao nhiêu?", Chatbot không có cơ chế nào để tra cứu — nó chỉ có thể thừa nhận giới hạn hoặc hallucinate từ training data:

> *"Xin lỗi, tôi không thể truy cập kho hàng..."* (Case 1 — Single LLM)

Block `Thought` trong ReAct buộc model **externalise** reasoning trước khi hành động. Điều này tạo hai lợi ích:
- **Traceability**: Log ghi lại `Thought` → `Action` → `Observation` từng bước, dễ debug khi agent sai.
- **Grounding**: Model không thể trả lời ngay bằng training data — phải gọi tool trước, observation từ tool gắn kết câu trả lời vào dữ liệu thực.

### 2. Reliability: Khi nào Agent tệ hơn Chatbot?

Từ comparative report, **Case 5 (Samsung S25 Ultra)** là ví dụ rõ nhất:

| Phase | Câu trả lời | Đánh giá |
|-------|-------------|----------|
| Chatbot | "Samsung Galaxy S25 Ultra chưa được công bố chính thức..." | Chính xác về giới hạn kiến thức |
| Agent v1 | "...giá thường rơi vào khoảng 1,000–1,500 USD" | **Hallucinate** dù tool báo không có |
| Agent v2 | "Sản phẩm không có trong kho" | Đúng nhờ rule cứng trong prompt v2 |

Agent v1 tệ hơn Chatbot vì: sau khi nhận Observation "không tìm thấy", prompt v1 không cấm model dùng training data để "bù đắp". Model nghĩ mình đang giúp ích nên tự thêm số liệu ngoài dataset.

Ngoài ra, **Case 2 (Agent v2)** trả lời "Sản phẩm không có trong kho" khi user hỏi iPhone tốt nhất trong 10 triệu — sai hoàn toàn dù kho có iPhone 13 với giá 9,990,000 VND. Prompt v2 quá conservative, cắt bỏ cả trường hợp có dữ liệu.

### 3. Observation: Feedback từ môi trường ảnh hưởng thế nào?

Observation đóng vai trò **grounding anchor** — mỗi kết quả tool call được nối thêm vào prompt, thu hẹp không gian mà model có thể trả lời. Đây là điểm mạnh cốt lõi của ReAct so với Chatbot thuần túy.

Tuy nhiên, từ Case 3 (khuyến mãi), tôi quan sát thấy: Observation sai input dẫn thẳng đến kết luận sai, và agent **không tự retry**. Tool nhận query `"khuyến mãi"` (có dấu) nhưng data lưu `"Khuyen mai"` (không dấu) → không match → agent kết luận "cửa hàng không có khuyến mãi". Vấn đề không phải là reasoning logic sai mà là tool không normalize đúng trước khi so sánh. Đây giải thích tại sao data layer và tool layer phải đáng tin cậy trước khi chạy agent — garbage in, garbage out.

---

## IV. Future Improvements (5 Points)

### Scalability — Streaming responses trong UI

Hiện tại `app.py` gọi `chatbot.chat()` và `agent.run()` trong một lần rồi mới hiển thị kết quả. Với agent nhiều bước, user phải chờ toàn bộ loop kết thúc. Cải tiến: implement `stream_chat()` từ `BaselineChatbot` vào UI bằng `st.write_stream()` của Streamlit để token xuất hiện ngay khi model generate.

Với Agent, có thể push từng `Thought/Action/Observation` step vào một `st.empty()` container trong khi loop chạy, thay vì buffer toàn bộ stdout sau đó mới render — giúp UX tốt hơn với max_steps lớn.

### Safety — Input validation trước khi gọi tool

`_execute_tool()` hiện truyền `args` thẳng vào `func(args)` mà không validate. Trong môi trường production, user có thể craft prompt injection để agent gọi `update_inventory` hoặc `delete_inventory` với args tùy ý. Cần thêm:
1. Schema validation cho từng tool (ví dụ: id phải match `P\d+`, price phải là số dương).
2. Confirmation step cho các destructive tools (`update`, `delete`) trước khi execute.
3. Rate limiting per session để tránh agent loop gọi tool liên tục khi stuck.

### Performance — Provider fallback và caching

Hiện tại nếu OpenAI API down, toàn bộ chatbot/agent không hoạt động. Cải tiến: implement provider fallback chain — nếu `OpenAIProvider.generate()` raise exception, tự động retry với `GeminiProvider`. `build_provider()` có thể nhận list ưu tiên thay vì một tên duy nhất.

Với các query lặp lại (cùng user_input, cùng inventory snapshot), có thể cache `search_inventory` kết quả bằng `functools.lru_cache` hoặc một simple dict cache có TTL — giảm LLM calls trung bình từ 1.8 xuống gần 1 cho các truy vấn phổ biến.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
