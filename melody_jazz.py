# -*- coding: utf-8 -*-
"""
S4 营养旋律 · 爵士版（钢琴三重奏 · 欢快/温暖向）
================================================
映射规则沿用 melody_minyue 的营养口径（保证两种曲风可对比）：

  调式     = 钠>80% 且 钙<50% → 转布鲁斯小调；否则保持明亮大调
  BPM      = 96 + 能量达成率 × 30（摇摆中速，与民乐 80+38、摇滚 114+36 拉开）
  引子     = 三甲营养素的"上行三连音 pickup"（弱起抢拍，爵士味）
  乐句     = 六营养素按光谱顺序，每项一句；乐句走向一上一下交替（对话感）
  音高走向 = 达成率 → 骨干音级（高→高音区）
  句长     = 达成率 → 拍数
  结尾     = 钙<50% → 悬置（九音不解决）；钙足 → 落主音
  装饰音   = 指纹决定（爵士用半音倚音 / 蓝调音）
  配器     = 电钢琴主奏（Rhodes 质感）+ 行走贝斯 + 刷鼓（hi-hat）+ 轻爵士和声

设计要点（欢快/温暖）：
  - Swing 8 分音符（长-短 2:1），是爵士"轻快弹跳"的根源
  - 大七和弦、九和弦（Cmaj9 / Fmaj7 / Dm9 / G13），温暖不刺耳
  - 行走贝斯每拍换音，根音→三音→五音→经过音，推进感
  - 刷鼓只做 hi-hat + 轻刷军鼓，不抢主奏
  - 电钢琴带轻微 bell 泛音（tine），比真钢琴更暖
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

# 爵士音阶：大调五声偏爵士（加 9 音），小调用布鲁斯音阶
JAZZ_MAJOR = ["C", "D", "E", "G", "A"]          # 五声（含 9 音感）
JAZZ_BLUES = ["C", "Ds", "F", "Fs", "G", "As"]  # 布鲁斯音阶


def compose(agg: dict, fp: dict) -> dict:
    t = agg["total"]
    sugar = t.get("sugar")
    if sugar is None:
        sugar = round(t["c"] * 0.35)

    nutr = [("碳水", t["c"] / 300), ("糖", sugar / 50), ("蛋白质", t["p"] / 60),
            ("脂肪", t["f"] / 70), ("钠", t["na"] / 2000), ("钙", t["ca"] / 1000)]
    rates = [(n, min(r, 1.6)) for n, r in nutr]

    kcal_rate = min(t["kcal"] / 2000.0, 1.0)
    # 爵士：摇摆中速（比民乐快、比摇滚慢，三种风格听感分开）
    bpm = int(96 + kcal_rate * 30)
    beat = 60.0 / bpm

    na_r = min(t["na"] / 2000.0, 1.6)
    ca_r = min(t["ca"] / 1000.0, 1.6)
    minor = na_r > 0.8 and ca_r < 0.5
    scale = JAZZ_BLUES if minor else JAZZ_MAJOR
    oct0 = 4

    h = fp.get("full") or fp.get("hex") or ""
    orn = int(h[16:20], 16) if len(h) >= 20 else 7

    notes = []
    idx = 0

    # ---------- 引子：三甲营养素的上行三连音 pickup ----------
    INT_STEP = {"碳水": 2, "糖": 3, "蛋白质": 4, "脂肪": 5, "钠": 3, "钙": 5}

    def _fold(d):
        return max(1, min(int(d), 9))

    rank = sorted(rates, key=lambda x: x[1], reverse=True)
    d1 = min(2 + int(min(rank[0][1], 1.2) * 2.5)
             + (0 if kcal_rate < 0.34 else 1 if kcal_rate < 0.5 else 2), 6)
    d2 = _fold(d1 + min(abs(INT_STEP[rank[1][0]]), 2))
    d3 = _fold(d2 + min(abs(INT_STEP[rank[2][0]]), 2))
    # 爵士引子一律上行（弱起上扬），时值取 swing 短-短-长
    for gi, dg in enumerate([d1, d2, d3]):
        notes.append(dict(freq=NOTE_FREQ[f"{scale[dg % len(scale)]}{oct0 + dg // len(scale)}"],
                          dur=beat * (0.30, 0.30, 0.52)[gi], vel=0.40 + 0.04 * gi,
                          orn=False, nutr="引子", swing=True))
    last_deg = d3
    for bi, (name, r) in enumerate(rates):
        dur_beats = (2.6 + min(r, 1.2) * 2.2) if name in ("碳水", "糖", "蛋白质", "脂肪") \
            else (2.4 + r)
        # 爵士句子更碎（切分），音数比民乐多
        n_notes = max(5, int(dur_beats * 2.6))
        base_deg = int(min(r, 1.3) / 1.3 * 8)
        start_deg = last_deg if abs(base_deg - last_deg) <= 3 else (base_deg + last_deg) // 2
        contour = []
        dirn = 1 if bi % 2 == 0 else -1          # 乐句一上一下交替，形成"对话"
        for k in range(n_notes):
            w = math.sin(k / max(n_notes - 1, 1) * math.pi)
            deg = start_deg + (base_deg - start_deg) * (k / max(n_notes - 1, 1)) \
                + dirn * int(w * 2.4)
            deg = max(0, min(int(deg), 9))
            # 爵士切分：弱位（奇数）加跳进，制造"抢拍"感（方向随乐句走）
            if k > 0 and k % 2 == 1:
                deg = max(1, min(deg + dirn * (2 if bi % 2 == 0 else 2), 9))
            contour.append(deg)
        # 句尾处理与民乐相反：上行句上扬、下行句落回，交替出"问-答"
        contour[-1] = min(base_deg + 2, 9) if dirn > 0 else max(base_deg - 2, 0)
        each = dur_beats * beat / n_notes
        for k, deg in enumerate(contour):
            nm = scale[deg % len(scale)]
            freq = NOTE_FREQ[f"{nm}{oct0 + deg // len(scale)}"]
            vel = 0.48 + 0.34 * min(r, 1.0)
            # 爵士重音：反拍（k%4==1/3）重于正拍，这是 swing 的精髓
            if k % 4 in (1, 3):
                vel = min(vel * 1.16, 0.95)
            elif k % 4 == 2:
                vel *= 0.86
            # 装饰音：指纹决定，爵士用半音倚音（bend 感）
            is_orn = ((orn >> (idx % 8)) & 1) == 1 and k in (1, n_notes - 2)
            gap = 0.04
            if is_orn:
                gdeg = min(deg + 1, len(scale) * 2 - 1)
                gfreq = NOTE_FREQ[f"{scale[gdeg % len(scale)]}{oct0 + gdeg // len(scale)}"]
                notes.append(dict(freq=gfreq, dur=each * 0.42, vel=vel * 0.5,
                                  orn=True, nutr=name))
                gap += 0.01
            notes.append(dict(freq=freq, dur=each - gap, vel=vel, orn=False, nutr=name,
                              swing=True))
            last_deg = deg
            idx += 1

    # 结尾：钙<50% → 九音悬置（爵士"未完成"最自然）；钙足 → 落主音
    if ca_r < 0.5:
        # 上行三音接近后停在九音（D），不回落
        tail = [("G", 4), ("A", 4), ("D", 5)]
    else:
        tail = [("D", 5), ("B", 4), ("C", 5)]
    for j, (nm, oc) in enumerate(tail):
        last = (j == len(tail) - 1)
        d = beat * (2.8 if last else 0.9)
        notes.append(dict(freq=NOTE_FREQ[f"{nm}{oc}"], dur=d,
                          vel=0.42 if last else 0.52, orn=False,
                          nutr=("钙(悬置)" if last and ca_r < 0.5 else "钙")))

    return dict(notes=notes, bpm=bpm, minor=minor, rates=dict(rates),
                kcal_rate=kcal_rate, ca_r=ca_r, na_r=na_r, scale=scale, oct0=oct0,
                sugar_est=(t.get("sugar") is None), kcal=t["kcal"], fp_hex=h[:16],
                style="jazz")


def explain(score: dict, agg: dict) -> dict:
    """爵士版编曲说明（结构同民乐版，供 melody_explain 复用）"""
    t = agg["total"]
    r = score["rates"]
    order = ["碳水", "糖", "蛋白质", "脂肪", "钠", "钙"]
    rank = sorted(r.items(), key=lambda x: x[1], reverse=True)
    lines = []

    lines.append(("调式", "爵士大调" if not score["minor"] else "布鲁斯小调",
                  f'钠 {t["na"]:.0f}mg（{r["钠"]*100:.0f}% 全日上限）'
                  + (f'，且钙 {r["钙"]*100:.0f}% 偏低 → 转布鲁斯小调'
                     if score["minor"] else "，未同时触发（钠>80% 且 钙<50%）→ 保持明亮大调")))

    lines.append(("速度与律动", f'{score["bpm"]} BPM · Swing',
                  f'能量 {t["kcal"]:.0f} kcal（占全日 {score["kcal_rate"]*100:.0f}%）：'
                  f'96 + {score["kcal_rate"]*100:.0f}%×30；八分音符按 2:1 摇摆演奏'))

    lines.append(("引子", "上行三连音 pickup（弱起）",
                  f'三甲营养素 {rank[0][0]} {rank[0][1]*100:.0f}%、'
                  f'{rank[1][0]} {rank[1][1]*100:.0f}%、{rank[2][0]} {rank[2][1]*100:.0f}% '
                  f'→ 起音 {min(2 + int(min(rank[0][1], 1.2) * 2.5) + (0 if score["kcal_rate"] < 0.34 else 1 if score["kcal_rate"] < 0.5 else 2), 6)} 级，逐级上行三音抢在正拍前进入；'
                  f'与民乐的"长音下滑引子"、摇滚的"强力和弦点弦引子"完全不同'))

    lines.append(("乐句顺序", " → ".join(order),
                  "与营养光谱同序：" + "，".join(f'{n} {r[n]*100:.0f}%' for n in order if n in r)))

    long_name = max(order, key=lambda n: r.get(n, 0))
    lines.append(("句长", f'{long_name} 句最长',
                  f'{long_name}达成率 {r[long_name]*100:.0f}% 最高 → 句长 = 2.6 + 达成率×2.2 拍'))

    lines.append(("音区", f'{long_name} 句最高',
                  f'骨干音级 = 达成率×8，{long_name} → 音级 {int(min(r[long_name],1.3)/1.3*8)}'))

    lines.append(("重音", "反拍重（swing）",
                  "爵士乐把重音放在弱拍上，制造" + "被推着走" + "的轻盈感；而非正拍下压"))

    lines.append(("和声", "大七 / 九和弦",
                  "温暖不刺耳，比三和弦更有" + "暖光" + "质感；配合电钢琴的 bell 泛音"))

    lines.append(("伴奏", "行走贝斯 + 刷鼓 hi-hat",
                  f'贝斯每拍换音（根→三→五→经过音）推进；刷鼓只铺底不抢主奏'))

    lines.append(("结尾", "上行停在九音，不回落" if score["ca_r"] < 0.5 else "落主音，完整收束",
                  f'钙 {t["ca"]:.0f}mg 仅达 {r["钙"]*100:.0f}%'
                  + ("（<50%）→ 停在九音，爵士里最自然的" + "意犹未尽"
                     if score["ca_r"] < 0.5 else "（≥50%）→ 完整终止")))

    lines.append(("唯一性", f'指纹 {score.get("fp_hex","")}',
                  "半音倚音的插位取自交互指纹，同一餐换个时间吃 → 骨架相同、装饰不同"))
    if score.get("sugar_est"):
        lines.append(("数据说明", "糖为推算值",
                      f'官方营养库无糖字段，按碳水×0.35 推算得 ~{t["c"]*0.35:.0f}g'))

    peak = long_name
    headline = (f'{t["kcal"]:.0f} kcal 的一餐，写成了一首 {score["bpm"]} BPM 的'
                f'{"布鲁斯小调" if score["minor"] else "明亮大调"}爵士三重奏：'
                f'{peak}最突出（{r[peak]*100:.0f}%），'
                + ("钙不足，结尾悬而未决。" if score["ca_r"] < 0.5 else "钙充足，收于主音。"))
    return dict(headline=headline, lines=lines, order=order, rates=r)


# ---------------------------------------------------------------- 爵士音色
def rhodes_tone(freq, dur, vel=0.8):
    """电钢琴（Fender Rhodes）：基音 + 强二泛音（tine 金属感）+ 快衰减 + 钟声余韵"""
    n = max(int(SR * dur), 8)
    tt = np.arange(n) / SR
    ph = 2 * np.pi * freq * tt
    # 基音 + tine 泛音（二、三、四）
    y = (np.sin(ph) * 1.0
         + np.sin(ph * 2) * 0.42
         + np.sin(ph * 3) * 0.14
         + np.sin(ph * 4) * 0.22          # tine 的金属亮感
         + np.sin(ph * 5.4) * 0.05)       # 非谐泛音 → bell 质感
    # 双段包络：撞击快衰减 + 长尾
    env = np.exp(-tt * 3.2) * 0.62 + np.exp(-tt * 0.9) * 0.38
    atk = int(0.004 * SR)
    env[:atk] *= np.linspace(0, 1, atk)
    rel = int(min(0.15, dur * 0.3) * SR)
    if rel > 0:
        env[-rel:] *= np.linspace(1, 0, rel) ** 1.2
    return (y * env * vel * 0.26).astype(np.float32)


def upright_bass_tone(freq, dur, vel=0.55):
    """立式贝斯（pizzicato）：低音厚实，快速起音，短衰减"""
    n = max(int(SR * dur), 8)
    tt = np.arange(n) / SR
    ph = 2 * np.pi * freq * tt
    y = (np.sin(ph) * 1.0 + np.sin(ph * 2) * 0.34
         + np.sin(ph * 3) * 0.14 + np.sin(ph * 4) * 0.05)
    # 拨弦指噪
    rng = np.random.default_rng(int(freq * 71) % 2**31)
    y = y + rng.standard_normal(n) * 0.02 * np.exp(-tt / 0.012)
    env = np.exp(-tt * 2.6)
    atk = int(0.008 * SR)
    env[:atk] *= np.linspace(0, 1, atk)
    rel = int(min(0.08, dur * 0.25) * SR)
    if rel > 0:
        env[-rel:] *= np.linspace(1, 0, rel)
    return (y * env * vel * 0.30).astype(np.float32)


def brush_hat(dur, vel=0.06, accent=False):
    """刷鼓 hi-hat：高频噪声 + 极快衰减"""
    n = max(int(SR * dur), 16)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(int(vel * 1e6) % 2**31)
    noise = rng.standard_normal(n)
    # 简易高通：一阶差分增强高频
    noise = np.diff(noise, prepend=0.0)
    env = np.exp(-tt * (55 if accent else 75))
    return (noise * env * vel).astype(np.float32)


def snare_brush(dur, vel=0.05):
    """刷军鼓（brushed snare）：噪声 + 中频本体"""
    n = max(int(SR * dur), 16)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(int(vel * 2e6) % 2**31)
    y = rng.standard_normal(n) * 0.6 + np.sin(2 * np.pi * 190 * tt) * 0.25
    env = np.exp(-tt * 22)
    atk = int(0.003 * SR)
    env[:atk] *= np.linspace(0, 1, atk)
    return (y * env * vel).astype(np.float32)


def render_jazz(score: dict, out: str) -> str:
    notes = score["notes"]
    total = sum(n["dur"] for n in notes) + 0.8
    buf = np.zeros(int(SR * total), np.float32)
    beat = 60.0 / score["bpm"]
    root_nm = "C" if not score["minor"] else "C"

    # ---------- 和弦进行：每 2 拍一个和弦（ii-V-I 味道），温暖大七/九和弦 ----------
    if score["minor"]:
        chords = [("C", [0, 3, 7, 10]), ("F", [0, 4, 7, 11]),   # Cm7 / Fm7
                  ("G", [0, 4, 7, 10]), ("C", [0, 3, 7, 10])]
    else:
        chords = [("C", [0, 4, 7, 11]), ("A", [0, 3, 7, 10]),   # Cmaj7 / Am7
                  ("F", [0, 4, 7, 11]), ("G", [0, 4, 7, 10])]   # Fmaj7 / G7

    def chord_freqs(root, ivs, octv=3):
        return [NOTE_FREQ[f"{root}{octv}"] * 2 ** (iv / 12) for iv in ivs]

    # ---------- 电钢琴：每 2 拍轻击和弦（comping），反拍进入 ----------
    pos = 0.0
    ci = 0
    mel_end = sum(n["dur"] for n in notes) - beat * 2
    while pos < mel_end:
        root, ivs = chords[ci % len(chords)]
        fs = chord_freqs(root, ivs, 3)
        for vi, f in enumerate(fs[1:]):        # 省略根音（贝斯负责）
            s = int((pos + 0.02 * vi) * SR)    # 轻微滚奏（strum）
            w = rhodes_tone(f, beat * 1.3, 0.26)
            e = min(s + len(w), len(buf))
            if s < len(buf):
                buf[s:e] += w[: e - s]
        pos += beat * 2
        ci += 1

    # ---------- 行走贝斯：每拍换音 根→三→五→经过音 ----------
    patt = [0, 4, 7, 10] if not score["minor"] else [0, 3, 7, 10]
    pos = 0.0
    bi = 0
    while pos < mel_end:
        root, ivs = chords[(bi // 4) % len(chords)]
        deg = patt[bi % 4]
        f = NOTE_FREQ[f"{root}2"] * 2 ** (deg / 12)
        w = upright_bass_tone(f, beat * 0.92, 0.52)
        s = int(pos * SR)
        e = min(s + len(w), len(buf))
        if s < len(buf):
            buf[s:e] += w[: e - s]
        pos += beat
        bi += 1

    # ---------- 刷鼓：hi-hat swing 八分 + 2/4 拍轻军鼓 ----------
    pos = 0.0
    hi = 0
    while pos < mel_end:
        # swing：第 1 个八分占 2/3，第 2 个占 1/3
        for sub, frac in ((0.0, 0.667), (0.667, 0.333)):
            ts = pos + sub * beat
            acc = (sub == 0.0 and hi % 2 == 0)
            w = brush_hat(beat * 0.4, 0.075 if acc else 0.045, acc)
            s = int(ts * SR)
            e = min(s + len(w), len(buf))
            if s < len(buf) and s < e:
                buf[s:e] += w[: e - s]
        # 2、4 拍轻刷军鼓
        if hi % 4 == 1:
            w = snare_brush(beat * 0.5, 0.055)
            s = int(pos * SR)
            e = min(s + len(w), len(buf))
            if s < len(buf):
                buf[s:e] += w[: e - s]
        pos += beat
        hi += 1

    # ---------- 主奏（电钢琴单音，带轻 swing 时值） ----------
    pos = 0.0
    for i, n in enumerate(notes):
        # swing 化：偶数音稍长、奇数音稍短（近似 2:1）
        d = n["dur"] * (1.12 if i % 2 == 0 else 0.86)
        v = n["vel"]
        if n["nutr"] == "钠":
            v = min(v * 1.06, 0.95)
        w = rhodes_tone(n["freq"], d, v)
        s = int(pos * SR)
        e = min(s + len(w), len(buf))
        if s < len(buf):
            buf[s:e] += w[: e - s]
        pos += n["dur"]

    peak = np.max(np.abs(buf)) or 1.0
    buf = buf / peak * 0.88
    out_buf = buf.copy()
    for dly, g in ((int(0.09 * SR), 0.16), (int(0.19 * SR), 0.09)):
        out_buf[dly:] += buf[:-dly] * g
    nz = np.nonzero(np.abs(out_buf) > 0.004)[0]
    if len(nz):
        out_buf = out_buf[: min(len(out_buf), nz[-1] + int(0.32 * SR))]
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
    seen = []
    for n in score["notes"]:
        if n["nutr"] not in seen:
            seen.append(n["nutr"])
    return (f"[爵士] BPM {score['bpm']} · {'布鲁斯小调' if score['minor'] else '大调'} · "
            f"{len(score['notes'])} 音 · 约 {dur:.0f}s\n"
            f"乐句：{' → '.join(seen)}\n"
            f"结尾：{'钙不足 → 停在九音悬置' if score['ca_r'] < 0.5 else '钙充足 → 落主音'}")
