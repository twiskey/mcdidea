# -*- coding: utf-8 -*-
"""
营养肖像 · 生成器（S1→S2→S3→S4 一键出图 + 出曲）
================================================
输入：一句人话描述 + 用餐时间 + 自选铭文（可选） + 曲风（可选）

  出图：营养光谱（带饼图）——已定稿视觉（宏量/微量分区 + 虚线分界 + 马卡龙饼图）
  出曲：民乐 / 爵士 / 摇滚——按营养数据映射生成，附专业版与大众版说明

用法（命令行）：
  python nutrition_portrait.py "我今天吃了板烧、玉米杯和纯牛奶" --time 2026-10-17T23:50
  python nutrition_portrait.py "早饭吃了脆薯饼和纯牛奶，午饭板烧加玉米杯" \
         --day --style rock --name 麦当当

用法（导入）：
  from nutrition_portrait import portrait
  res = portrait("我今天吃了板烧、玉米杯和纯牛奶",
                 when=datetime.now(), inscription="麦当当", style="jazz")
  # res["spectrum"] 图片路径；res["melody"] 旋律结果 dict（含 audio/plain/headline）
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Optional

from nutrition_core import parse, aggregate, day_aggregate, split_meals, fingerprint

STYLE_CHOICES = ("minyue", "jazz", "rock")
STYLE_LABELS = {"minyue": "民乐", "jazz": "爵士", "rock": "摇滚"}


# ------------------------------------------------------------------ 光谱
def render_spectrum_image(agg: dict, fp: dict, out: str,
                          with_pie: bool = True) -> str:
    """渲染营养光谱（默认带饼图，即定稿版）。"""
    from spectrum_toy import render_spectrum
    return render_spectrum(agg, fp, out, with_pie=with_pie)


# ------------------------------------------------------------------ 单餐
def portrait(raw_text: str, when: Optional[datetime] = None, inscription: str = "",
             style: str = "minyue", price: Optional[float] = None,
             meal_label: str = "一餐", out_dir: str = ".",
             with_spectrum: bool = True, with_melody: bool = True) -> dict:
    """一句话 → 光谱图 + 旋律 + 说明。返回结果字典。"""
    when = when or datetime.now()
    if style not in STYLE_CHOICES:
        raise ValueError(f"style 需为 {STYLE_CHOICES} 之一")

    p = parse(raw_text)
    agg = aggregate(p, meal_label=meal_label, price=price)
    order = [it["name"] for it in agg["items"]]
    fp = fingerprint(when, order, raw_text,
                     {"name": inscription} if inscription else {})

    res = dict(raw_text=raw_text, when=when.strftime("%Y-%m-%d %H:%M"),
               inscription=inscription, style=style,
               order=order, nutrition=agg["total"])

    stem = f"{STYLE_LABELS[style]}_{when.strftime('%Y%m%d_%H%M')}"
    if with_spectrum:
        img = f"{out_dir}/营养光谱_{stem}.png"
        render_spectrum_image(agg, fp, img, with_pie=True)
        res["spectrum"] = img

    if with_melody:
        from melody_style import generate, to_markdown_pro
        d = generate(raw_text, order, when, style=style,
                     inscription=inscription, price=price,
                     label=meal_label,
                     audio_name=f"{out_dir}/营养旋律_{stem}.wav")
        res["melody"] = d
        res["melody_pro_md"] = to_markdown_pro(d)
        res["melody_plain_md"] = "# 这顿饭，听起来是什么味道\n\n" + d["plain"] + "\n"

    return res


# ------------------------------------------------------------------ 日谱
def day_portrait(raw_text: str, when: Optional[datetime] = None,
                 inscription: str = "", style: str = "minyue",
                 out_dir: str = ".") -> dict:
    """多餐日谱：早/午/晚合并成一张光谱 + 一首曲。"""
    when = when or datetime.now()
    segs = [(lab or "一餐", parse(chunk)) for lab, chunk in split_meals(raw_text)
            if parse(chunk).items]
    agg = day_aggregate(segs, day_label="一日")
    order = [m["name"] for m in agg.get("meals", [])]
    fp = fingerprint(when, order, raw_text,
                     {"name": inscription} if inscription else {})

    stem = f"日谱_{when.strftime('%Y%m%d_%H%M')}"
    img = f"{out_dir}/营养光谱_{stem}.png"
    render_spectrum_image(agg, fp, img, with_pie=True)

    from melody_style import generate
    d = generate(raw_text, order, when, style=style, inscription=inscription,
                 label="一日", audio_name=f"{out_dir}/营养旋律_{stem}.wav")
    return dict(raw_text=raw_text, when=when.strftime("%Y-%m-%d %H:%M"),
                inscription=inscription, style=style, order=order,
                nutrition=agg["total"], spectrum=img, melody=d)


# ------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="营养肖像生成器：一句话 → 营养光谱图 + 营养旋律")
    ap.add_argument("text", help="餐品描述，如「我今天吃了板烧、玉米杯和纯牛奶」")
    ap.add_argument("--time", default=None, help="用餐时间 ISO 格式，如 2026-10-17T23:50")
    ap.add_argument("--name", default="", help="自选铭文（显示在落款处）")
    ap.add_argument("--style", default="minyue", choices=STYLE_CHOICES,
                    help="旋律曲风：minyue=民乐 / jazz=爵士 / rock=摇滚")
    ap.add_argument("--price", type=float, default=None, help="总价（可选）")
    ap.add_argument("--label", default="一餐", help="餐次标签，如 午餐")
    ap.add_argument("--day", action="store_true", help="多餐合并成日谱")
    ap.add_argument("--no-spectrum", action="store_true", help="不出图")
    ap.add_argument("--no-melody", action="store_true", help="不出曲")
    ap.add_argument("--out-dir", default=".", help="输出目录")
    ap.add_argument("--json", action="store_true", help="以 JSON 打印结果摘要")
    a = ap.parse_args(argv)

    when = datetime.fromisoformat(a.time) if a.time else datetime.now()

    if a.day:
        res = day_portrait(a.text, when, a.name, a.style, a.out_dir)
    else:
        res = portrait(a.text, when, a.name, a.style, a.price, a.label,
                       a.out_dir, not a.no_spectrum, not a.no_melody)

    if a.json:
        brief = {k: v for k, v in res.items()
                 if k in ("raw_text", "when", "style", "spectrum", "order", "nutrition")}
        if "melody" in res:
            brief["melody"] = {k: res["melody"][k]
                               for k in ("audio", "headline", "bpm", "duration")}
        print(json.dumps(brief, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"餐品：{' + '.join(res['order'])}")
        t = res["nutrition"]
        print(f"营养：{t['kcal']:.0f} kcal · 蛋白 {t['p']:.0f}g · 脂肪 {t['f']:.0f}g "
              f"· 碳水 {t['c']:.0f}g · 钠 {t['na']:.0f}mg · 钙 {t['ca']:.0f}mg")
        if "spectrum" in res:
            print(f"光谱图：{res['spectrum']}")
        if "melody" in res:
            m = res["melody"]
            print(f"旋律：{m['music']['audio']}（{STYLE_LABELS[a.style]} · "
                  f"{m['music']['bpm']} BPM · {m['music']['duration']}s）")
            print(f"一句话：{m['headline']}")
    return res


if __name__ == "__main__":
    main()
