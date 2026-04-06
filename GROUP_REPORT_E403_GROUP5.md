# Báo Cáo So Sánh — LLM Đơn Lẻ vs Agent v1 vs Agent v2

- **Date**: 2026-04-06 17:22:35
- **Provider**: OpenAIProvider  |  **Model**: gpt-4o
- **Total use cases**: 5
- **Team Name**: E403 Group 5
- **Team Members**: Lê Hoàng Minh, Đặng Anh Quân, Lê Đức Hải, Huỳnh Khải Huy
- **Deployment Date**: 2026-04-06

---

## 1. Tóm tắt báo cáo

Dự án này triển khai một ReAct Inventory Assistant cho các truy vấn cửa hàng điện thoại, sử dụng tool truy xuất kho hàng nội bộ và hệ thống telemetry logs có cấu trúc. Chúng tôi đánh giá hệ thống qua 5 kịch bản định sẵn (tra cứu giá, tư vấn theo ngân sách, khuyến mãi, kiểm tra tồn kho và xử lý câu hỏi ngoài dữ liệu).

- **Case 1 (iPhone 15 price)**: Agent v1 và Agent v2 đều trả về đúng giá trong kho; Single LLM không thể truy cập dữ liệu cửa hàng.
- **Case 2 (best iPhone under 10M)**: Agent v1 đưa ra gợi ý có căn cứ dữ liệu (iPhone 13 128GB, 9,990,000 VNĐ);Agent v2 trả về “không có trong kho”;Single LLM gave generic advice.
- **Case 3 (Truy vấn khuyến mãi)**: Cả ba đều thất bại trong việc liệt kê khuyến mãi đang hoạt động (do mismatch từ khóa / chuẩn hóa dữ liệu).
- **Case 4 (iPhone 14 stock)**: Agent v1 và Agent v2 đều trả lời dựa trên dữ liệu kho; Single LLM trả lời chung chung, không có căn cứ dữ liệu.
- **Case 5 (Samsung S25 outside dataset)**: Agent v2 thực hiện fallback an toàn (báo không có trong kho); Agent v1 và Single LLM bổ sung kiến thức ngoài dữ liệu huấn luyện.
- **Tổng kết chất lượng theo mô hình**: Single LLM = 0/5 câu trả lời có căn cứ dữ liệu; Agent v1 = 3/5; Agent v2 = 3/5.
- **Kết luận chính**: Agent v1 mạnh hơn trong các bài toán tư vấn / recommendation (Case 2), Agent v2 mạnh hơn trong xử lý an toàn dữ liệu ngoài phạm vi (Case 5). Theo Phase Metrics, Agent v2 hiệu quả hơn Agent v1
(giảm 22.2% số lần gọi, 26.1% token/chi phí, 35.0% độ trễ).

---

## 2. Kiến Trúc Hệ Thống & Công Cụ

### 2.1 Triển Khai Vòng Lặp ReAct

Agent tuân theo vòng lặp:
1. Sinh `Thought` + `Action`
2. Parse hành động từ output LLM (`Action: tool_name(args)`)
3. Thực thi tool và thêm `Observation`
4. Lặp lại cho đến khi có `Final Answer` hoặc đạt giới hạn bước

Chi tiết triển khai:
- File: `src/agent/agent.py`
- Giới hạn vòng lặp: `max_steps=5`
- Telemetry: Log sự kiện tại mỗi bước LLM và mỗi lần gọi tool

### 2.2 Tool Definitions (Inventory)

| Tên tool | Định dạng input | Mục đích |
| :--- | :--- | :--- |
| `search_inventory` | `string` | Tìm sản phẩm / khuyến mãi theo từ khóa trong `data/inventory.json` |
| `update_inventory` | `"<id>, price=<value>, stock=<value>"` | Cập nhật giá và tồn kho |
| `delete_inventory` | `"<id>"` | Xóa sản phẩm theo id |

### 2.3 LLM Providers Used

- **Primary**: OpenAI `gpt-4o`
- **Secondary (Backup)**: Provider Gemini (có trong codebase, không dùng trong lần chạy này)

---

## Phase Metrics Summary

| Metric | Single LLM | Agent v1 | Agent v2 |
|--------|-----------|---------|---------|
| LLM calls | 5 | 9 | 7 |
| Total tokens | 827 | 3,328 | 2,460 |
| Estimated cost | $0.0083 | $0.0333 | $0.0246 |
| Total LLM latency | 6,742 ms | 12,868 ms | 8,367 ms |
| Errors | 0 | 0 | 0 |

---

## Per-Case Results

