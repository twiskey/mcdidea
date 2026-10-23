# -*- coding: utf-8 -*-
"""菜单视图：把 nutrition_core.CATALOG 转成前端要的 JSON。

营养数值已在服务启动时由 mcp_cache.refresh_catalog() 用麦当劳官方 MCP
的缓存覆盖过——这里的 CATALOG 就是"开启点餐台时同步的最新值"。
"""
from __future__ import annotations

import mcp_cache
from nutrition_core import CATALOG

# 分类顺序与展示名（与 CATALOG 的 cat 字段对应）
CATEGORIES = [
    ("main", "汉堡 · 卷"),
    ("side", "小食"),
    ("drink", "饮品"),
]


def _initial(name: str) -> str:
    """菜品色块上的字：优先取品牌名里的第一个汉字。"""
    overrides = {
        "不素之霸双层牛堡": "牛", "双层深海鳕鱼堡": "鳕", "双层吉士汉堡": "吉",
        "吉士汉堡": "吉", "酥酥多笋卷": "笋", "麦乐鸡5块": "鸡",
        "中薯条": "薯", "大薯条": "薯", "小杯玉米杯": "玉", "大杯玉米杯": "玉",
        "纯牛奶（盒装）": "奶", "热牛奶中杯": "奶", "可乐中杯": "乐",
        "雪碧中杯": "碧", "100%苹果汁": "苹", "锡兰红茶": "茶",
        "阳光柠檬红茶中杯": "柠", "中杯怡泉+C": "柠",
    }
    if name in overrides:
        return overrides[name]
    for ch in name:
        if "\u4e00" <= ch <= "\u9fff":
            return ch
    return name[:1]


def menu_payload() -> dict:
    cats = []
    for key, label in CATEGORIES:
        items = []
        for name, d in CATALOG.items():
            if d.get("cat") != key:
                continue
            items.append(dict(
                code=d["code"], name=name, price=d["price"], kcal=d["kcal"],
                protein=d["p"], sodium=d["na"], calcium=d["ca"],
                color=d["color"], initial=_initial(name),
            ))
        cats.append(dict(key=key, label=label, items=items))
    payload = dict(categories=cats)
    st = mcp_cache.store()
    payload["store"] = dict(
        name=st["storeName"], address=st["address"], distance=st["distance"],
        storeCode=str(st["storeCode"]),
        open_hours=f'{st.get("businessStartTime", "")}-{st.get("businessEndTime", "")}',
        open_now=bool(st.get("businessStatus")),
    ) if st else None
    payload["synced_at"] = mcp_cache.synced_at()
    return payload


def find(code: str):
    """按 code 找官方单品，返回 (name, dict) 或 None。"""
    code = str(code)
    for name, d in CATALOG.items():
        if str(d["code"]) == code:
            return name, d
    return None
