# -*- coding: utf-8 -*-
"""订单 → 取餐号 → 营养光谱 + 营养旋律。

设计要点：
  1. 营养数值直接按 SKU code 从官方 CATALOG 取，不走文本解析（避免"玉米杯"被
     别名匹配成小杯、数量丢失等问题）。
  2. 指纹的铭文用取餐号，时间用下单时刻 → 同一单反复进出结果一致；
     不同单、不同菜必然不同。
  3. 每个订单每个曲风只生成一次，产物落在 out/<order_no>/。
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime

from nutrition_core import CATALOG, Item, Parsed, aggregate, fingerprint
from spectrum_toy import render_spectrum
from melody_style import STYLES, PLAIN_VERSION, generate as generate_melody

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "out")
DATA_DIR = os.path.join(BASE, "data")
LEDGER = os.path.join(DATA_DIR, "orders.json")

_lock = threading.RLock()
_db = None


# ---------------------------------------------------------------- 台账
def _load() -> dict:
    global _db
    if _db is None:
        try:
            with open(LEDGER, encoding="utf-8") as f:
                _db = json.load(f)
        except Exception:
            _db = {"seq": 0, "orders": {}}
        _db.setdefault("seq", 0)
        _db.setdefault("orders", {})
    return _db


def _save() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER)


# ---------------------------------------------------------------- 下单
def create_order(cart: list) -> dict:
    """cart: [{"code": "...", "qty": 2}] → 订单记录（含取餐号）。"""
    if not isinstance(cart, list) or not cart:
        raise ValueError("购物车是空的")

    rows = []
    for raw in cart:
        if not isinstance(raw, dict):
            raise ValueError("购物车格式不正确")
        code = str(raw.get("code") or "")
        try:
            qty = int(raw.get("qty") or 0)
        except (TypeError, ValueError):
            raise ValueError("数量必须是整数")
        if qty <= 0:
            continue
        if qty > 20:
            raise ValueError("单个餐品最多 20 份")
        hit = next(((n, d) for n, d in CATALOG.items()
                    if str(d["code"]) == code), None)
        if hit is None:
            raise ValueError("菜单里没有这个餐品")
        name, d = hit
        rows.append(dict(code=code, name=name, qty=qty,
                         price=round(d["price"] * qty, 2),
                         kcal=round(d["kcal"] * qty, 1)))

    if not rows:
        raise ValueError("购物车是空的")

    with _lock:
        db = _load()
        seq = int(db["seq"]) + 1
        db["seq"] = seq
        now = datetime.now()
        rec = dict(
            order_no=now.strftime("%Y%m%d") + f"-{seq:04d}",
            pickup=f"A{seq:03d}",
            created_at=now.isoformat(timespec="seconds"),
            items=rows,
            total=round(sum(r["price"] for r in rows), 2),
            count=sum(r["qty"] for r in rows),
            styles={},
        )
        db["orders"][rec["order_no"]] = rec
        _save()
        os.makedirs(os.path.join(OUT_DIR, rec["order_no"]), exist_ok=True)
        return rec


def get_order(order_no: str) -> dict:
    with _lock:
        rec = _load()["orders"].get(str(order_no))
        if rec is None:
            raise ValueError("订单不存在")
        return rec


# ---------------------------------------------------------------- 营养 → 图/曲
def _parsed(rec: dict) -> Parsed:
    items = []
    for row in rec["items"]:
        hit = next(((n, d) for n, d in CATALOG.items()
                    if str(d["code"]) == str(row["code"])), None)
        if hit is None:
            continue
        name, d = hit
        q = int(row["qty"])
        items.append(Item(
            name=name, qty=q,
            kcal=d["kcal"] * q, p=d["p"] * q, f=d["f"] * q, c=d["c"] * q,
            na=d["na"] * q, ca=d["ca"] * q, price=d["price"] * q,
            color=d["color"], tone=d["tone"], cat=d["cat"], code=str(d["code"]),
        ))
    raw = "、".join(r["name"] + (f"×{r['qty']}" if r["qty"] > 1 else "")
                    for r in rec["items"])
    return Parsed(items=items, raw_text=raw)


def _payload(rec: dict, style: str, entry: dict, cached: bool) -> dict:
    melody = entry["melody"]
    folder = rec["order_no"]
    return dict(
        order_no=folder, pickup=rec["pickup"], style=style,
        style_label=STYLES[style]["label"],
        spectrum_url=f"/media/{folder}/spectrum.png?v=1",
        audio_url=f"/media/{folder}/{entry['audio']}",
        melody=melody, nutrition=melody["nutrition"],
        items=rec["items"], total=rec["total"], cached=cached,
    )


def build_portrait(order_no: str, style: str = "minyue") -> dict:
    """生成（或复用）指定订单 + 曲风的光谱与旋律。"""
    if style not in STYLES:
        raise ValueError(f"不支持的曲风：{style}")

    with _lock:
        rec = get_order(order_no)
        folder = os.path.join(OUT_DIR, rec["order_no"])
        entry = rec["styles"].get(style)
        if entry:
            img_ok = os.path.exists(os.path.join(folder, "spectrum.png"))
            wav_ok = os.path.exists(os.path.join(folder, entry["audio"]))
            # 说明文案升级后，旧缓存要重算，否则页面还显示上一版说法
            fresh = entry.get("melody", {}).get("plain_version") == PLAIN_VERSION
            if img_ok and wav_ok and fresh:
                return _payload(rec, style, entry, cached=True)

        p = _parsed(rec)
        agg = aggregate(p, meal_label="一餐", price=rec["total"])
        when = datetime.fromisoformat(rec["created_at"])
        names = [i.name for i in p.items]
        fp = fingerprint(when, names, p.raw_text, {"name": rec["pickup"]})

        os.makedirs(folder, exist_ok=True)
        img = os.path.join(folder, "spectrum.png")
        if not os.path.exists(img):
            render_spectrum(agg, fp, img, with_pie=True)

        audio = f"{style}.wav"
        melody = generate_melody(
            p.raw_text, names, when, style=style, inscription=rec["pickup"],
            price=rec["total"], label="一餐",
            audio_name=os.path.join(folder, audio), agg=agg,
        )

        rec["styles"][style] = dict(audio=audio, melody=melody)
        _save()
        return _payload(rec, style, rec["styles"][style], cached=False)


def health() -> dict:
    with _lock:
        db = _load()
        return dict(ok=True, orders=len(db["orders"]), seq=int(db["seq"]))
