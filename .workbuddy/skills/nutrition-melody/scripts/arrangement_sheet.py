#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编曲规划单生成器（ARR 编号）。

编曲规划师工作流第一步：先出单，再按单合成。规划单内容由真实营养数值驱动。
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

from nutrition_core import CATALOG, Item, Parsed, aggregate, fingerprint, parse  # noqa: E402
from melody_style import STYLES, _load  # noqa: E402

# 配器层次表：与三曲风引擎的实际实现一一对应
ORCHESTRATION = {
    "minyue": dict(
        name="民乐室内乐（二胡主奏 + 古筝 + 竹笛）",
        layers=[
            ("L1 主奏", "二胡", "D4–D6", "承载营养映射的骨干旋律，6.2Hz 密揉弦 + 滑音 + 弓噪", "主 0.30"),
            ("L2 铺底", "古筝", "C3–C4", "每 2 拍一组五声琶音，4 种 pattern 轮换，末音前 1 拍停", "副 0.30"),
            ("L3 点缀", "梆子/木鱼", "打击", "强拍 0.13 / 中 0.055 / 弱 0.035，正拍下压", "弱"),
            ("L4 色彩", "竹笛 + 房间混响", "高八度", "乐句开头长音标句读；混响 0.11/0.23/0.37s", "非常弱 0.16"),
        ],
        tail="徵→角→商级进下行，钙不足停二度悬置；末音 3.2 拍渐弱",
    ),
    "jazz": dict(
        name="轻爵士钢琴三重奏（电钢琴 + 行走贝斯 + 刷鼓）",
        layers=[
            ("L1 主奏", "电钢琴（Rhodes tine）", "C4–C6", "骨干旋律，强 2/4 泛音 + 5.4 倍非谐钟声，双段包络", "主"),
            ("L2 低音", "行走贝斯", "E2–E4", "每拍换音：根→三→五→经过音，全曲推进引擎", "副"),
            ("L3 律动", "刷鼓", "打击", "swing hat + 2/4 brush snare，Swing 2:1 反拍重音", "弱"),
            ("L4 和声/空间", "comping + 房间混响", "中音区", "每 2 拍 Cmaj7/Am7/Fmaj7/G7；混响三段延迟", "非常弱"),
        ],
        tail="钙不足上行停九音不回落；混响自然收",
    ),
    "rock": dict(
        name="流行摇滚四件套（重失真吉他 + 贝斯 + 鼓组）",
        layers=[
            ("L1 主奏", "重失真电吉他", "E3–E5", "锯齿双吉他失谐 0.6% → tanh drive 7.5 → 箱体低通", "主"),
            ("L2 节奏", "强力和弦 riff", "E2–E4", "根+五+八度（无三音），I-V-vi-IV，八分 chug", "副"),
            ("L3 低音", "电贝斯", "E1–E3", "每拍根音，第 2/4 拍八度顶，第 5 拍半音经过音", "副"),
            ("L4 律动/空间", "鼓组 + 延音收尾", "打击", "kick 四踩+双踩、snare 2/4、每 2 小节三连填充；末尾延音和弦 + 1.6s 全局淡出", "—"),
        ],
        tail="钙不足上行停二音（上扬悬置）；伴奏提前 1.5 拍收，延音和弦 2.2s 渐弱",
    ),
}


