# -*- coding: utf-8 -*-
"""
麦当劳营养肖像 · 数据底座
------------------------
S1 菜单别名表 / 自由文本解析 / 官方 MCP 核价
S2 营养聚合 + 用户指纹

设计原则：
  1. 事实层（营养数值、价格）只由真实数据决定，指纹不参与。
  2. 指纹只决定渲染层（相位、笔触、颜色偏移、印章），保证唯一但不篡改事实。
  3. 不向用户索取任何个人信息，指纹来自这一次交互本身（时间/顺序/措辞）。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ============================================================
# 一、官方单品营养库（来源：官方 MCP list-nutrition-foods 解析值）
#     kcal, P, F, C, Na, Ca 均为官方值；价格优先取 calculate-price 实核
# ============================================================
CATALOG: Dict[str, dict] = {
    # ---- 主食：汉堡 / 卷 ----
    "板烧鸡腿堡":   dict(code="1406",        kcal=391, p=23, f=17, c=35, na=1041, ca=93,  price=23.5, cat="main", color="#8B4513", tone="电钢琴"),
    "麦辣鸡腿汉堡": dict(code="1440",        kcal=485, p=24, f=24, c=42, na=1208, ca=154, price=22.5, cat="main", color="#C1440E", tone="失真吉他"),
    "麦香鸡":       dict(code="1450",        kcal=369, p=15, f=17, c=39, na=731,  ca=73,  price=16.5, cat="main", color="#D9A24A", tone="单簧管"),
    "麦香鱼":       dict(code="1600",        kcal=325, p=16, f=13, c=35, na=556,  ca=99,  price=23.0, cat="main", color="#E8D9A8", tone="长笛"),
    "双层深海鳕鱼堡": dict(code="9900003586", kcal=485, p=28, f=21, c=46, na=917,  ca=147, price=24.5, cat="main", color="#E3C27E", tone="双簧管"),
    "不素之霸双层牛堡": dict(code="4648",      kcal=493, p=28, f=27, c=34, na=1012, ca=75,  price=26.5, cat="main", color="#6B3410", tone="大提琴"),
    "培根蔬萃双层牛堡": dict(code="1106",      kcal=442, p=24, f=23, c=34, na=728,  ca=73,  price=25.0, cat="main", color="#7A3B1E", tone="圆号"),
    "双层吉士汉堡": dict(code="1120",        kcal=429, p=27, f=22, c=31, na=1017, ca=232, price=22.5, cat="main", color="#C98A2E", tone="中提琴"),
    "酥酥多笋卷":   dict(code="521816",      kcal=342, p=14, f=15, c=36, na=1044, ca=41,  price=20.5, cat="main", color="#9C7B3C", tone="巴松"),
    "吉士汉堡":     dict(code="1130",        kcal=298, p=15, f=13, c=30, na=716,  ca=181, price=13.0, cat="main", color="#CE9A3E", tone="口琴"),
    # ---- 小食 ----
    "小杯玉米杯":   dict(code="4437",        kcal=53,  p=2,  f=1,  c=7,  na=1,    ca=6,   price=13.0, cat="side",  color="#F4C430", tone="马林巴"),
    "大杯玉米杯":   dict(code="4438",        kcal=87,  p=4,  f=1,  c=12, na=2,    ca=10,  price=15.5, cat="side",  color="#F0B429", tone="马林巴"),
    "中薯条":       dict(code="4810",        kcal=289, p=4,  f=12, c=38, na=165,  ca=18,  price=14.0, cat="side",  color="#E8B33A", tone="木琴"),
    "大薯条":       dict(code="4811",        kcal=434, p=6,  f=18, c=57, na=248,  ca=27,  price=17.0, cat="side",  color="#E8A83A", tone="木琴"),
    "苹果片":       dict(code="6102",        kcal=32,  p=0,  f=0,  c=7,  na=0,    ca=18,  price=7.0,  cat="side",  color="#9BC24A", tone="钢片琴"),
    "麦乐鸡5块":    dict(code="1401",        kcal=213, p=12, f=12, c=13, na=422,  ca=9,   price=14.0, cat="side",  color="#C99A56", tone="钢片琴"),
    "脆薯饼":       dict(code="521741",      kcal=146, p=1,  f=9,  c=14, na=311,  ca=7,   price=8.0,  cat="side",  color="#D9A24A", tone="铃鼓"),
    "麦旋风":       dict(code="522050",      kcal=285, p=5,  f=10, c=43, na=125,  ca=140, price=15.0, cat="side",  color="#F2E6D0", tone="竖琴"),
    # ---- 饮品 ----
    "纯牛奶（盒装）": dict(code="3755",      kcal=129, p=7,  f=7,  c=10, na=73,   ca=231, price=11.0, cat="drink", color="#F7F3E8", tone="长笛"),
    "热牛奶中杯":   dict(code="507394",      kcal=176, p=10, f=8,  c=15, na=101,  ca=319, price=19.0, cat="drink", color="#FBF6EA", tone="弦乐"),
    "可乐中杯":     dict(code="3061",        kcal=147, p=0,  f=0,  c=36, na=0,    ca=10,  price=10.0, cat="drink", color="#4A1E10", tone="贝斯"),
    "雪碧中杯":     dict(code="3060",        kcal=105, p=0,  f=0,  c=26, na=29,   ca=0,   price=10.0, cat="drink", color="#7FC9A8", tone="钟琴"),
    "100%苹果汁":   dict(code="6362",        kcal=88,  p=0,  f=0,  c=21, na=0,    ca=0,   price=12.0, cat="drink", color="#E0A63A", tone="颤音琴"),
    "锡兰红茶":     dict(code="3505",        kcal=2,   p=0,  f=0,  c=0,  na=0,    ca=5,   price=11.0, cat="drink", color="#8C4A1E", tone="木吉他"),
    "阳光柠檬红茶中杯": dict(code="515281",  kcal=117, p=0,  f=0,  c=29, na=17,   ca=0,   price=10.0, cat="drink", color="#E3B23A", tone="颤音琴"),
    "中杯怡泉+C":   dict(code="515520",      kcal=110, p=0,  f=0,  c=27, na=0,    ca=0,   price=11.5, cat="drink", color="#E8D04A", tone="钟琴"),
}

# ============================================================
# 二、S1 别名表：把用户怎么说话，映射到官方单品名
#     顺序重要：更具体的别名必须排在更泛的前面
# ============================================================
ALIASES: List[Tuple[str, str]] = [
    # 汉堡
    ("培根蔬萃双层牛堡", "培根蔬萃双层牛堡"), ("培根蔬萃", "培根蔬萃双层牛堡"),
    ("蔬萃", "培根蔬萃双层牛堡"),
    ("不素之霸", "不素之霸双层牛堡"), ("双层牛堡", "不素之霸双层牛堡"),
    ("双层鳕鱼", "双层深海鳕鱼堡"), ("鳕鱼堡", "双层深海鳕鱼堡"),
    ("板烧", "板烧鸡腿堡"), ("鸡腿堡", "板烧鸡腿堡"),
    ("麦辣", "麦辣鸡腿汉堡"), ("辣鸡腿", "麦辣鸡腿汉堡"),
    ("麦香鱼", "麦香鱼"), ("鱼堡", "麦香鱼"),
    ("双层吉士", "双层吉士汉堡"), ("吉士汉堡", "双层吉士汉堡"),
    ("吉士", "吉士汉堡"),
    ("麦香鸡", "麦香鸡"),
    ("笋卷", "酥酥多笋卷"), ("卷", "酥酥多笋卷"),
    # 小食
    ("大玉米", "大杯玉米杯"), ("大杯玉米", "大杯玉米杯"),
    ("玉米", "小杯玉米杯"), ("粟米", "小杯玉米杯"),
    ("大薯", "大薯条"), ("大份薯条", "大薯条"),
    ("中薯", "中薯条"), ("薯条", "中薯条"),
    ("苹果片", "苹果片"), ("苹果", "苹果片"),
    ("麦乐鸡", "麦乐鸡5块"), ("鸡块", "麦乐鸡5块"),
    ("薯饼", "脆薯饼"), ("脆薯", "脆薯饼"),
    ("麦旋风", "麦旋风"), ("奥利奥", "麦旋风"),
    # 饮品
    ("盒装纯牛奶", "纯牛奶（盒装）"), ("纯牛奶", "纯牛奶（盒装）"),
    ("盒装牛奶", "纯牛奶（盒装）"), ("牛奶", "纯牛奶（盒装）"),
    ("热牛奶", "热牛奶中杯"), ("热牛", "热牛奶中杯"),
    ("可乐", "可乐中杯"), ("肥宅水", "可乐中杯"),
    ("雪碧", "雪碧中杯"),
    ("苹果汁", "100%苹果汁"), ("果汁", "100%苹果汁"),
    ("锡兰", "锡兰红茶"), ("红茶", "锡兰红茶"),
    ("柠檬茶", "阳光柠檬红茶中杯"), ("怡泉", "中杯怡泉+C"),
]

# 数量词
CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
          "八": 8, "九": 9, "十": 10}

# 分隔与噪音
SPLIT_RE = re.compile(r"[、,，;；+＋\n]|还有|再加|以及|配了|点了|再来|加|和|配")
STOPWORDS = ["我今天吃了", "我吃了", "今天吃了", "我点了", "点了", "吃了", "我要了",
             "麦当劳", "麦记", "午饭", "午餐", "晚饭", "早餐", "夜宵", "一共", "总共",
             "大概", "左右", "然后", "另外", "还有", "外加", "配", "搭", "一份", "一个", "一杯"]

QTY_RE = re.compile(r"([0-9]+|[一两二三四五六七八九十])\s*(份|个|杯|盒|块|只)?")


@dataclass
class Item:
    name: str
    qty: int
    kcal: float
    p: float
    f: float
    c: float
    na: float
    ca: float
    price: float
    color: str
    tone: str
    cat: str
    code: str
    raw: str = ""
    price_verified: bool = False


@dataclass
class Parsed:
    items: List[Item] = field(default_factory=list)
    unmatched: List[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def total(self) -> dict:
        t = dict(kcal=0.0, p=0.0, f=0.0, c=0.0, na=0.0, ca=0.0, price=0.0)
        for i in self.items:
            for k in ("kcal", "p", "f", "c", "na", "ca", "price"):
                t[k] += getattr(i, k)
        return t


def _clean(seg: str) -> str:
    s = seg.strip()
    for w in sorted(STOPWORDS, key=len, reverse=True):
        s = s.replace(w, "")
    return re.sub(r"^[的了\s]+|[的了\s]+$", "", s.strip())


def _match_one(seg: str) -> List[Tuple[str, int]]:
    """在一段文本里找出全部 (单品, 数量)。多字别名优先；匹配后从原文剔除再继续找。"""
    rest = seg
    found: List[Tuple[str, int]] = []
    guard = 0
    while guard < 8:
        guard += 1
        qty = 1
        m = QTY_RE.search(rest)
        if m:
            q = m.group(1)
            qty = int(q) if q.isdigit() else CN_NUM.get(q, 1)
            rest = rest[:m.start()] + "|" + rest[m.end():]
        cleaned = _clean(rest)
        if not cleaned:
            break
        hit = None
        for alias, name in sorted(ALIASES, key=lambda x: -len(x[0])):
            if alias in cleaned:
                hit = (alias, name)
                break
        if hit is None:
            break
        found.append((hit[1], qty))
        rest = cleaned.replace(hit[0], "|", 1)
    return found


def parse(text: str) -> Parsed:
    """自由文本 → 单品清单。匹配不到的不猜，进 unmatched。"""
    p = Parsed(raw_text=text)
    merged: Dict[str, int] = {}
    order: List[str] = []
    for seg in SPLIT_RE.split(text):
        if not seg or not seg.strip():
            continue
        hits = _match_one(seg)
        if not hits:
            c = _clean(seg)
            if c and len(c) >= 1:
                p.unmatched.append(c)
            continue
        for name, qty in hits:
            if name not in merged:
                order.append(name)
                merged[name] = 0
            merged[name] += qty
    for name in order:
        d = CATALOG[name]
        q = merged[name]
        p.items.append(Item(
            name=name, qty=q,
            kcal=d["kcal"] * q, p=d["p"] * q, f=d["f"] * q, c=d["c"] * q,
            na=d["na"] * q, ca=d["ca"] * q, price=d["price"] * q,
            color=d["color"], tone=d["tone"], cat=d["cat"], code=d["code"],
        ))
    return p


# ============================================================
# 三、S2 营养聚合 + 派生指标
# ============================================================
# 参考值（15 岁，全日 DRIs）
REF = dict(kcal=2250, p=60, f=70, c=300, na_cap=2000, na_lunch=600, ca=1000)


def aggregate(p: Parsed, meal_label: str = "一餐", price: Optional[float] = None) -> dict:
    t = p.total
    if price is not None:
        t["price"] = float(price)
    kcal = max(t["kcal"], 1e-6)
    # 供能比（Atwater）
    e_p, e_f, e_c = t["p"] * 4, t["f"] * 9, t["c"] * 4
    e_sum = max(e_p + e_f + e_c, 1e-6)
    shares = []
    for i in p.items:
        shares.append(dict(name=i.name, qty=i.qty, kcal=i.kcal,
                           share=i.kcal / kcal if kcal else 0,
                           color=i.color, tone=i.tone, cat=i.cat,
                           na=i.na, ca=i.ca, p=i.p, f=i.f, c=i.c,
                           price=i.price, code=i.code))
    return dict(
        label=meal_label,
        items=shares,
        total=t,
        share_p=e_p / e_sum, share_f=e_f / e_sum, share_c=e_c / e_sum,
        p_rate=t["p"] / REF["p"],
        ca_rate=t["ca"] / REF["ca"],
        kcal_rate=t["kcal"] / REF["kcal"],
        na_ratio=t["na"] / max(t["ca"], 1),          # 钠钙比：咸与淡的分界
        na_over=t["na"] / REF["na_lunch"],           # 相对午餐建议值的倍数
        na_note=(f'午饭建议的 {t["na"]/REF["na_lunch"]:.1f} 倍'),
        n_items=len(p.items),
        mode="meal",
    )


# 餐次关键词（顺序重要：更具体的放前面）
MEAL_KEYS = [
    ("早餐", ["早餐", "早饭", "早上", "早晨", "morning"]),
    ("午餐", ["午餐", "午饭", "中午", "午饭", "lunch"]),
    ("下午", ["下午茶", "下午", "加餐", "零食"]),
    ("晚餐", ["晚餐", "晚饭", "晚上", "傍晚", "dinner"]),
    ("夜宵", ["夜宵", "宵夜", "深夜", "半夜"]),
]


def split_meals(text: str) -> List[Tuple[Optional[str], str]]:
    """把一天的原话切成 [(餐次名, 该餐文本)]。识别不到餐次就整体当一餐。"""
    hits = []
    for label, keys in MEAL_KEYS:
        for k in keys:
            for m in re.finditer(k, text):
                hits.append((m.start(), label))
    hits.sort()
    # 去掉重叠（同一位置被多个关键词命中，保留更靠前的）
    dedup = []
    for pos, lab in hits:
        if dedup and pos - dedup[-1][0] < 2:
            continue
        dedup.append((pos, lab))
    if not dedup:
        return [(None, text)]
    out = []
    for idx, (pos, lab) in enumerate(dedup):
        end = dedup[idx + 1][0] if idx + 1 < len(dedup) else len(text)
        chunk = text[pos:end]
        out.append((lab, chunk))
    return out


def day_aggregate(segs: List[Tuple[str, Parsed]],
                  price: Optional[float] = None,
                  day_label: str = "饮食日谱") -> dict:
    """多餐合并成一天的日谱：每个餐次成为一个"峰"。"""
    meal_units = []
    tot = dict(kcal=0.0, p=0.0, f=0.0, c=0.0, na=0.0, ca=0.0, price=0.0)
    n_items = 0
    for label, parsed in segs:
        a = aggregate(parsed, label or "一餐")
        mt = a["total"]
        for k in tot:
            tot[k] += mt[k]
        n_items += len(parsed.items)
        meal_units.append(dict(
            name=label or "一餐", total=mt, kcal=mt["kcal"],
            p=mt["p"], f=mt["f"], c=mt["c"], na=mt["na"], ca=mt["ca"],
            color=a["items"][0]["color"] if a["items"] else "#E8B44A",
            items=a["items"],
            na_note=a["na_note"],
        ))
    if price is not None:
        tot["price"] = float(price)
    kcal = max(tot["kcal"], 1e-6)
    e_p, e_f, e_c = tot["p"] * 4, tot["f"] * 9, tot["c"] * 4
    e_sum = max(e_p + e_f + e_c, 1e-6)
    return dict(
        label=day_label, meals=meal_units, total=tot,
        share_p=e_p / e_sum, share_f=e_f / e_sum, share_c=e_c / e_sum,
        p_rate=tot["p"] / REF["p"], ca_rate=tot["ca"] / REF["ca"],
        kcal_rate=tot["kcal"] / REF["kcal"],
        na_ratio=tot["na"] / max(tot["ca"], 1),
        na_over=tot["na"] / REF["na_cap"],
        na_note=f'全日上限的 {tot["na"]/REF["na_cap"]:.1f} 倍',
        n_items=n_items, n_meals=len(meal_units), mode="day",
    )


# ============================================================
# 四、S2 用户指纹：只取这一次交互本身，不问隐私
# ============================================================
def fingerprint(when: datetime, order: List[str], raw_text: str,
                custom: Optional[dict] = None) -> dict:
    """交互指纹 + 自选元素 → 64 位标识。

    同样一份餐在别的时刻吃，笔迹会变；事实数值不会变。
    custom 支持：name(名字) / number(数字或手机尾号) / color(十六进制色)
    """
    custom = custom or {}
    custom_str = "|".join(f"{k}={v}" for k, v in sorted(custom.items()) if v not in (None, ""))
    payload = f"{when.isoformat(timespec='minutes')}|{'/'.join(order)}|{raw_text.strip()}|{custom_str}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def seg(a, b):
        return int(h[a:b], 16)

    # 铭文：优先用名字；没有名字用数字
    inscription = custom.get("name") or (f'№{custom["number"]}' if custom.get("number") else "")
    # 自选数字额外驱动相位，让"这个数字"真的改变画面纹理
    num_phase = (int(re.sub(r"\D", "", str(custom.get("number", "0"))) or 0) % 1000) / 1000.0

    return dict(
        hex=h[:16].upper(),
        full=h,
        payload=payload,
        custom=custom,
        inscription=inscription,
        color=custom.get("color"),
        phase=(seg(0, 8) / 0xFFFFFFFF + num_phase) % 1.0,
        grain=seg(8, 16) / 0xFFFFFFFF,
        hue_shift=(seg(16, 24) / 0xFFFFFFFF - 0.5) * 6.0,
        strokes=6 + seg(24, 32) % 7,
        orn=seg(32, 48) / 0xFFFFFFFF,
        hour=when.hour,
        when=when.strftime("%Y-%m-%d %H:%M"),
        order=order,
        iv=seg(48, 52),
    )


def seal_svg(fp: dict, size: int = 88) -> str:
    """把指纹画成一枚极简几何印章（36 条线里取 9 条，命中即实）。"""
    bits = [(fp["iv"] >> k) & 1 for k in range(9)]
    cell = size / 3
    lines = []
    for r in range(3):
        for c in range(3):
            if bits[r * 3 + c]:
                lines.append(f'<rect x="{c*cell:.2f}" y="{r*cell:.2f}" '
                             f'width="{cell:.2f}" height="{cell:.2f}" fill="currentColor"/>')
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
            f'xmlns="http://www.w3.org/2000/svg">{"".join(lines)}</svg>')


def describe(fp: dict) -> dict:
    """把指纹翻译成人能读的说明（给作品附注用）。"""
    h = fp["hour"]
    return {
        "指纹": fp["hex"],
        "时刻": fp["when"],
        "时段": ("深夜" if h >= 21 or h < 5 else
                 "清晨" if h < 9 else
                 "白天" if h < 18 else "傍晚"),
        "顺序": " → ".join(fp["order"]),
        "笔触数": fp["strokes"],
        "铭文": fp.get("inscription", ""),
    }


# ============================================================
if __name__ == "__main__":
    demo = "我今天吃了板烧、玉米杯和纯牛奶"
    r = parse(demo)
    print(json.dumps([x.name for x in r.items], ensure_ascii=False),
          "unmatched:", r.unmatched)
    a = aggregate(r, "晚餐")
    print(json.dumps({k: round(v, 3) for k, v in a["total"].items()}, ensure_ascii=False))
    print("供能比 P/F/C:", round(a["share_p"], 3), round(a["share_f"], 3), round(a["share_c"], 3))
    print("钠钙比:", round(a["na_ratio"], 2))
    fp = fingerprint(datetime(2026, 10, 17, 22, 43), [x.name for x in r.items], demo)
    print(json.dumps(describe(fp), ensure_ascii=False))
