#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""营养旋律 skill 执行脚本：合成 WAV + 生成说明（专业版/大众版/JSON）。

用法见 ../SKILL.md。引擎位于项目根（nutrition_core.py / melody_style.py /
melody_minyue.py / melody_jazz.py / melody_rock.py）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def _find_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "nutrition_core.py").exists() and (p / "melody_style.py").exists():
            return p
    raise SystemExit("找不到引擎目录：需要 nutrition_core.py 与 melody_style.py")


ROOT = _find_root()
sys.path.insert(0, str(ROOT))

from nutrition_core import CATALOG, Item, Parsed  # noqa: E402
from melody_style import STYLES, generate, to_markdown_pro  # noqa: E402


def _parse_codes(raw: str):
    items, names = [], []
    for seg in raw.split(","):
        seg = seg.strip()
        if not seg:
            continue
        code, _, q = seg.partition(":")
        qty = int(q) if q.strip() else 1
        hit = next(((n, d) for n, d in CATALOG.items() if str(d["code"]) == str(code)), None)
        if hit is None:
            raise SystemExit(f"菜单里没有这个编码：{code}")
        name, d = hit
        items.append(Item(name=name, qty=qty,
                          kcal=d["kcal"] * qty, p=d["p"] * qty, f=d["f"] * qty,
                          c=d["c"] * qty, na=d["na"] * qty, ca=d["ca"] * qty,
                          price=d["price"] * qty, color=d["color"], tone=d["tone"],
                          cat=d["cat"], code=str(d["code"])))
        names.append(name + (f"×{qty}" if qty > 1 else ""))
    if not items:
        raise SystemExit("--codes 为空")
    return Parsed(items=items, raw_text="、".join(names)), "、".join(names)


def main() -> None:
    ap = argparse.ArgumentParser(description="营养旋律：营养数据 → 12~20 秒旋律")
    ap.add_argument("text", nargs="?", default="", help="自然语言餐品描述")
    ap.add_argument("--codes", help="SKU 编码:数量，逗号分隔")
    ap.add_argument("--style", default="minyue", choices=list(STYLES), help="曲风")
    ap.add_argument("-o", "--out", help="输出 WAV 路径")
    ap.add_argument("--json-out", help="说明 JSON 路径")
    ap.add_argument("--md-out", help="专业版+大众版 Markdown 路径")
    ap.add_argument("--time", help="指纹时间 ISO，如 2026-10-19T23:50")
    ap.add_argument("--name", default="", help="铭文（名字/数字/颜色）")
    ap.add_argument("--label", default="一餐", help="餐次标签")
    ap.add_argument("--price", type=float, help="总价，留空自动")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args()

    if not args.text and not args.codes:
        ap.error("请提供餐品描述，或用 --codes 指定 SKU")

    when = datetime.fromisoformat(args.time) if args.time else datetime.now()
    if args.codes:
        parsed, raw = _parse_codes(args.codes)
        order = [i.name for i in parsed.items]
    else:
        raw = args.text
        parsed = None
        from nutrition_core import parse
        p = parse(raw)
        if not p.items:
            raise SystemExit("没识别出任何餐品，请检查描述（或改用 --codes）")
        order = [i.name for i in p.items]

    out = args.out or os.path.join(
        os.getcwd(), f"营养旋律_{STYLES[args.style]['label']}_{datetime.now():%Y%m%d_%H%M%S}.wav")
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)

    d = generate(raw, order, when, style=args.style, inscription=args.name,
                 price=args.price, label=args.label, audio_name=out, agg=None if parsed is None else _agg(parsed, args))
    print(json.dumps(dict(output=out, style=args.style,
                          headline=d["headline"], plain=d["plain"],
                          music=d["music"], rates=d["rates"],
                          input=d["input"], nutrition=d["nutrition"]),
                    ensure_ascii=False, indent=2))

    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)) or ".", exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    if args.md_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.md_out)) or ".", exist_ok=True)
        lead = d["plain"].split("\n")
        lead_line = next((s for s in lead if s.strip().lstrip("*").startswith("一句话")), "")
        lead_clean = (lead_line.replace("**", "").replace("一句话：", "")
                      .replace("一句话:", "").strip().lstrip("- ").strip())
        md = ["# 这顿饭，听起来是什么味道", "", lead_clean, "",
              "## 编曲说明（专业版）", "", to_markdown_pro(d), ""]
        with open(args.md_out, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
    print(f"\n已生成：{out}", file=sys.stderr)


def _agg(parsed: Parsed, args) -> dict:
    from nutrition_core import aggregate
    return aggregate(parsed, meal_label=args.label, price=args.price)


if __name__ == "__main__":
    main()