def main() -> None:
    ap = argparse.ArgumentParser(description="编曲规划单：营养数据 → 配器规划（ARR 编号）")
    ap.add_argument("text", nargs="?", default="", help="自然语言餐品描述")
    ap.add_argument("--codes", help="SKU 编码:数量，逗号分隔")
    ap.add_argument("--style", default="minyue", choices=list(STYLES), help="曲风")
    ap.add_argument("-o", "--out", help="规划单 Markdown 路径")
    ap.add_argument("--time", help="指纹时间 ISO")
    ap.add_argument("--name", default="", help="铭文")
    ap.add_argument("--label", default="一餐", help="餐次标签")
    ap.add_argument("--price", type=float, help="总价")
    args = ap.parse_args()

    if not args.text and not args.codes:
        ap.error("请提供餐品描述，或用 --codes 指定 SKU")

    when = datetime.fromisoformat(args.time) if args.time else datetime.now()
    if args.codes:
        items, names = [], []
        for seg in args.codes.split(","):
            seg = seg.strip()
            if not seg:
                continue
            code, _, q = seg.partition(":")
            qty = int(q) if q.strip() else 1
            hit = next(((n, d) for n, d in CATALOG.items() if str(d["code"]) == str(code)), None)
            if hit is None:
                raise SystemExit(f"菜单里没有这个编码：{code}")
            name, d = hit
            items.append(Item(name=name, qty=qty, kcal=d["kcal"] * qty, p=d["p"] * qty,
                              f=d["f"] * qty, c=d["c"] * qty, na=d["na"] * qty,
                              ca=d["ca"] * qty, price=d["price"] * qty, color=d["color"],
                              tone=d["tone"], cat=d["cat"], code=str(d["code"])))
            names.append(name)
        parsed = Parsed(items=items, raw_text="、".join(names))
        raw = parsed.raw_text
    else:
        raw = args.text
        parsed = parse(raw)
        if not parsed.items:
            raise SystemExit("没识别出任何餐品")

    agg = aggregate(parsed, meal_label=args.label, price=args.price)
    order = [i["name"] for i in agg["items"]]
    fp = fingerprint(when, order, raw, {"name": args.name} if args.name else {})

    compose, explain, _render = _load(args.style)
    score = compose(agg, fp)
    ex = explain(score, agg)
    t = agg["total"]

    # 段落表：按营养素分组统计拍数/音级/力度
    segs = {}
    for n in score["notes"]:
        seg = segs.setdefault(n["nutr"], dict(beats=0.0, n=0, hi=0.0, vel=0.0))
        seg["beats"] += n["dur"] / (60.0 / score["bpm"])
        seg["n"] += 1
        seg["hi"] = max(seg["hi"], n["freq"])
        seg["vel"] = max(seg["vel"], n["vel"])

    orch = ORCHESTRATION[args.style]
    arr_no = f"ARR-{datetime.now():%Y-%m%d}-%03d" % (when.minute % 1000)

    L = []
    L.append(f"# 营养旋律 · {STYLES[args.style]['label']}版 配器规划单（{arr_no}）")
    L.append("")
    L.append(f"> 依据：本 skill 内置《编曲规划师工作流》第三节「匹配口径」。引擎全部波形合成，无第三方采样。")
    L.append(f"> 版本：v1.0　日期：{datetime.now():%Y-%m-%d}　指纹：{fp['hex']}")
    L.append("")
    L.append("## 一、成品定位")
    L.append("")
    L.append("| 项目 | 参数 |")
    L.append("|---|---|")
    L.append(f"| 曲风 | {orch['name']} |")
    L.append(f"| 时长 | {score['duration'] if 'duration' in score else round(sum(n['dur'] for n in score['notes']), 2)} 秒（{len(score['notes'])} 音） |")
    L.append(f"| 调式 | {'小调色彩' if score['minor'] else '大调/明亮'}（钠钙比 {agg['na_ratio']:.2f}） |")
    L.append(f"| BPM | {score['bpm']}（= 基数 + 能量达成率 {agg['kcal_rate']*100:.0f}% × 系数） |")
    L.append(f"| 能量 | {t['kcal']:.0f} kcal / {t.get('price') and round(t['price'],2) or '—'} 元 |")
    L.append(f"| 输出 | 44.1kHz / 16bit / 立体声 WAV |")
    L.append("")
    L.append("## 二、配器层次表")
    L.append("")
    L.append("| 层 | 乐器 | 音区 | 职能 | 音量 |")
    L.append("|---|---|---|---|---|")
    for row in orch["layers"]:
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("**层次原则**：L1 与 L2 音区错开避免同频掩蔽；L3 只做律动不抢主奏；L4 不压缩保留余韵。")
    L.append("")
    L.append("## 三、段落结构（六乐句 = 六营养素，与光谱同序）")
    L.append("")
    L.append("| 乐句 | 拍数 | 音符数 | 峰值频率 | 峰值力度 |")
    L.append("|---|---|---|---|---|")
    for name, s in segs.items():
        L.append(f"| {name} | {s['beats']:.1f} | {s['n']} | {s['hi']:.0f} Hz | {s['vel']:.2f} |")
    L.append("")
    L.append("## 四、收尾（三段式，验收硬指标）")
    L.append("")
    L.append(f"- 营养依据：钙达成率 {ex['rates'].get('钙', 0)*100:.0f}% → "
             f"{'悬置收束（不落主音）' if ex['rates'].get('钙', 0) < 0.5 else '级进落主音'}")
    L.append(f"- 手法：{orch['tail']}")
    L.append("- 验收：最后 1 秒能量必须平滑衰减（脚本自动校验），不得出现硬切。")
    L.append("")
    L.append("## 五、连贯性与唯一性")
    L.append("")
    L.append("- 后一句起点音向前句末音靠拢，跨度大时取中间过渡音；换音均带滑音。")
    L.append(f"- 装饰音插位 = 交互指纹第 16–20 位（本单指纹 {fp['hex']}）→ 曲子独一无二。")
    L.append("- 事实层（调式/BPM/句长/音高）只由营养数值决定，指纹不参与。")
    L.append("")
    L.append("## 六、验收清单")
    L.append("")
    L.append("- [ ] 时长 10~22 秒")
    L.append("- [ ] 结尾平滑衰减，无硬切")
    L.append("- [ ] 无 >0.5s 的静音尾")
    L.append("- [ ] peak ≤ 0.95 × 满幅，无削波")
    L.append("- [ ] 说明三件套齐全（专业版映射 / 大众版概括 / JSON）")
    L.append("")
    L.append("> 合规：全部音色为波形合成，无采样素材。本单为过程辅助文档，不构成法律意见。")

    md = "\n".join(L) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"已生成：{args.out}", file=sys.stderr)
    else:
        print(md)


if __name__ == "__main__":
    main()
