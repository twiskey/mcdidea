# -*- coding: utf-8 -*-
"""
S4 营养旋律引擎 · 民乐版（二胡主奏 · 古筝/竹笛/琵琶配器）
==========================================================
映射规则（每条可追溯到官方营养数值，指纹只影响渲染层）：

  调式     = 钠钙比：钠超标且钙不足 → 小调偏暗；钙充足 → 大调明亮
  BPM      = 能量达成率：80 + rate*38（民乐偏中慢，留出滑音与留白）
  引子     = 三项最突出营养素的音程签名（见 _intro_degs），每餐开头不同
  乐句     = 六营养素按光谱顺序（宏量→微量），每营养素一个乐句
  音高走向 = 各营养素达成率 → 该乐句的骨干音高（达成率高→音区高）
  句长     = 宏量营养素达成率（越高句子越长）
  句尾     = 每句末音下沉二级（民乐"落腔"），与爵士的上扬句尾相反
  结尾     = 钙<50% → 级进滑落到二度悬置；钙足 → 级进落主音
  装饰音   = 指纹 orn 段决定插位（同餐不同时，旋律气质不同）
  配器     = 二胡主旋律（滑音+揉弦+慢起弓）；古筝琶音铺底；竹笛长音点缀
"""
from __future__ import annotations

import math
import wave
import numpy as np

SR = 44100

NOTE_FREQ = {}
_NAMES = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"]
for _oct in range(1, 7):
    for _i, _n in enumerate(_NAMES):
        midi = 12 * (_oct + 1) + _i
        NOTE_FREQ[f"{_n}{_oct}"] = 440.0 * 2 ** ((midi - 69) / 12)

# 五声调式（民乐骨架：宫商角徵羽）
PENTA_MAJOR = ["C", "D", "E", "G", "A"]
PENTA_MINOR = ["C", "D", "Fs", "G", "A"]