| # | Case | Single LLM | Agent v1 | Agent v2 |
|---|------|-----------|---------|---------|
| 1 | Gia iPhone 15 | COMPLETED (1569 ms) | COMPLETED (2086 ms) | COMPLETED (2001 ms) |
| 2 | iPhone tot nhat trong 10 trieu | COMPLETED (1338 ms) | COMPLETED (3110 ms) | COMPLETED (1554 ms) |
| 3 | Chuong trinh khuyen mai | COMPLETED (1045 ms) | COMPLETED (1534 ms) | COMPLETED (1618 ms) |
| 4 | Ton kho iPhone 14 | COMPLETED (1465 ms) | COMPLETED (3577 ms) | COMPLETED (1525 ms) |
| 5 | San pham ngoai du lieu (Samsung S25) | COMPLETED (1327 ms) | COMPLETED (2578 ms) | COMPLETED (1678 ms) |

---

## Case-by-Case Comparison

### Case 1 — Gia iPhone 15

> **Prompt:** Gia cua chiec Iphone 15 la bao nhieu ? Hay su dung du lieu cua kho hang va uu tien goi tool search_inventory de tra loi.
> **Expected:** Tra ve gia chinh xac cua iPhone 15 tu du lieu kho.

| Phase | Answer | Duration |
|-------|--------|----------|
| Single LLM | Xin lỗi, nhưng tôi không thể truy cập kho hàng hoặc sử dụng các công cụ tìm kiếm bên ngoài để kiểm tra giá cả hiện tại của iPhone 15. Để biết thông tin giá chính xác nhất, bạn nên kiểm tra trang web chính thức của Apple hoặc các nhà bán lẻ uy tín tại địa phương. | 1569 ms |
| Agent v1   | Giá của chiếc iPhone 15 128GB là 18,990,000 VND. | 2086 ms |
| Agent v2   | Giá của chiếc iPhone 15 128GB là 18,990,000 VND. | 2001 ms |

---

### Case 2 — iPhone tot nhat trong 10 trieu

> **Prompt:** Toi co 10 trieu dong, lieu toi co the mua duoc mot chiec iphone tot nhat trong tam gia khong? Hay dua tren du lieu ton kho va gia trong kho, nho goi tool search_inventory.
> **Expected:** Goi y iPhone phu hop nhat trong tam gia 10 trieu dua tren du lieu thuc te.

| Phase | Answer | Duration |
|-------|--------|----------|
| Single LLM | Xin lỗi, tôi không thể gọi công cụ hoặc truy cập dữ liệu thời gian thực, bao gồm thông tin tồn kho hoặc giá cả hiện tại. Tuy nhiên, với 10 triệu đồng, bạn có thể xem xét các mẫu iPhone đã qua sử dụng hoặc các phiên bản cũ hơn như iPhone SE (2020) hoặc iPhone 8. Giá cả có thể thay đổi tùy thuộc vào tình trạng và nơi bán. Để có thông tin chính xác nhất, bạn nên kiểm tra trực tiếp tại các cửa hàng bán lẻ hoặc các trang web thương mại điện tử uy tín. | 1338 ms |
| Agent v1   | Với 10 triệu đồng, bạn có thể mua iPhone 13 128GB với giá 9,990,000 VND, đây là lựa chọn tốt nhất trong tầm giá của bạn dựa trên dữ liệu tồn kho hiện tại. | 3110 ms |
| Agent v2   | Sản phẩm không có trong kho. | 1554 ms |

---

### Case 3 — Chuong trinh khuyen mai

> **Prompt:** Cua hang hien tai co chuong trinh giam gia nao khong? Hay tim trong du lieu kho bang tool search_inventory voi tu khoa khuyen mai.
> **Expected:** Liet ke cac chuong trinh khuyen mai dang co trong kho.

| Phase | Answer | Duration |
|-------|--------|----------|
| Single LLM | Xin lỗi, tôi không thể tìm kiếm dữ liệu trong cơ sở dữ liệu nội bộ hoặc các công cụ như bạn đã mô tả. Tôi cũng không thể truy cập trực tiếp vào thông tin thời gian thực của cửa hàng. Để biết thông tin chi tiết về các chương trình khuyến mãi hiện tại, bạn nên liên hệ trực tiếp với cửa hàng hoặc kiểm tra trên trang web chính thức của họ. | 1045 ms |
| Agent v1   | Hiện tại không có sản phẩm nào trong kho có từ khóa "khuyến mãi", có thể cửa hàng không có chương trình giảm giá nào vào lúc này. | 1534 ms |
| Agent v2   | Sản phẩm không có trong kho. | 1618 ms |

---

### Case 4 — Ton kho iPhone 14

> **Prompt:** Chiec Iphone 14 co con hang khong ? Hay kiem tra ton kho bang tool search_inventory truoc khi ket luan.
> **Expected:** Tra ve trang thai ton kho chinh xac cua iPhone 14.

