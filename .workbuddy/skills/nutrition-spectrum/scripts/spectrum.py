#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""营养光谱 skill 执行脚本。

用法见 ../SKILL.md。引擎位于项目根（nutrition_core.py + spectrum_toy.py），
本脚本只做参数解析与编排，不复制引擎逻辑。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def _find_root() -> Path:
    """向上找到含引擎的目录。"""
    for p in Path(__file__).resolve().parents:
        if (p / "nutrition_core.py").exists() and (p / "spectrum_toy.py").exists():
            return p
    raise SystemExit("找不到引擎目录：需要同目录下存在 nutrition_core.py 与 spectrum_toy.py")


ROOT = _find_root()
sys.path.insert(0, str(ROOT))

from nutrition_core import (  # noqa: E402
    CATALOG, Item, Parsed, aggregate, day_aggregate, fingerprint, parse, split_meals,
)
from spectrum_toy import NUTRIENTS as SPEC_NUTRIENTS  # noqa: E402
from spectrum_toy import render_spectrum  # noqa: E402


def _by_code(code: str, qty: int) -> Item:
    hit = next(((n, d) for n, d in CATALOG.items() if str(d["code"]) == str(code)), None)
    if hit is None:
        raise SystemExit(f"菜单里没有这个编码：{code}")
    name, d = hit
    return Item(name=name, qty=qty,
                kcal=d["kcal"] * qty, p=d["p"] * qty, f=d["f"] * qty, c=d["c"] * qty,
                na=d["na"] * qty, ca=d["ca"] * qty, price=d["price"] * qty,
                color=d["color"], tone=d["tone"], cat=d["cat"], code=str(d["code"]))


def _parse_codes(raw: str) -> Parsed:
    items, names = [], []
    for seg in raw.split(","):
        seg = seg.strip()
        if not seg:
            continue
        code, _, q = seg.partition(":")
        qty = int(q) if q.strip() else 1
        it = _by_code(code.strip(), qty)
        items.append(it)
        names.append(it.name + (f"×{qty}" if qty > 1 else ""))
    if not items:
        raise SystemExit("--codes 为空")
    return Parsed(items=items, raw_text="、".join(names))


def build(args) -> tuple[dict, dict, str]:
    when = datetime.fromisoformat(args.time) if args.time else datetime.now()
    raw = args.text or ""

    if args.codes:
        parsed = _parse_codes(args.codes)
        agg = aggregate(parsed, meal_label=args.label, price=args.price)
        order = [i.name for i in parsed.items]
        raw = parsed.raw_text
    elif args.day:
        segs = []
        for lab, chunk in split_meals(raw):
            p = parse(chunk)
            if p.items:
                segs.append((lab or "一餐", p))
        if not segs:
            raise SystemExit("没识别出任何餐品，请检查描述")
        agg = day_aggregate(segs, price=args.price, day_label="饮食日谱")
        order = [i.name for m in agg["meals"] for i in m["items"]]
        parsed = None
    else:
        parsed = parse(raw)
        if not parsed.items:
            raise SystemExit("没识别出任何餐品，请检查描述（或改用 --codes）")
        agg = aggregate(parsed, meal_label=args.label, price=args.price)
        order = [i.name for i in parsed.items]

    fp = fingerprint(when, order, raw, {"name": args.name} if args.name else {})
    return agg, fp, raw


def summarize(agg: dict, fp: dict, out: str, unmatched: list) -> dict:
    t = agg["total"]
    sugar_raw = t.get("sugar")
    sugar = sugar_raw if sugar_raw is not None else t["c"] * 0.35
    values = dict(na=t["na"], c=t["c"], p=t["p"], f=t["f"], sug=sugar, ca=t["ca"])
    rates = {n["key"]: min(values[n["key"]] / n["ref"], 1.6) for n in SPEC_NUTRIENTS}
    # 饼图数据：单餐用菜品，日谱用餐次
    units = agg["items"] if agg.get("mode") == "meal" else agg.get("meals", [])
    return dict(
        output=out,
        mode=agg.get("mode", "meal"),
        fingerprint=fp["hex"][:8],
        inscription=fp.get("inscription", ""),
        time=fp.get("when", ""),
        kcal=round(t["kcal"], 1),
        price=round(t.get("price") or 0, 2),
        nutrients=dict(
            carb=round(t["c"], 1), sugar=round(sugar, 1),
            sugar_estimated=sugar_raw is None,
            protein=round(t["p"], 1), fat=round(t["f"], 1),
            sodium=round(t["na"], 1), calcium=round(t["ca"], 1),
        ),
        rates={n["name"]: round(rates[n["key"]] * 100, 1) for n in SPEC_NUTRIENTS},
        pie=[dict(name=u["name"], pct=round(u["kcal"] / max(t["kcal"], 1e-6) * 100, 1))
             for u in units],
        unmatched=unmatched,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="营养光谱：六项营养素达成率谱带图")
    ap.add_argument("text", nargs="?", default="", help="自然语言餐品描述")
    ap.add_argument("--codes", help="SKU 编码:数量，逗号分隔，如 1406:1,4437:2")
    ap.add_argument("-o", "--out", help="输出 PNG 路径")
    ap.add_argument("--no-pie", action="store_true", help="不画饼图")
    ap.add_argument("--day", action="store_true", help="多餐合并成日谱")
    ap.add_argument("--time", help="指纹时间 ISO，如 2026-10-19T23:50")
    ap.add_argument("--name", default="", help="自选铭文（名字/数字/颜色）")
    ap.add_argument("--price", type=float, help="总价，留空自动")
    ap.add_argument("--label", default="一餐", help="餐次标签")
    ap.add_argument("--json", action="store_true", help="只输出 JSON 摘要")
    args = ap.parse_args()

    if not args.text and not args.codes:
        ap.error("请提供餐品描述，或用 --codes 指定 SKU")

    agg, fp, _raw = build(args)
    out = args.out or os.path.join(os.getcwd(),
                                   f"营养光谱_{datetime.now():%Y%m%d_%H%M%S}.png")
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    render_spectrum(agg, fp, out, with_pie=not args.no_pie)

    unmatched = []
    if args.text and not args.codes:
        p = parse(args.text)
        unmatched = [u for u in (p.unmatched or []) if u.strip(" 、,，")]

    s = summarize(agg, fp, out, unmatched)
    if args.json:
        print(json.dumps(s, ensure_ascii=False))
        return

    print(json.dumps(s, ensure_ascii=False, indent=2))
    print(f"\n已生成：{out}")


if __name__ == "__main__":
    main()