def compose(agg: dict, fp: dict) -> dict:
    t = agg["total"]
    sugar = t.get("sugar")
    if sugar is None:
        sugar = round(t["c"] * 0.35)

    nutr = [("碳水", t["c"] / 300), ("糖", sugar / 50), ("蛋白质", t["p"] / 60),
            ("脂肪", t["f"] / 70), ("钠", t["na"] / 2000), ("钙", t["ca"] / 1000)]
    rates = [(n, min(r, 1.6)) for n, r in nutr]

    kcal_rate = min(t["kcal"] / 2000.0, 1.0)
    # 民乐：中慢速，留滑音与留白（与爵士 98+42、摇滚 114+36 明显拉开）
    bpm = int(80 + kcal_rate * 38)
    beat = 60.0 / bpm

    na_r = min(t["na"] / 2000.0, 1.6)
    ca_r = min(t["ca"] / 1000.0, 1.6)
    minor = na_r > 0.8 and ca_r < 0.5
    scale = PENTA_MINOR if minor else PENTA_MAJOR
    oct0 = 4                                   # 二胡音区偏高（D4~D6 常用）

    h = fp.get("full") or fp.get("hex") or ""
    orn = int(h[16:20], 16) if len(h) >= 20 else 7

    notes = []
    idx = 0

    # ---------- 引子：由「最突出的三项营养素」生成音程签名 ----------
    # 每份餐的三甲营养素不同 → 开头的上行/下行音程不同，不再千篇一律从主音起。
    INT_STEP = {"碳水": 2, "糖": 3, "蛋白质": 4, "脂肪": 5, "钠": -3, "钙": 5}

    def _fold(d):                                    # 音级夹在 1~9，越界就贴边（不外翻成八度）
        return max(1, min(int(d), 9))

    rank = sorted(rates, key=lambda x: x[1], reverse=True)
    # 起音 = 第一名达成率（2.5 级/100%）+ 能量档位（0/1/2 级）→ 同结构餐品也能分开
    d1 = min(2 + int(min(rank[0][1], 1.2) * 2.5)
             + (0 if kcal_rate < 0.34 else 1 if kcal_rate < 0.5 else 2), 6)
    d2 = _fold(d1 + INT_STEP[rank[1][0]])            # 第二名决定第一次跳进的方向与幅度
    d3 = _fold(d2 + int(INT_STEP[rank[2][0]] / 2))   # 第三名决定回落深度
    intro = [d1, d2, d3] + ([_fold(d3 + 1)] if kcal_rate >= 0.5 else [])
    for gi, dg in enumerate(intro):
        dd = (1.5, 0.9, 1.2, 0.8)[gi]
        notes.append(dict(freq=NOTE_FREQ[f"{scale[dg % 5]}{oct0 + dg // 5}"],
                          dur=beat * dd, vel=0.44, orn=False, glide=True, nutr="引子"))
    last_deg = intro[-1]
    for bi, (name, r) in enumerate(rates):
        dur_beats = (2.6 + min(r, 1.2) * 2.2) if name in ("碳水", "糖", "蛋白质", "脂肪") \
            else (2.4 + r)
        n_notes = max(4, int(dur_beats * 2))
        # 骨干音级（五声 0..9），并向上一句末音靠拢做"连贯"处理
        base_deg = int(min(r, 1.3) / 1.3 * 8)
        start_deg = last_deg if abs(base_deg - last_deg) <= 3 else (base_deg + last_deg) // 2
        contour = []
        for k in range(n_notes):
            w = math.sin(k / max(n_notes - 1, 1) * math.pi)
            # 民乐以级进为主：拱形幅度收窄到 1 级，避免大跳
            deg = start_deg + (base_deg - start_deg) * (k / max(n_notes - 1, 1)) + int(w * 1.2)
            deg = max(0, min(int(deg), 9))
            # 欢快律动：偶数位加五声音阶跳进（四度/五度），形成"跳音"感
            if k > 0 and k % 2 == 1 and bi % 2 == 0:
                deg = min(deg + 3, 9)
            elif k > 0 and k % 2 == 1:
                deg = max(deg - 2, 1)
            contour.append(deg)
        # 民乐"落腔"：句尾下沉二级落回骨干音，与爵士的上扬句尾形成对比
        contour[-1] = max(base_deg - 2, 0)
        each = dur_beats * beat / n_notes
        for k, deg in enumerate(contour):
            nm = scale[deg % 5]
            freq = NOTE_FREQ[f"{nm}{oct0 + deg // 5}"]
            vel = 0.50 + 0.36 * min(r, 1.0)
            # 欢快版：奇数音稍强（强-弱-强-弱的律动感）
            if k % 4 == 0:
                vel = min(vel * 1.12, 0.95)
            elif k % 4 == 2:
                vel *= 0.88
            # 装饰音：指纹决定，用二胡滑音式短倚音
            is_orn = ((orn >> (idx % 8)) & 1) == 1 and k in (1, n_notes - 2)
            gap = 0.045 if not is_orn else 0.02          # 缩短留白，音符更"连跳"
            if is_orn:
                gdeg = min(deg + 1, 11)
                gfreq = NOTE_FREQ[f"{scale[gdeg % 5]}{oct0 + gdeg // 5}"]
                notes.append(dict(freq=gfreq, dur=each * 0.45, vel=vel * 0.55,
                                  orn=True, nutr=name))
                gap += each * 0.05
            notes.append(dict(freq=freq, dur=each - gap, vel=vel, orn=False, nutr=name,
                              glide=(last_deg != deg) and abs(deg - last_deg) <= 2))
            last_deg = deg
            idx += 1

    # 结尾：级进收束三段式（见配器规划单 ARR-2026-1018-001 第四节）
    # 钙<50% → 徵-角-商（4-3-2）二度悬置；钙足 → 角-商-宫（2-1-0）落主音
    tail = [4, 3, 2] if ca_r < 0.5 else [2, 1, 0]
    for j, dg in enumerate(tail):
        last = (j == len(tail) - 1)
        d = beat * (3.2 if last else 1.1)
        # 末音力度递减至 0.40，不做强收
        v = 0.40 if last else 0.50
        notes.append(dict(freq=NOTE_FREQ[f"{scale[dg % 5]}{oct0 + dg // 5}"],
                          dur=d, vel=v, orn=False, glide=True,
                          nutr=("钙(悬置)" if last and ca_r < 0.5 else "钙")))
    
    return dict(notes=notes, bpm=bpm, minor=minor, rates=dict(rates),
                kcal_rate=kcal_rate, ca_r=ca_r, na_r=na_r, scale=scale, oct0=oct0,
                sugar_est=(t.get("sugar") is None), kcal=t["kcal"], fp_hex=h[:16])


