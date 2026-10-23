# -*- coding: utf-8 -*-
"""
营养光谱 · 风格 I 玩具风扩展（toy_render 的姊妹篇）
====================================================
参照太阳光谱图的构图：一条横轴 + 彩虹连续谱 + 峰形能量曲线。

营养 → 光谱的映射关系（每一条都可追溯到官方数值）：

  横轴 = 六种营养素按"严谨分类、同类相邻"排成一条谱带：
        供能区（碳水 → 糖 → 蛋白质 → 脂肪） + 矿物质区（钠 → 钙）
        （糖在学术上属于碳水化合物，归供能区；钠/钙同属矿物质）
  每种营养素占的横向宽度 = 它在这一餐里的"存在感"
        （该营养素总量 / 全日参考值，归一化后分配谱带宽度）
  谱高   = 该营养素相对全日参考值的达成率（100% = 满格线）
  谱色   = 该营养素的"本色"（固定色，横轴连续渐变，像可见光 400-800nm）
  峰形   = 高斯峰叠加，宽度=不确定度（钠的峰最"胖"—— 高钠数字难读）
  太阳   = 这一餐的总能量（573 kcal → 光球大小）

数据（板烧+玉米杯+牛奶）：
  蛋白 32g(53%)  脂肪 25g(36%)  碳水 52g(17%)  糖 ~18g(推算,36%)
  钠 1115mg(56%·全日)  钙 330mg(33%)
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont

W, H = 1400, 1000
SS = 2
F_BLACK = "C:/Windows/Fonts/msyh.ttc"
F_HEAVY = "C:/Windows/Fonts/simhei.ttf"
BG = (255, 243, 226)

# 六种营养素：顺序=谱带从左到右（严谨分类、同类相邻：供能 → 矿物质）
# ref=全日参考值；col=本色；label/en
NUTRIENTS = [
    dict(key="c",  name="碳水",   en="CARB",    ref=300,  col=(255, 160, 64),  peak_w=0.90),
    dict(key="sug",name="糖",     en="SUGAR",   ref=50,   col=(90, 190, 200),  peak_w=0.60),
    dict(key="p",  name="蛋白质", en="PROTEIN", ref=60,   col=(255, 88, 88),   peak_w=0.85),
    dict(key="f",  name="脂肪",   en="FAT",     ref=70,   col=(120, 190, 90),  peak_w=0.80),
    dict(key="na", name="钠",     en="SODIUM",  ref=2000, col=(214, 108, 172), peak_w=0.75),
    dict(key="ca", name="钙",     en="CALCIUM", ref=1000, col=(120, 130, 245), peak_w=0.55),
]


def font(p, s):
    try:
        return ImageFont.truetype(p, s)
    except Exception:
        return ImageFont.truetype(F_BLACK, s)


def _tc(d, xy, s, f, fill, anchor="mm", stroke=0, sf=None):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sf)


def lerp(c1, c2, t):
    return tuple(int(round(a * (1 - t) + b * t)) for a, b in zip(c1, c2))


def spectrum_colors(n=256):
    """谱带本色渐变（按 NUTRIENTS 顺序插值，模拟连续光谱）"""
    stops = [n_["col"] for n_ in NUTRIENTS]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        out.append(lerp(stops[k], stops[k + 1], t - k))
    return out


def render_spectrum(agg: dict, fp: dict, out: str, *, with_pie: bool = False,
                    footer_extra: str = "") -> str:
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img)
    Wc, Hc = W * SS, H * SS
    t = agg["total"]

    # 背景
    for gy in range(0, Hc, 90 * SS):
        for gx in range(0, Wc, 90 * SS):
            ox = (gy // (90 * SS)) % 2 * 45 * SS
            d.ellipse([gx + ox, gy, gx + ox + 26 * SS, gy + 26 * SS], fill=(255, 232, 205))
    img = ImageChops.multiply(
        img, _radial_bg((Wc, Hc), (int(Wc * 0.5), int(Hc * 0.10))))
    d = ImageDraw.Draw(img)

    mode_day = agg.get("mode") == "day"

    # ---------------- 数值准备（含糖推算） ----------------
    sugar = t.get("sugar")
    if sugar is None:
        # 推算：碳水里扣掉"复合碳水"份额。牛奶自带乳糖 10g/盒已计入 sugar 字段的场景。
        # 统一口径：糖 ≈ 饮品自带糖 + 沙拉酱/酱料糖，这里用官方 sugar 字段缺失时按碳水 ×0.35 估（标注为推算）
        sugar = round(t["c"] * 0.35)
        sugar_est = True
    else:
        sugar_est = False
    values = dict(na=t["na"], c=t["c"], p=t["p"], f=t["f"], sug=sugar, ca=t["ca"])

    # 存在感 = 达成率（min(2.0)），归一化分配谱带宽度
    rates = {}
    for n_ in NUTRIENTS:
        rates[n_["key"]] = min(values[n_["key"]] / n_["ref"], 1.6)
    raw = np.array([rates[n_["key"]] for n_ in NUTRIENTS])
    widths = raw / raw.sum()

    # ---------------- 谱区几何 ----------------
    sx0, sx1 = int(0.075 * Wc), int(0.925 * Wc)
    sy_base = int(0.805 * Hc)     # 谱底线（整体下移）
    sy_top = int(0.355 * Hc)      # 100% 线
    sy_full = int(0.425 * Hc)     # 满格线位置
    span = sx1 - sx0

    # 累计每段的 x 区间
    segs = []
    x = sx0
    for n_, wdt in zip(NUTRIENTS, widths):
        w = wdt * span
        segs.append((x, x + w))
        x += w

    # ---------------- 峰形曲线：段中心高度严格=各自达成率 ----------------
    nx = 420
    xs = np.linspace(sx0, sx1, nx)
    centers = np.array([(x0 + x1) / 2 for (x0, x1) in segs])
    center_h = np.array([rates[n_["key"]] for n_ in NUTRIENTS])
    heights = np.zeros(nx)
    for i, xv in enumerate(xs):
        if xv <= centers[0]:
            heights[i] = center_h[0]
        elif xv >= centers[-1]:
            heights[i] = center_h[-1]
        else:
            k = np.searchsorted(centers, xv) - 1
            tt = (xv - centers[k]) / (centers[k + 1] - centers[k])
            tt = 0.5 - 0.5 * math.cos(tt * math.pi)   # 余弦平滑，段中心处恰好=该营养素达成率
            heights[i] = center_h[k] * (1 - tt) + center_h[k + 1] * tt
    # 两端回到低值，形成"山脚"
    edge_drop = 0.30
    left_len = centers[0] - sx0
    right_len = sx1 - centers[-1]
    for i, xv in enumerate(xs):
        if xv < centers[0]:
            tt = xv / max(centers[0] - sx0, 1)
            heights[i] = min(heights[i], center_h[0] * (0.35 + 0.65 * tt))
        if xv > centers[-1]:
            tt = (sx1 - xv) / max(sx1 - centers[-1], 1)
            heights[i] = min(heights[i], center_h[-1] * (0.35 + 0.65 * tt))
    heights = np.clip(heights, 0.04, 1.5)

    def y_of(h):
        return sy_base - h * (sy_base - sy_full)

    # ---------------- 谱底：彩虹条（像 400-800nm 那条彩虹） ----------------
    bar_h = 16 * SS
    spec = spectrum_colors(600)
    step = span / len(spec)
    for i, col in enumerate(spec):
        x0 = sx0 + i * step
        d.rectangle([x0, sy_base, x0 + step + 1, sy_base + bar_h], fill=col)
    d.rectangle([sx0, sy_base, sx1, sy_base + bar_h], outline=(60, 40, 25), width=3 * SS)
    # 波长刻度感：谱带下写营养名
    for (x0, x1), n_ in zip(segs, NUTRIENTS):
        _tc(d, ((x0 + x1) / 2, sy_base + bar_h + 26 * SS), n_["name"],
            font(F_HEAVY, 26 * SS), (60, 40, 25))
        _tc(d, ((x0 + x1) / 2, sy_base + bar_h + 58 * SS),
            f'{values[n_["key"]]:.0f}', font(F_HEAVY, 24 * SS), n_["col"])

    # ---------------- 光谱曲线本体（实心填充 + 彩虹渐变） ----------------
    poly_pts = [(sx0, sy_base)]
    for i, (xv, h) in enumerate(zip(xs, heights)):
        poly_pts.append((xv, y_of(h)))
    poly_pts.append((sx1, sy_base))

    mask = Image.new("L", (Wc, Hc), 0)
    dm = ImageDraw.Draw(mask)
    dm.polygon(poly_pts, fill=255)
    # 渐变填充层：横彩虹 × 纵向亮度
    grad = np.zeros((Hc, Wc, 3), np.uint8)
    for i in range(len(spec)):
        x0 = int(sx0 + i * step)
        x1 = int(sx0 + (i + 1) * step) + 1
        col = spec[i]
        grad[:, x0:x1] = col
    base = np.array(img, dtype=np.float32)
    g = grad.astype(np.float32)
    m = (np.array(mask, dtype=np.float32) / 255.0)[..., None]
    # 顶部更亮，底部仅略暗 → "光从上洒下"，整体鲜艳（定稿亮度）
    lum = np.linspace(1.00, 1.48, Hc)[:, None, None]
    out_arr = (base * (1 - m) + g * lum * m).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(out_arr)
    d = ImageDraw.Draw(img)

    # 曲线描边
    edge = [(xv, y_of(h)) for xv, h in zip(xs, heights)]
    d.line(edge, fill=(255, 255, 255), width=5 * SS)
    d.line(edge, fill=(70, 45, 25), width=2 * SS)

    # ---------------- 满格 100% 参考线 ----------------
    d.line([sx0, sy_full, sx1, sy_full], fill=(170, 120, 90), width=2 * SS)
    for t_ in np.linspace(0, 1, 5):
        xv = sx0 + span * t_
        d.line([xv, sy_full - 6 * SS, xv, sy_full + 6 * SS], fill=(170, 120, 90), width=2 * SS)
    _tc(d, (sx0 - 14 * SS, sy_full), "100%", font(F_HEAVY, 22 * SS), (176, 120, 40), "rm")
    _tc(d, (sx0 - 14 * SS, (sy_full + sy_base) / 2), "达成率", font(F_BLACK, 18 * SS),
        (170, 140, 115), "rm")

    # 分区标签（像 UV / Light / IR）
    zones = [(0, 4, "宏量营养物质 MACRONUTRIENTS"), (4, 6, "微量营养物质 MICRONUTRIENTS")]
    for (i0, i1, lab) in zones:
        x0 = segs[i0][0]
        x1 = segs[i1 - 1][1]
        _tc(d, ((x0 + x1) / 2, int(0.275 * Hc)), lab, font(F_HEAVY, 24 * SS), (150, 115, 85))
        d.line([x0, int(0.295 * Hc), x1, int(0.295 * Hc)], fill=(200, 175, 150), width=2 * SS)

    # 宏量/微量分界虚线（脂肪段与钠段之间），谱带左半落宏量区、右半落微量区
    bxx = segs[4][0]  # 钠段起点 = 宏量区结束处
    _dashed(d, (bxx, int(0.300 * Hc)), (bxx, sy_base), (195, 150, 115), 2 * SS, dash=12)
    d.ellipse([bxx - 4 * SS, int(0.300 * Hc) - 4 * SS, bxx + 4 * SS, int(0.300 * Hc) + 4 * SS],
              fill=(195, 150, 115))

    # ---------------- 峰标注 ----------------
    for (x0, x1), n_ in zip(segs, NUTRIENTS):
        cxx = (x0 + x1) / 2
        idx = int((cxx - sx0) / span * (len(xs) - 1))
        h = heights[idx]
        note = f'{rates[n_["key"]]*100:.0f}%'
        _tc(d, (cxx, y_of(h) - 26 * SS), note, font(F_HEAVY, 26 * SS),
            (255, 255, 255), "mm", stroke=3 * SS, sf=(150, 60, 30))

    # ---------------- 糖的备注（推算） ----------------
    if sugar_est:
        _tc(d, (sx1, sy_base + bar_h + 92 * SS),
            "糖为推算值（碳水×0.35），官方营养库未提供糖字段",
            font(F_BLACK, 18 * SS), (190, 140, 60), "rm")

    # ---------------- 标题 ----------------
    mode_day = agg.get("mode") == "day"
    _tc(d, (int(0.075 * Wc), int(0.075 * Hc)), "NUTRITIONAL SPECTRUM",
        font(F_HEAVY, 24 * SS), (233, 108, 48), "lm")
    _tc(d, (int(0.075 * Wc), int(0.135 * Hc)),
        "我的营养光谱", font(F_HEAVY, 58 * SS), (46, 30, 20), "ls")
    labels_join = " · ".join([u["name"] for u in (agg["meals"] if mode_day else agg["items"])][:4])
    _tc(d, (int(0.075 * Wc), int(0.205 * Hc)),
        labels_join + ("…" if len((agg["meals"] if mode_day else agg["items"])) > 4 else ""),
        font(F_BLACK, 24 * SS), (140, 100, 70), "ls")

    # ---------------- 可选饼图（右下角小窗） ----------------
    if with_pie:
        pr = int(min(Wc, Hc) * 0.095)
        pcx, pcy = int(0.810 * Wc), int(0.150 * Hc)
        mode_day2 = agg.get("mode") == "day"
        units = agg["meals"] if mode_day2 else agg["items"]
        vals = [u["kcal"] for u in units]
        tot_k = sum(vals) or 1
        a = -90.0
        for i_, (u, val) in enumerate(zip(units, vals)):
            span_a = val / tot_k * 360
            col = _unit_color(u, i_)
            d.pieslice([pcx - pr, pcy - pr, pcx + pr, pcy + pr], a, a + span_a, fill=col)
            a += span_a
        d.ellipse([pcx - pr, pcy - pr, pcx + pr, pcy + pr], outline=(160, 160, 160), width=4 * SS)
        cir = int(pr * 0.30)
        d.ellipse([pcx - cir, pcy - cir, pcx + cir, pcy + cir], fill=(255, 253, 246))
        _tc(d, (pcx, pcy - 14 * SS), f'{tot_k:.0f}', font(F_HEAVY, 30 * SS), (48, 32, 20))
        _tc(d, (pcx, pcy + 18 * SS), "kcal", font(F_BLACK, 14 * SS), (150, 110, 80))
        # 右侧说明列：标题 + 图例（按条目数动态垂直居中于饼图）
        col_x = pcx + pr + 20 * SS
        n_leg = min(len(units), 5)
        block_h = 34 * SS + n_leg * 30 * SS          # 标题行 + 图例行
        cy0 = pcy - block_h // 2 + 17 * SS           # 标题基线
        _tc(d, (col_x, cy0), "各菜品能量占比",
            font(F_BLACK, 17 * SS), (150, 115, 85), "lm")
        ly = cy0 + 34 * SS
        for j_, u in enumerate(units[:5]):
            d.ellipse([col_x, ly - 6 * SS, col_x + 12 * SS, ly + 6 * SS],
                      fill=_unit_color(u, j_), outline=(160, 160, 160), width=SS)
            _tc(d, (col_x + 20 * SS, ly), u["name"][:8],
                font(F_BLACK, 15 * SS), (90, 60, 40), "lm")
            ly += 30 * SS

    # ---------------- 落款 ----------------
    try:
        from nutrition_core import describe as _describe
        desc = fp.get("describe") or _describe(fp)
    except Exception:
        desc = fp.get("describe", {})
    name = fp.get("inscription") or ""
    line = "　·　".join(x for x in [name, f'¥{t["price"]:.2f}',
                                   desc.get("时刻", ""), footer_extra] if x)
    _tc(d, (int(0.075 * Wc), int(0.950 * Hc)), line, font(F_BLACK, 20 * SS), (170, 140, 115), "ls")

    im = img.resize((W, H), Image.LANCZOS)
    im.save(out, quality=96)
    return out


def _unit_color(u, idx=None):
    """马卡龙色板：固定不变（按菜品序号取色，同一输入永远同一配色）、高饱和对比"""
    name = u.get("name", "")
    fixed = {"早餐": (247, 166, 125), "午餐": (250, 200, 90), "晚餐": (110, 185, 220),
             "夜宵": (180, 130, 210), "下午": (245, 130, 150)}
    if name in fixed:
        return fixed[name]
    if idx is None:
        idx = 0
    macaron_cycle = [(244, 150, 110), (250, 200, 80), (110, 185, 220),
                     (180, 130, 210), (140, 210, 170), (245, 130, 150)]
    return macaron_cycle[idx % 6]


def _radial_bg(size, center):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - center[0], yy - center[1]) / max(hyp := max(w, h), 1)
    t = np.clip(r ** 1.6, 0, 1)[..., None]
    return Image.fromarray((np.array([255, 255, 244]) * (1 - t) + np.array(BG) * t).astype(np.uint8))


def _dashed(d, p0, p1, fill, width, dash=14):
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(int(L / (dash * 2)), 1)
    for i in range(n):
        t0 = i * 2 * dash / L
        t1 = min((i * 2 + 1) * dash / L, 1)
        d.line([x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0,
                x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1], fill=fill, width=width)
