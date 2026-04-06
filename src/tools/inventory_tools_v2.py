"""
Inventory tools v2 — extends v1 with list_all_inventory.

Reason: v1 agent had no way to enumerate all products; calling search_inventory("")
returned nothing because empty query matched nothing. list_all_inventory fixes that.
"""

from src.tools.inventory_tools import INVENTORY_TOOLS, _load


def list_all_inventory(_args: str = "") -> str:
    """
    Trả về toàn bộ danh sách sản phẩm trong kho (bao gồm cả khuyến mãi).
    Không cần tham số.
    """
    items = _load()
    if not items:
        return "Kho hàng hiện đang trống."
    lines = [
        f"[{item['id']}] {item['name']} | Giá: {item['price']:,} VND | Tồn kho: {item['stock']}"
        for item in items
    ]
    return "\n".join(lines)


INVENTORY_TOOLS_V2 = INVENTORY_TOOLS + [
    {
        "name": "list_all_inventory",
        "description": "Liệt kê toàn bộ sản phẩm trong kho. Không cần tham số.",
        "func": list_all_inventory,
    }
]
