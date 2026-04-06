import json
import os
import unicodedata
from typing import List, Dict, Any

DATA_FILE = os.path.join(os.path.dirname(__file__), "../../data/inventory.json")


def _load() -> List[Dict[str, Any]]:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: List[Dict[str, Any]]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Tool functions ─────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().strip()


def search_inventory(query: str) -> str:
    """
    Tìm sản phẩm theo tên (không phân biệt hoa thường, chuẩn hóa Unicode).
    Trả về danh sách sản phẩm khớp (id, name, price, stock).
    """
    query = _normalize(query.strip('"\''))
    if not query:
        items = _load()
        lines = [f"[{m['id']}] {m['name']} | Giá: {m['price']:,} VND | Tồn kho: {m['stock']}" for m in items]
        return "\n".join(lines)
    items = _load()
    matches = [item for item in items if query in _normalize(item["name"])]
    if not matches:
        return f"Không tìm thấy sản phẩm nào khớp với '{query}'."
    lines = [f"[{m['id']}] {m['name']} | Giá: {m['price']:,} VND | Tồn kho: {m['stock']}" for m in matches]
    return "\n".join(lines)


def update_inventory(args: str) -> str:
    """
    Cập nhật giá hoặc tồn kho của sản phẩm.
    args format: "<id>, price=<value>" hoặc "<id>, stock=<value>" hoặc cả hai.
    Ví dụ: "P001, price=27000000, stock=10"
    """
    parts = [p.strip() for p in args.split(",")]
    if not parts:
        return "Thiếu tham số. Dùng: <id>, price=<value>, stock=<value>"

    product_id = parts[0].upper()
    updates = {}
    for part in parts[1:]:
        if "=" in part:
            key, val = part.split("=", 1)
            key = key.strip()
            if key in ("price", "stock"):
                try:
                    updates[key] = int(val.strip())
                except ValueError:
                    return f"Giá trị '{val.strip()}' không hợp lệ cho '{key}'."

    if not updates:
        return "Không có trường nào được cập nhật. Dùng price= hoặc stock=."

    items = _load()
    for item in items:
        if item["id"] == product_id:
            item.update(updates)
            _save(items)
            changed = ", ".join(f"{k}={v:,}" for k, v in updates.items())
            return f"Đã cập nhật [{product_id}] {item['name']}: {changed}."

    return f"Không tìm thấy sản phẩm với id '{product_id}'."


def delete_inventory(args: str) -> str:
    """
    Xóa sản phẩm khỏi kho theo id.
    args format: "<id>"
    Ví dụ: "P003"
    """
    product_id = args.strip().upper()
    items = _load()
    remaining = [item for item in items if item["id"] != product_id]
    if len(remaining) == len(items):
        return f"Không tìm thấy sản phẩm với id '{product_id}'."
    deleted = next(item for item in items if item["id"] == product_id)
    _save(remaining)
    return f"Đã xóa [{product_id}] {deleted['name']} khỏi kho."


# ── Tool definitions (dùng trực tiếp với ReActAgent) ──────────────────────────

INVENTORY_TOOLS = [
    {
        "name": "search_inventory",
        "description": "Tìm sản phẩm trong kho theo tên. Input: chuỗi tên cần tìm.",
        "func": search_inventory,
    },
    {
        "name": "update_inventory",
        "description": (
            "Cập nhật giá hoặc số lượng tồn kho của sản phẩm. "
            "Input: '<id>, price=<value>, stock=<value>' (price và stock tùy chọn)."
        ),
        "func": update_inventory,
    },
    {
        "name": "delete_inventory",
        "description": "Xóa sản phẩm khỏi kho theo id. Input: '<id>'.",
        "func": delete_inventory,
    },
]
