# -*- coding: utf-8 -*-
"""
S4 曲风选择器：民乐 / 爵士
===========================
统一入口 — 传入菜单与曲风，输出音频 + 专业说明 + 大众版说明。

  from melody_style import generate
  res = generate("我今天吃了板烧、玉米杯和纯牛奶",
                 ["板烧鸡腿堡", "小杯玉米杯", "纯牛奶（盒装）"],
                 when=datetime.now(), style="jazz", inscription="麦当当")
  # res["audio"], res["plain"], res["headline"], res["mapping"]

两种曲风共用营养映射口径，只有音色与律动不同：
  民乐 = 二胡主奏 + 古筝 + 竹笛（五声调式，连贯滑音）
  爵士 = 电钢琴主奏 + 行走贝斯 + 刷鼓（Swing 摇摆，大七/九和弦）
共同约束：欢快、积极、温暖——小调仅在「钠严重超标且钙不足」时触发，
          两种曲风都以明亮大调为默认。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from nutrition_core import parse, aggregate, fingerprint

STYLES = {
    "minyue": dict(label="民乐", en="Chinese Folk", desc="二胡主奏 · 古筝 · 竹笛"),
    "jazz":   dict(label="爵士", en="Jazz", desc="电钢琴 · 行走贝斯 · 刷鼓"),
    "rock":   dict(label="摇滚", en="Rock", desc="过载电吉他 · 电贝斯 · 鼓组"),
}

# 大众版文案版本号：改文案时 +1，让点餐台自动重算缓存的说明
PLAIN_VERSION = 2

# 「最突出」那一项的通俗说法：风味名 + 口感
FLAVOR = {
    "碳水": ("主食的饱足感", "踏实、有分量"),
    "糖": ("甜味", "轻快、有点上头"),
    "蛋白质": ("肉的厚度", "结实、越听越有劲"),
    "脂肪": ("油润的香气", "浓郁、暖乎乎"),
    "钠": ("咸鲜味", "够味、有烟火气"),
    "钙": ("奶香", "干净、温和"),
}
# 曲风专属尾句（让同一份餐的三首曲子，这句话也不一样）
STYLE_TAIL = {
    "minyue": "像一段随口哼出来的小调",
    "jazz": "像一段让人跟着点头的摇摆",
    "rock": "像一段开着车往前走的节奏",
}


def _load(style: str):
    if style == "minyue":
        from melody_minyue import compose, explain, render as render_minyue
        return compose, explain, render_minyue
    if style == "jazz":
        from melody_jazz import compose, explain, render_jazz
        return compose, explain, render_jazz
    if style == "rock":
        from melody_rock import compose, explain, render_rock
        return compose, explain, render_rock
    raise ValueError(f"unknown style: {style}（可选：{list(STYLES)}）")


def plain_text(d: dict) -> str:
    """大众版说明（说人话，无术语）。两种曲风共用骨架，措辞随曲风微调。"""
    n = d["nutrition"]
    r = d["rates"]
    m = d["music"]
    style = m["style"]

    top = max(r, key=lambda k: r[k])
    low = min(r, key=lambda k: r[k])
    top_pct = r[top] * 100

    if n["kcal"] < 500:
        energy = "分量不算多"
    elif n["kcal"] < 750:
        energy = "分量刚好"
    else:
        energy = "分量挺足"

    if r["钠"] > 0.85:
        salt = "咸鲜味很冲，一听就知道这顿够味"
    elif r["钠"] > 0.5:
        salt = "咸鲜味偏重，是有记忆点的那种味道"
    else:
        salt = "咸味不重，整体偏清爽"

    if top == "钠":                      # 钠已经是主角时，别再重复"最抢耳"
        salt = "咸鲜是这顿饭的主角，别的味道都在给它让路"

    if r["钙"] < 0.5:
        tail = ("所以曲子最后没有落回“家”，留了个小小的悬念"
                "——就像提醒你：下次记得补杯奶。")
    else:
        tail = "钙也够用，所以曲子最后稳稳地落回了主音，收得完整。"

    # 曲风专属的一句
    if style == "minyue":
        timbre = "二胡拉主旋律，古筝在底下拨出亮亮的琶音，还有笛子偶尔探个头"
        feel = "像一段轻快的小曲，滑音连着走，不硌耳"
    elif style == "jazz":
        timbre = "电钢琴弹主旋律，贝斯一路走音推着往前，鼓刷轻轻扫着节奏"
        feel = "像咖啡馆里那种会让人跟着点头的轻爵士，暖洋洋的"
    else:
        timbre = "电吉他弹主旋律，贝斯和鼓组一路踩着拍子往前冲"
        feel = "像一首热血又阳光的公路摇滚，越听越有劲"

    lines = []
    # 首行：由"最突出的那一项"决定风味，钙决定收尾，曲风决定比喻
    flavor, mouth = FLAVOR.get(top, ("味道", "有点意思"))
    tail_short = "结尾故意留了个尾巴" if r["钙"] < 0.5 else "结尾稳稳落回主音"
    lines.append(f"**一句话**：这顿饭的味道，被写成了 {int(round(m['duration']))} 秒的"
                 f"{STYLES[style]['label']}——{flavor}最抢耳，{mouth}，"
                 f"{tail_short}，{STYLE_TAIL.get(style, '')}。")
    lines.append("")
    lines.append("**说人话版**：")
    lines.append("")
    lines.append(f"- 这顿饭 {n['kcal']} 大卡，{energy}，所以整首曲子节奏是轻快的，不拖沓。")
    lines.append(f"- 六样营养（碳水、糖、蛋白质、脂肪、盐、钙）各占一小段，"
                 f"**哪样给得多，哪样就唱得高、唱得久**。"
                 f"这顿饭里 **{top}最突出（{top_pct:.0f}%）**，"
                 f"所以它的乐句最高、最饱满、最显眼。")

    # 蛋白质的"力量感"按实际达成率分档，不再固定成一句话
    pr = r["蛋白质"]
    if pr > 0.6:
        power = "力量感很足——蛋白质管够，把整首曲子的骨架撑得笔直"
    elif pr > 0.35:
        power = "力量感适中——蛋白质不多不少，旋律站得稳"
    else:
        power = "力量感偏轻——蛋白质少，曲子主要靠节奏和音色撑场面"
    lines.append(f"- 味道上，{salt}；{power}。")
    lines.append(f"- 配器上，{timbre}，{feel}。")
    lines.append(f"- {tail}")
    lines.append("- 还有个小细节：同一份餐，每个人听到的曲子骨架相同，"
                 "但有几个装饰音的位置不一样——那是专属于你的版本。")
    lines.append("")
    lines.append(f"*（专业参数：{m['bpm']} BPM · "
                 f"{'小调' if m['mode'] == 'minor' else '大调'} · "
                 f"{m['notes']} 个音 · {m['duration']} 秒，详细对应见专业版说明。）*")
    return "\n".join(lines)


def to_markdown_pro(d: dict) -> str:
    n = d["nutrition"]
    m = d["music"]
    st = STYLES[m["style"]]
    out = [f"# 这首旋律是怎么写出来的（{st['label']}版）\n"]
    out.append(f"> {d['headline']}\n")
    out.append(f"**曲风**：{st['label']} {st['en']} — {st['desc']}　"
               f"**餐品**：{' + '.join(d['input']['order'])}　"
               f"**能量**：{n['kcal']} kcal　**时长**：{m['duration']}s\n")
    out.append("| 音乐要素 | 本曲取值 | 由哪项营养数据决定 |")
    out.append("|---|---|---|")
    for row in d["mapping"]:
        out.append(f"| {row['element']} | {row['value']} | {row['basis']} |")
    out.append("")
    out.append("## 营养达成率（对照光谱）\n")
    out.append("| " + " | ".join(d["rates"].keys()) + " |")
    out.append("|" + "---|" * len(d["rates"]))
    out.append("| " + " | ".join(f"{v*100:.0f}%" for v in d["rates"].values()) + " |")
    out.append("")
    out.append("## 固定映射规则（三种曲风共用，BPM 基准各不同）\n")
    bpm_rule = {"minyue": "80 + 能量达成率 × 38", "jazz": "96 + 能量达成率 × 30",
                "rock": "114 + 能量达成率 × 36"}[m["style"]]
    out.append("1. **调式** = 钠是否超 80% 且钙是否低于 50%（同时满足转暗色）")
    out.append(f"2. **BPM** = {bpm_rule}（{st['label']}）")
    out.append("3. **引子** = 三甲营养素的音程签名：起音级 = 第一名达成率×2.5 + 能量档位，"
               "第二名定跳进方向，第三名定回落深度")
    out.append("4. **乐句顺序** = 碳水→糖→蛋白质→脂肪→钠→钙（与光谱同序）")
    out.append("5. **句长** = 2.6 + 达成率 × 2.2 拍（宏量）/ 2.4 + 达成率（微量）")
    out.append("6. **骨干音级** = 达成率 × 8")
    out.append("7. **力度** = 0.50 + 0.36 × 达成率")
    out.append("8. **结尾** = 钙 < 50% → 悬置；≥50% → 落主音")
    out.append("9. **装饰音位置** = 交互指纹第 16–20 位")
    out.append("")
    if n["sugar_estimated"]:
        out.append("> 注：官方营养库无糖字段，糖按碳水 ×0.35 推算。")
    return "\n".join(out)


def generate(raw_text: str, order: list, when: Optional[datetime] = None,
             style: str = "minyue", inscription: str = "",
             price: Optional[float] = None, label: str = "一餐",
             audio_name: Optional[str] = None, agg: Optional[dict] = None) -> dict:
    """生成旋律 + 说明。返回 dict，含 audio / plain / headline / mapping 等。

    agg: 可选，直接传入已聚合的营养结果（点餐等结构化场景用，避免重复解析文本
         导致数量丢失或别名歧义）。不传则按 raw_text 解析。
    """
    when = when or datetime.now()
    compose, explain, render = _load(style)
    if agg is None:
        agg = aggregate(parse(raw_text), meal_label=label, price=price)
    fp = fingerprint(when, order, raw_text,
                     {"name": inscription} if inscription else {})
    score = compose(agg, fp)
    ex = explain(score, agg)
    t = agg["total"]

    audio = audio_name or f"营养旋律_{STYLES[style]['label']}_单餐.wav"
    render(score, audio)

    d = dict(
        schema="nutrition-melody/1.1",
        style=style,
        style_label=STYLES[style]["label"],
        generated_at=when.strftime("%Y-%m-%d %H:%M"),
        input=dict(raw_text=raw_text, order=order, inscription=inscription),
        nutrition=dict(kcal=round(t["kcal"]), p=round(t["p"], 1), f=round(t["f"], 1),
                       c=round(t["c"], 1), na=round(t["na"]), ca=round(t["ca"]),
                       sugar=round(t.get("sugar") if t.get("sugar") is not None
                                   else t["c"] * 0.35, 1),
                       sugar_estimated=t.get("sugar") is None),
        rates={k: round(v, 4) for k, v in ex["rates"].items()},
        music=dict(style=style, bpm=score["bpm"],
                   mode="minor" if score["minor"] else "major",
                   notes=len(score["notes"]),
                   duration=round(sum(n["dur"] for n in score["notes"]), 2),
                   audio=audio),
        headline=ex["headline"],
        mapping=[dict(element=e, value=v, basis=b) for e, v, b in ex["lines"]],
        plain_version=PLAIN_VERSION,
    )
    d["plain"] = plain_text(d)
    return d


if __name__ == "__main__":
    RAW = "我今天吃了板烧、玉米杯和纯牛奶"
    ORDER = ["板烧鸡腿堡", "小杯玉米杯", "纯牛奶（盒装）"]
    WHEN = datetime(2026, 10, 17, 23, 50)
    for st in ("minyue", "jazz", "rock"):
        d = generate(RAW, ORDER, WHEN, style=st, inscription="麦当当", price=47.5, label="午餐")
        tag = STYLES[st]["label"]
        with open(f"旋律说明_{tag}.json", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        with open(f"旋律说明_{tag}_专业版.md", "w", encoding="utf-8") as f:
            f.write(to_markdown_pro(d))
        with open(f"旋律说明_{tag}_大众版.md", "w", encoding="utf-8") as f:
            f.write("# 这顿饭，听起来是什么味道\n\n" + d["plain"] + "\n")
        print(f"[{tag}] {d['headline']}")
