# -*- coding: utf-8 -*-
"""MCP 缓存层：点餐台与麦当劳官方 MCP 之间的唯一桥梁。

刷新流程（每次【开启点餐台】执行一次，见 ../MCP_INTEGRATION.md）：
  1) Agent 会话调用 mcd-mcp.query-nearby-stores → 最近门店
  2) Agent 会话调用 mcd-mcp.list-nutrition-foods → 全量营养库
  3) 把两者写入 data/mcp_cache.json（含与 CATALOG 的 diff）
  4) 本服务启动时读入内存，并用最新营养覆盖 CATALOG（in place）

使用期间不再调用 MCP——缓存即真相；下次重新"开启点餐台"时覆盖本文件。
服务本身不联网调 MCP（MCP 工具在 Agent 会话中才可用）。
"""
from __future__ import annotations

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE, "data", "mcp_cache.json")

_data: dict | None = None


def load() -> dict:
    """读缓存文件（进程内只加载一次）。没有缓存时返回空 dict，服务仍可用（走 CATALOG 快照）。"""
    global _data
    if _data is None:
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {}
    return _data


def store() -> dict | None:
    """最近门店（query-nearby-stores 的 nearest），无缓存时返回 None。"""
    return (load().get("store") or {}).get("nearest")


def synced_at() -> str:
    return str(load().get("generated_at") or "")


def refresh_catalog() -> list[dict]:
    """用 MCP 最新营养覆盖 CATALOG 营养值（in place）。返回改动列表（启动时打印用）。"""
    from nutrition_core import CATALOG

    by_name = load().get("nutrition_by_name") or {}
    name_map = load().get("name_map") or {}
    changed = []
    for cname, d in CATALOG.items():
        rec = by_name.get(name_map.get(cname, cname))
        if not rec:
            continue
        for ck, mk in (("kcal", "kcal"), ("p", "p"), ("f", "f"),
                       ("c", "c"), ("na", "na"), ("ca", "ca")):
            new = rec.get(mk)
            if new is not None and d.get(ck) != new:
                changed.append(dict(code=str(d["code"]), name=cname,
                                    field=ck, old=d.get(ck), new=new))
                d[ck] = new
    return changed