def explain(score: dict, agg: dict) -> dict:
    """把编曲决策逐条翻译成"由哪项营养数据决定"——供成片展示用。
    返回 dict：headline / lines(list of (要素, 取值, 依据)) / outro
    """
    t = agg["total"]
    r = score["rates"]
    rank = sorted(r.items(), key=lambda x: x[1], reverse=True)
    d1 = min(2 + int(min(rank[0][1], 1.2) * 2.5)
             + (0 if score["kcal_rate"] < 0.34 else 1 if score["kcal_rate"] < 0.5 else 2), 6)
    lines = []

    lines.append(("调式", "五声大调" if not score["minor"] else "五声小调",
                  f'钠 {t["na"]:.0f}mg（{r["钠"]*100:.0f}% 全日上限）'
                  + ("" if not score["minor"] else " 且 ") +
                  (f'钙 {t["ca"]:.0f}mg（{r["钙"]*100:.0f}%）偏低 → 转小调'
                   if score["minor"] else "，未达小调阈值（钠>80% 且 钙<50%）→ 保持明亮")))

    lines.append(("速度", f'{score["bpm"]} BPM',
                  f'能量 {t["kcal"]:.0f} kcal（占全日 {score["kcal_rate"]*100:.0f}%）：'
                  f'80 + {score["kcal_rate"]*100:.0f}%×38 = {score["bpm"]}；'
                  f'能量越高越欢快'))

    order = ["碳水", "糖", "蛋白质", "脂肪", "钠", "钙"]
    seq = []
    for nm in order:
        if nm in r:
            seq.append(f'{nm} {r[nm]*100:.0f}%')
    lines.append(("引子", "三音音程签名",
                  f'取达成率最高的三项：{rank[0][0]} {rank[0][1]*100:.0f}%、'
                  f'{rank[1][0]} {rank[1][1]*100:.0f}%、{rank[2][0]} {rank[2][1]*100:.0f}% '
                  f'→ 起音 {d1} 级、按 {rank[1][0]} 的音程跳、按 {rank[2][0]} 回落；'
                  f'开头因此每餐不同'))

    lines.append(("乐句顺序", " → ".join(order), "与营养光谱同序：" + "，".join(seq)))

    # 句长最长者 + 音区最高者
    long_name = max(order, key=lambda n: r.get(n, 0))
    lines.append(("句长", f'{long_name} 句最长',
                  f'{long_name}达成率 {r[long_name]*100:.0f}% 为六项中最高 → '
                  f'句长 = 2.6 + 达成率×2.2 拍，与其正相关'))

    lines.append(("音区", f'{long_name} 句音区最高',
                  f'骨干音级 = 达成率×8，{long_name} {r[long_name]*100:.0f}% → '
                  f'音级 {int(min(r[long_name],1.3)/1.3*8)}；其它营养素按达成率依次排列'))

    lines.append(("力度", f'{long_name} 句最饱满',
                  f'每音力度 0.50 + 0.36×达成率，{long_name} 达 '
                  f'{0.50+0.36*min(r[long_name],1):.2f}，为全曲最高'))

    lines.append(("伴奏", "古筝 2 拍一组琶音 + 梆子打击",
                  f'欢快度由能量决定（{t["kcal"]:.0f} kcal）；'
                  f'强拍重音 0.13 / 中 0.055 / 弱 0.035'))

    lines.append(("结尾", "徵→角→商，二度悬置" if score["ca_r"] < 0.5 else
                  "角→商→宫，落主音收束",
                  f'钙 {t["ca"]:.0f}mg 仅达全日 {r["钙"]*100:.0f}%'
                  + ("（<50%）→ 不解决，留一个" + "缺口" + "感"
                     if score["ca_r"] < 0.5 else "（≥50%）→ 完整终止")))

    lines.append(("唯一性", f'指纹 {score.get("fp_hex","")}',
                  "装饰音插位取自交互指纹，同一餐换个时间吃 → 骨架相同、装饰不同"))
    if score.get("sugar_est"):
        lines.append(("数据说明", "糖为推算值",
                      f'官方营养库无糖字段，按碳水×0.35 推算得 ~{t["c"]*0.35:.0f}g'))

    # 一句话标题（成片大标题下方显示）
    peak_nm = long_name
    headline = (f'{t["kcal"]:.0f} kcal 的一餐，写成了一首 {score["bpm"]} BPM 的'
                f'{"小调" if score["minor"] else "大调"}五声民乐：'
                f'{peak_nm}最突出（{r[peak_nm]*100:.0f}%），'
                + ("钙不足，结尾悬而未决。" if score["ca_r"] < 0.5 else "钙充足，收于主音。"))
    return dict(headline=headline, lines=lines, order=order, rates=r)