| Phase | Answer | Duration |
|-------|--------|----------|
| Single LLM | Xin lỗi, tôi không thể kiểm tra tình trạng còn hàng hoặc truy cập các công cụ tìm kiếm tồn kho thực tế. Bạn nên kiểm tra trên trang web chính thức của Apple hoặc liên hệ với các cửa hàng bán lẻ để biết thông tin cập nhật nhất về tình trạng hàng của iPhone 14. | 1465 ms |
| Agent v1   | Chiếc iPhone 14 hiện vẫn còn hàng với các tùy chọn sau: - iPhone 14 128GB: Còn 6 chiếc - iPhone 14 Plus 128GB: Còn 3 chiếc - iPhone 14 256GB: Còn 5 chiếc  Ngoài ra, còn có chương trình khuyến mãi giảm giá 10% cho iPhone 14 128GB. | 3577 ms |
| Agent v2   | Sản phẩm "Iphone 14" hiện có sẵn trong kho với số lượng 20 chiếc. | 1525 ms |

---

### Case 5 — San pham ngoai du lieu (Samsung S25)

> **Prompt:** Gia cua chiec Samsung s25 ultra la bao nhieu ? Hay tim trong kho bang tool search_inventory; neu khong co thi tra loi thong tin ngoai du lieu.
> **Expected:** Bao san pham khong co trong kho, khong tu y bịa gia.

| Phase | Answer | Duration |
|-------|--------|----------|
| Single LLM | Xin lỗi, tôi không thể truy cập công cụ tìm kiếm hoặc cơ sở dữ liệu hiện tại để kiểm tra giá của Samsung S25 Ultra. Tuy nhiên, tôi có thể nói rằng Samsung Galaxy S25 Ultra hiện chưa được công bố chính thức. Giá chi tiết sẽ phụ thuộc vào thông số kỹ thuật và khu vực khi sản phẩm được ra mắt. Bạn có thể kiểm tra thêm thông tin từ trang web của Samsung hoặc các nhà bán lẻ sau này. | 1327 ms |
| Agent v1   | Sản phẩm Samsung S25 Ultra không có trong kho hiện tại của chúng tôi. Theo thông tin ngoài dữ liệu, giá của Samsung Galaxy S25 Ultra có thể khác nhau tùy thuộc vào nhà cung cấp và quốc gia, nhưng thường rơi vào khoảng từ 1,000 đến 1,500 USD. Tuy nhiên, bạn nên kiểm tra tại các cửa hàng hoặc trang web bán lẻ để có giá chính xác nhất. | 2578 ms |
| Agent v2   | Sản phẩm không có trong kho. | 1678 ms |

---

## Conclusions

### Phase 1 — Single LLM: What can it do?

- Trả lời dựa hoàn toàn vào **training data** của model, không có dữ liệu thực tế.
- Không biết tồn kho, giá hiện tại, hay khuyến mãi — dễ **hallucinate** số liệu.
- Mỗi câu hỏi chỉ tốn **1 LLM call**, latency trung bình 1,348 ms.
- Phù hợp cho câu hỏi chung, không phù hợp cho nghiệp vụ cần dữ liệu thực.

### Phase 2 — Agent v1: ReAct thêm được gì?

- Có thể **gọi tool** để lấy dữ liệu thực từ kho hàng trước khi trả lời.
- Trung bình **1.8 LLM calls/case** do cần thêm bước Thought → Action → Observation.
- Latency trung bình tăng lên 1,429 ms/call, tổng token tăng lên 3,328.
- Nhược điểm: prompt v1 không cấm dùng kiến thức ngoài → vẫn có thể hallucinate
  khi tool không trả về kết quả (thấy rõ ở Case 5 — Samsung S25).

### Phase 3 — Agent v2: Fix được gì so với v1?

- **Prompt v2** thêm rule cứng: chỉ trả lời từ kết quả tool, không dùng kiến thức ngoài.
- **Tool `list_all_inventory`** cho phép liệt kê toàn bộ kho mà không cần từ khóa.
- Tổng token: 2,460 (so với v1: 3,328)
- Chi phí ước tính: $0.0246 (so với v1: $0.0333)
- Case 5 (Samsung S25): v2 phải báo không có trong kho, không tự bịa giá.

### Tổng hợp

| Tiêu chí | Single LLM | Agent v1 | Agent v2 |
|----------|-----------|---------|---------|
| Dùng dữ liệu thực | Không | Có | Có |
| Chống hallucination | Không | Một phần | Có (rule cứng) |
| LLM calls / case | 1 | ~1.8 | ~1.4 |
| Chi phí / session | $0.0083 | $0.0333 | $0.0246 |
| List toàn bộ kho | Không | Không (cần từ khóa) | Có (`list_all_inventory`) |