# ---------------------------------------------------------------- 民乐音色
def erhu_tone(freq, dur, vel=0.8, glide=True):
    """二胡（欢快版）：鼻音质感 + 轻揉弦 + 快起弓 + 短促弓噪"""
    n = max(int(SR * dur), 8)
    tt = np.arange(n) / SR
    # 揉弦：6.2Hz，幅度减半（欢快时少用长揉）
    vib = 1.0 + 0.0045 * np.sin(2 * np.pi * 6.2 * tt) * np.minimum(tt / 0.15, 1.0)
    # 滑音：起点低 40 音分，20ms 滑入（比慢板更利落）
    if glide:
        slide = 1.0 - 0.040 * np.exp(-tt / 0.022)
        vib = vib * slide
    phase = 2 * np.pi * freq * np.cumsum(vib) / SR
    # 二胡泛音列：奇次谐波强（鼻音）
    y = (np.sin(phase) * 1.0
         + np.sin(phase * 2) * 0.28
         + np.sin(phase * 3) * 0.34
         + np.sin(phase * 5) * 0.14
         + np.sin(phase * 7) * 0.05)
    # 弓噪（马尾擦弦）
    rng = np.random.default_rng(int(freq * 37) % 2**31)
    y = y + rng.standard_normal(n) * 0.007
    # 包络：快起弓 35ms，衰减稍快（跳音感），尾部短回收
    atk = int(0.035 * SR)
    rel = int(min(0.12, dur * 0.28) * SR)
    env = np.ones(n)
    env[:atk] = np.linspace(0, 1, atk) ** 1.2
    if rel > 0:
        env[-rel:] *= np.linspace(1, 0, rel) ** 1.1
    y = y * env * np.exp(-0.45 * tt)
    return (y * vel * 0.30).astype(np.float32)


def guzheng_tone(freq, dur, vel=0.4):
    """古筝：拨弦，快速起音 + 双衰减（金属亮 + 木箱暖）"""
    n = max(int(SR * dur), 8)
    tt = np.arange(n) / SR
    ph = 2 * np.pi * freq * tt
    y = (np.sin(ph) * 1.0 + np.sin(ph * 2) * 0.5 + np.sin(ph * 3) * 0.3
         + np.sin(ph * 4) * 0.18 + np.sin(ph * 6) * 0.08)
    # 拨弦噪声
    rng = np.random.default_rng(int(freq * 91) % 2**31)
    pick = rng.standard_normal(n) * 0.03 * np.exp(-tt / 0.008)
    y = y + pick
    env = np.exp(-tt * 2.2) * 0.7 + np.exp(-tt * 0.7) * 0.3
    atk = int(0.006 * SR)
    env[:atk] *= np.linspace(0, 1, atk)
    return (y * env * vel * 0.25).astype(np.float32)


def dizi_tone(freq, dur, vel=0.3):
    """竹笛：气声 + 明亮泛音 + 轻微颤音"""
    n = max(int(SR * dur), 8)
    tt = np.arange(n) / SR
    vib = 1.0 + 0.005 * np.sin(2 * np.pi * 5.0 * tt) * np.minimum(tt / 0.3, 1)
    phase = 2 * np.pi * freq * np.cumsum(vib) / SR
    y = (np.sin(phase) * 1.0 + np.sin(phase * 2) * 0.35
         + np.sin(phase * 3) * 0.16 + np.sin(phase * 4) * 0.06)
    rng = np.random.default_rng(int(freq * 53) % 2**31)
    y = y + rng.standard_normal(n) * 0.02      # 气声
    atk = int(0.05 * SR)
    rel = int(min(0.15, dur * 0.3) * SR)
    env = np.ones(n)
    env[:atk] = np.linspace(0, 1, atk) ** 1.2
    if rel > 0:
        env[-rel:] *= np.linspace(1, 0, rel)
    return (y * env * vel * 0.20).astype(np.float32)


def perc_tone(dur, vel=0.1, accent=False):
    """梆子/木鱼式打击：短促瞬态 + 木质中频 + 轻微噪声"""
    n = max(int(SR * dur), 16)
    tt = np.arange(n) / SR
    base = 880.0 if accent else 660.0
    y = (np.sin(2 * np.pi * base * tt) * np.exp(-tt * 28)
         + np.sin(2 * np.pi * base * 1.6 * tt) * 0.5 * np.exp(-tt * 38))
    rng = np.random.default_rng(int(base) % 2**31)
    y = y + rng.standard_normal(n) * 0.35 * np.exp(-tt * 90)
    atk = int(0.002 * SR)
    y[:atk] *= np.linspace(0, 1, atk)
    return (y * vel).astype(np.float32)


def render(score: dict, out: str, style: str = "minyue") -> str:
    """乐谱 → wav。style: minyue（二胡主奏+古筝+竹笛+梆子）"""
    notes = score["notes"]
    total = sum(n["dur"] for n in notes) + 0.9
    buf = np.zeros(int(SR * total), np.float32)
    beat = 60.0 / score["bpm"]
    scale = score.get("scale", PENTA_MAJOR)
    oct0 = score.get("oct0", 4)

    if style == "minyue":
        # L2 古筝铺底（欢快版）：每 2 拍一组上行琶音，节奏更密更跳
        pos = 0.0
        bar = 2 * beat
        k = 0
        total_mel = sum(n["dur"] for n in notes)
        gz_end = total_mel - beat
        patterns = [[0, 2, 4], [4, 2, 0], [0, 4, 2], [2, 4, 0]]
        while pos < min(total, gz_end) - 0.6:
            for j, dg in enumerate(patterns[k % 4]):
                nm = scale[dg % 5]
                f = NOTE_FREQ[f"{nm}{oct0 - 1 + dg // 5}"]
                s = int((pos + j * bar / 3) * SR)
                w = guzheng_tone(f, bar / 2.5, 0.26)
                e = min(s + len(w), len(buf))
                if s < len(buf):
                    buf[s:e] += w[: e - s]
            pos += bar
            k += 1
        # L2b 打击乐（欢快感关键）：拍手/梆子，强拍重、弱拍轻
        beat_dur = beat
        ppos = 0.0
        bi2 = 0
        while ppos < min(total, gz_end):
            amp = 0.13 if bi2 % 4 == 0 else (0.055 if bi2 % 2 == 0 else 0.035)
            w = perc_tone(beat_dur * 0.35, amp, bi2 % 4 == 0)
            s = int(ppos * SR)
            e = min(s + len(w), len(buf))
            if s < len(buf):
                buf[s:e] += w[: e - s]
            ppos += beat_dur
            bi2 += 1
        # L3 竹笛点缀：乐句开头长音（高八度），钙段退出
        pos = 0.0
        for i, n in enumerate(notes):
            if i % 9 == 0 and n["vel"] > 0.55 and n["nutr"] not in ("钙", "钙(悬置)"):
                f = n["freq"] * 2
                w = dizi_tone(f, beat * 2.0, 0.16)
                s = int(pos * SR)
                e = min(s + len(w), len(buf))
                if s < len(buf):
                    buf[s:e] += w[: e - s]
            pos += n["dur"]
        # L1 二胡主奏：钠段力度最大，古筝让位（整体压薄）
        pos = 0.0
        for n in notes:
            v = n["vel"]
            if n["nutr"] == "钠":
                v = min(v * 1.08, 0.95)          # 钠段二胡最饱满
            w = erhu_tone(n["freq"], n["dur"], v, glide=n.get("glide", True))
            s = int(pos * SR)
            e = min(s + len(w), len(buf))
            if s < len(buf):
                buf[s:e] += w[: e - s]
            pos += n["dur"]
    else:
        raise ValueError(style)

    peak = np.max(np.abs(buf)) or 1.0
    buf = buf / peak * 0.86
    # 民乐空间感：稍长的房间混响（两段延迟）
    out_buf = buf.copy()
    for dly, g in ((int(0.11 * SR), 0.20), (int(0.23 * SR), 0.12), (int(0.37 * SR), 0.07)):
        out_buf[dly:] += buf[:-dly] * g
    # 裁掉尾部静音（只留 0.35s 混响余韵）
    nz = np.nonzero(np.abs(out_buf) > 0.004)[0]
    if len(nz):
        trim_to = min(len(out_buf), nz[-1] + int(0.35 * SR))
        out_buf = out_buf[:trim_to]
    st = np.stack([out_buf, out_buf], axis=1)
    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    with wave.open(out, "w") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    return out


def score_summary(score: dict) -> str:
    dur = sum(n["dur"] for n in score["notes"])
    lines = [f"BPM {score['bpm']} · {'小调' if score['minor'] else '大调'}五声 · "
             f"共 {len(score['notes'])} 音 · 时长约 {dur:.0f}s"]
    seen = []
    for n in score["notes"]:
        if n["nutr"] not in seen:
            seen.append(n["nutr"])
    lines.append("乐句：" + " → ".join(seen))
    lines.append("结尾：" + ("钙不足 → 级进滑落，二度悬置" if score["ca_r"] < 0.5
                            else "钙充足 → 级进落主音收束"))
    return "\n".join(lines)
