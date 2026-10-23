# -*- coding: utf-8 -*-
"""
S4 营养旋律 · 摇滚版（电吉他 + 贝斯 + 鼓组 · 欢快积极向 pop-rock）
================================================================
营养映射口径与民乐/爵士同源（调式/BPM/句序/句长/音区/力度/结尾/装饰音），
但旋律形态刻意做得不一样：

  速度     = 114 + 能量达成率×36（三曲风里最快；民乐 80+38r、爵士 96+30r）
  引子     = 根音 + 四度的强力和弦点弦两下，切分切入
  主句     = riff 循环 0-2-3-2（根-三度-四度-三度），句句转位、句尾落回根音
  配器     = 电吉他主奏（过载失真，八分音符强力和弦 riff）+ 电贝斯（八度跟拍）
             + 鼓组（kick 四踩 + snare 2/4 + 开镲重拍）
  律动     = 正拍下压（与爵士的反拍 swing 相反），每拍都有颗粒感
  和声     = 强力和弦（power chord，根+五），干脆有力，不带阴郁小和弦
  结尾     = 钙<50% → 上扬停在二音不解决（摇滚"悬着"的经典手法）；钙足 → 落主音
  装饰音   = 指纹决定 → 电吉他 bend（推弦）式短倚音
"""
from __future__ import annotations

import wave
import numpy as np

SR = 44100

NOTE_FREQ = {}
_NAMES = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"]
for _oct in range(1, 7):
    for _i, _n in enumerate(_NAMES):
        midi = 12 * (_oct + 1) + _i
        NOTE_FREQ[f"{_n}{_oct}"] = 440.0 * 2 ** ((midi - 69) / 12)

# 大调五声（欢快摇滚的常用骨架）
ROCK_MAJOR = ["C", "D", "E", "G", "A"]
ROCK_BLUES = ["C", "Ds", "F", "Fs", "G", "As"]


def compose(agg: dict, fp: dict) -> dict:
    t = agg["total"]
    sugar = t.get("sugar")
    if sugar is None:
        sugar = round(t["c"] * 0.35)

    nutr = [("碳水", t["c"] / 300), ("糖", sugar / 50), ("蛋白质", t["p"] / 60),
            ("脂肪", t["f"] / 70), ("钠", t["na"] / 2000), ("钙", t["ca"] / 1000)]
    rates = [(n, min(r, 1.6)) for n, r in nutr]

    kcal_rate = min(t["kcal"] / 2000.0, 1.0)
    # 摇滚：最快（与民乐 80+38、爵士 96+30 拉开差距）
    bpm = int(114 + kcal_rate * 36)
    beat = 60.0 / bpm

    na_r = min(t["na"] / 2000.0, 1.6)
    ca_r = min(t["ca"] / 1000.0, 1.6)
    minor = na_r > 0.8 and ca_r < 0.5
    scale = ROCK_BLUES if minor else ROCK_MAJOR
    oct0 = 4

    h = fp.get("full") or fp.get("hex") or ""
    orn = int(h[16:20], 16) if len(h) >= 20 else 7

    notes = []
    idx = 0

    # ---------- 引子：强力和弦式点弦（根音 + 五音，两下） ----------
    rank = sorted(rates, key=lambda x: x[1], reverse=True)
    d1 = min(2 + int(min(rank[0][1], 1.2) * 2.5)
             + (0 if kcal_rate < 0.34 else 1 if kcal_rate < 0.5 else 2), 6)
    d5 = min(d1 + 3, 7)                             # 根 + 四度（限制在八度内，便于接主句）
    for gi, dg in enumerate([d1, d5, d1] if kcal_rate < 0.5 else [d1, d5, d1, d5]):
        notes.append(dict(freq=NOTE_FREQ[f"{scale[dg % len(scale)]}{oct0 + dg // len(scale)}"],
                          dur=beat * 0.42, vel=0.62 if gi % 2 == 0 else 0.50,
                          orn=False, nutr="引子"))
    last_deg = d5
    for bi, (name, r) in enumerate(rates):
        dur_beats = (2.6 + min(r, 1.2) * 2.2) if name in ("碳水", "糖", "蛋白质", "脂肪") \
            else (2.4 + r)
        n_notes = max(5, int(dur_beats * 2.4))
        base_deg = int(min(r, 1.3) / 1.3 * 8)
        # 摇滚 riff：以骨干音为根，0-2-3-2 循环（根-三度-四度-三度），句句如此转位
        contour = []
        riff = (0, 2, 3, 2)
        # 首句往引子末音靠拢，避免引子与主句之间出现八度大跳
        root = max(1, min(int((base_deg * 2 + last_deg) / 3) if bi == 0 else base_deg, 7))
        for k in range(n_notes):
            contour.append(min(root + riff[k % 4], 9))
        # 句尾回到根音（riff 收在根音上，颗粒感整齐）
        contour[-1] = root
        each = dur_beats * beat / n_notes
        for k, deg in enumerate(contour):
            nm = scale[deg % len(scale)]
            freq = NOTE_FREQ[f"{nm}{oct0 + deg // len(scale)}"]
            vel = 0.52 + 0.34 * min(r, 1.0)
            # 正拍重音（摇滚与爵士相反）
            if k % 4 == 0:
                vel = min(vel * 1.15, 0.97)
            elif k % 4 == 2:
                vel *= 0.90
            # 装饰音：指纹决定，推弦式（上弯半音）
            is_orn = ((orn >> (idx % 8)) & 1) == 1 and k in (1, n_notes - 2)
            gap = 0.035
            if is_orn:
                gfreq = freq * 1.06                      # 半音上弯
                notes.append(dict(freq=gfreq, dur=each * 0.4, vel=vel * 0.55,
                                  orn=True, nutr=name, bend=True))
                gap += 0.01
            notes.append(dict(freq=freq, dur=each - gap, vel=vel, orn=False, nutr=name))
            last_deg = deg
            idx += 1

    # 结尾：钙<50% → 上行停在二音（悬置但不阴郁）；钙足 → 落主音
    if ca_r < 0.5:
        tail = [(4, oct0), (0, oct0 + 1)]                # 徵 → 高宫，停在二度感
    else:
        tail = [(2, oct0), (0, oct0)]                    # 角 → 宫，解决
    for j, (dg, oc) in enumerate(tail):
        last = (j == len(tail) - 1)
        d = beat * (2.6 if last else 0.9)
        notes.append(dict(freq=NOTE_FREQ[f"{scale[dg % len(scale)]}{oc}"],
                          dur=d, vel=0.46 if last else 0.55, orn=False,
                          nutr=("钙(悬置)" if last and ca_r < 0.5 else "钙")))

    return dict(notes=notes, bpm=bpm, minor=minor, rates=dict(rates),
                kcal_rate=kcal_rate, ca_r=ca_r, na_r=na_r, scale=scale, oct0=oct0,
                sugar_est=(t.get("sugar") is None), kcal=t["kcal"], fp_hex=h[:16],
                style="rock")


def explain(score: dict, agg: dict) -> dict:
    t = agg["total"]
    r = score["rates"]
    order = ["碳水", "糖", "蛋白质", "脂肪", "钠", "钙"]
    rank = sorted(r.items(), key=lambda x: x[1], reverse=True)
    lines = []

    lines.append(("调式", "摇滚大调" if not score["minor"] else "布鲁斯摇滚",
                  f'钠 {t["na"]:.0f}mg（{r["钠"]*100:.0f}%）'
                  + (f'，且钙 {r["钙"]*100:.0f}% 偏低 → 布鲁斯摇滚'
                     if score["minor"] else "，未同时触发 → 保持明亮大调")))

    lines.append(("速度", f'{score["bpm"]} BPM',
                  f'能量 {t["kcal"]:.0f} kcal（占全日 {score["kcal_rate"]*100:.0f}%）：'
                  f'114 + {score["kcal_rate"]*100:.0f}%×36，三曲风里最快'))

    lines.append(("引子", "强力和弦点弦（根 + 五）",
                  f'三甲营养素 {rank[0][0]} {rank[0][1]*100:.0f}%、'
                  f'{rank[1][0]} {rank[1][1]*100:.0f}%、{rank[2][0]} {rank[2][1]*100:.0f}% '
                  f'→ riff 起点 {min(2 + int(min(rank[0][1], 1.2) * 2.5) + (0 if score["kcal_rate"] < 0.34 else 1 if score["kcal_rate"] < 0.5 else 2), 6)} 级，根-五交替两下切入'))

    lines.append(("乐句顺序", " → ".join(order),
                  "与营养光谱同序：" + "，".join(f'{n} {r[n]*100:.0f}%' for n in order if n in r)))

    long_name = max(order, key=lambda n: r.get(n, 0))
    lines.append(("句长", f'{long_name} 句最长',
                  f'{long_name}达成率 {r[long_name]*100:.0f}% 最高 → 句长 = 2.6 + 达成率×2.2 拍'))

    lines.append(("音区", f'{long_name} 句最高',
                  f'骨干音级 = 达成率×8，且每句后半段整体上顶 2 级（推气氛）'))

    lines.append(("重音", "正拍重（四踩驱动）",
                  "摇滚与爵士相反：重音落正拍，底鼓每拍都踩，颗粒感强"))

    lines.append(("和声", "强力和弦 Power Chord",
                  "根音+五音，无三音 → 干脆有力，不存在阴郁的大小调色彩，天然积极"))

    lines.append(("配器", "重失真电吉他 + 电贝斯 + 加重鼓组",
                  f'吉他双轨失谐强失真 chug，贝斯八度顶+半音经过音，鼓组双踩+每2小节军鼓填充'))

    lines.append(("结尾", "上行停在二音，不解决" if score["ca_r"] < 0.5 else "落主音，完整收束",
                  f'钙 {t["ca"]:.0f}mg 仅达 {r["钙"]*100:.0f}%'
                  + ("（<50%）→ 上扬悬置（摇滚里" + "想继续" + "的手法），不阴郁"
                     if score["ca_r"] < 0.5 else "（≥50%）→ 完整终止")))

    lines.append(("唯一性", f'指纹 {score.get("fp_hex","")}',
                  "推弦式倚音的插位取自交互指纹，同一餐换个时间吃 → 骨架相同、装饰不同"))
    if score.get("sugar_est"):
        lines.append(("数据说明", "糖为推算值",
                      f'官方营养库无糖字段，按碳水×0.35 推算得 ~{t["c"]*0.35:.0f}g'))

    peak = long_name
    headline = (f'{t["kcal"]:.0f} kcal 的一餐，写成了一首 {score["bpm"]} BPM 的'
                f'摇滚：{peak}最突出（{r[peak]*100:.0f}%），'
                + ("钙不足，结尾上扬悬着。" if score["ca_r"] < 0.5 else "钙充足，收于主音。"))
    return dict(headline=headline, lines=lines, order=order, rates=r)


# ---------------------------------------------------------------- 摇滚音色
def _soft_clip(x, drive=3.0):
    """软削波 = 过载失真"""
    return np.tanh(x * drive) / np.tanh(drive)


def guitar_power(freq, dur, vel=0.7):
    """过载电吉他（重版）：双锯齿失谐加大 + 强失真 + 密集低通 chug 感"""
    n = max(int(SR * dur), 8)
    tt = np.arange(n) / SR
    ph = 2 * np.pi * freq * tt
    # 两把吉他，失谐 0.6%（更宽的墙）
    saw = 2 * ((ph / (2 * np.pi)) % 1.0) - 1.0
    det = 2 * (((ph * 1.006) / (2 * np.pi)) % 1.0) - 1.0
    y = saw + det
    y = _soft_clip(y, 7.5)                 # 失真加深（4.5 → 7.5）
    # 箱体感：低通略收窄，突出中频冲劲
    kernel = np.ones(9) / 9
    y = np.convolve(y, kernel, mode="same")
    y = y + 0.22 * np.sin(ph * 2) * np.exp(-tt * 3)
    # 包络：极快起音、断奏 chug
    atk = int(0.003 * SR)
    rel = int(min(0.05, dur * 0.28) * SR)
    env = np.ones(n)
    env[:atk] = np.linspace(0, 1, atk)
    if rel > 0:
        env[-rel:] *= np.linspace(1, 0, rel)
    y = y * env * np.exp(-tt * 0.9)
    return (y * vel * 0.22).astype(np.float32)


def guitar_power_chord(root_freq, dur, vel=0.5):
    """强力和弦：根 + 五度（+八度），过载"""
    n = max(int(SR * dur), 8)
    y = guitar_power(root_freq, dur, vel)
    y5 = guitar_power(root_freq * 1.5, dur, vel * 0.8)
    y8 = guitar_power(root_freq * 2, dur, vel * 0.6)
    m = min(len(y), len(y5), len(y8))
    return (y[:m] + y5[:m] + y8[:m]).astype(np.float32)


def bass_electric(freq, dur, vel=0.55):
    """电贝斯：低频厚实 + 指弹攻壳"""
    n = max(int(SR * dur), 8)
    tt = np.arange(n) / SR
    ph = 2 * np.pi * freq * tt
    y = (np.sin(ph) * 1.0 + np.sin(ph * 2) * 0.42
         + np.sin(ph * 3) * 0.12)
    y = _soft_clip(y, 2.2)
    rng = np.random.default_rng(int(freq * 83) % 2**31)
    y = y + rng.standard_normal(n) * 0.015 * np.exp(-tt / 0.01)
    env = np.exp(-tt * 1.8)
    atk = int(0.005 * SR)
    env[:atk] *= np.linspace(0, 1, atk)
    rel = int(min(0.06, dur * 0.25) * SR)
    if rel > 0:
        env[-rel:] *= np.linspace(1, 0, rel)
    return (y * env * vel * 0.30).astype(np.float32)


def drum_kick(dur, vel=0.4):
    """底鼓：频率下扫 + 快衰减"""
    n = max(int(SR * dur), 16)
    tt = np.arange(n) / SR
    f = 110 * np.exp(-tt * 18) + 42
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-tt * 16)
    return (y * vel).astype(np.float32)


def drum_snare(dur, vel=0.22):
    """军鼓：噪声 + 200Hz 本体"""
    n = max(int(SR * dur), 16)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(20261018)
    y = rng.standard_normal(n) * 0.7 + np.sin(2 * np.pi * 205 * tt) * 0.3
    env = np.exp(-tt * 26)
    return (y * env * vel).astype(np.float32)


def drum_hihat(dur, vel=0.09, open_=False):
    """hi-hat：高频噪声，闭/开镲"""
    n = max(int(SR * dur), 16)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(int(vel * 1e6) % 2**31)
    noise = np.diff(rng.standard_normal(n), prepend=0.0)
    env = np.exp(-tt * (20 if open_ else 60))
    return (noise * env * vel).astype(np.float32)


def render_rock(score: dict, out: str) -> str:
    notes = score["notes"]
    total = sum(n["dur"] for n in notes) + 0.8
    buf = np.zeros(int(SR * total), np.float32)
    beat = 60.0 / score["bpm"]
    scale = score["scale"]
    oct0 = score["oct0"]
    mel_end = sum(n["dur"] for n in notes)

    # ---------- 和声进行：I-V-vi-IV（流行摇滚万能进行） ----------
    roots = ["C", "G", "A", "F"]
    chord_beats = 2
    # 伴奏在旋律结束前 1.5 拍全部停下，给结尾留"减速带"
    acc_end = mel_end - beat * 1.5

    # ---------- 节奏吉他：八分音符强力和弦 riff ----------
    pos = 0.0
    ci = 0
    while pos < acc_end:
        root = roots[ci % len(roots)]
        f = NOTE_FREQ[f"{root}3"]
        w = guitar_power_chord(f, beat * 0.85, 0.34)
        s = int(pos * SR)
        e = min(s + len(w), len(buf))
        if s < len(buf):
            buf[s:e] += w[: e - s]
        # 反拍再补一下（八分推动）
        s2 = int((pos + beat * 0.5) * SR)
        w2 = guitar_power_chord(f, beat * 0.4, 0.22)
        e2 = min(s2 + len(w2), len(buf))
        if s2 < len(buf):
            buf[s2:e2] += w2[: e2 - s2]
        pos += chord_beats * beat
        ci += 1

    # ---------- 电贝斯（重版）：每拍根音 + 第2/4拍八度顶 + 半音经过音 ----------
    pos = 0.0
    bi = 0
    while pos < acc_end:
        root = roots[(bi // 2) % len(roots)]
        if bi % 4 in (1, 3):
            f = NOTE_FREQ[f"{root}2"] * 2                 # 八度顶
        elif bi % 8 == 5:
            f = NOTE_FREQ[f"{root}2"] * 2 ** (10 / 12)    # 半音经过（布鲁斯味）
        else:
            f = NOTE_FREQ[f"{root}2"]
        w = bass_electric(f, beat * 0.88, 0.56)
        s = int(pos * SR)
        e = min(s + len(w), len(buf))
        if s < len(buf):
            buf[s:e] += w[: e - s]
        pos += beat
        bi += 1

    # ---------- 鼓组（重版）：kick 四踩加重 + snare 2/4 + hi-hat 八分 + 换和弦开镲 + 每 2 小节填充 ----------
    pos = 0.0
    di = 0
    while pos < acc_end:
        w = drum_kick(beat * 0.5, 0.52)
        s = int(pos * SR); e = min(s + len(w), len(buf))
        if s < len(buf): buf[s:e] += w[: e - s]
        # 第 3 拍再加一脚（双踩推进）
        if di % 4 == 2:
            s2 = int((pos + beat * 0.5) * SR)
            w2 = drum_kick(beat * 0.4, 0.36)
            e2 = min(s2 + len(w2), len(buf))
            if s2 < len(buf): buf[s2:e2] += w2[: e2 - s2]
        if di % 2 == 1:
            w = drum_snare(beat * 0.5, 0.27)
            s = int(pos * SR); e = min(s + len(w), len(buf))
            if s < len(buf): buf[s:e] += w[: e - s]
        for sub in (0.0, 0.5):
            open_ = (sub == 0.0 and di % 4 == 0)
            w = drum_hihat(beat * 0.45, 0.10 if open_ else 0.075, open_)
            s = int((pos + sub * beat) * SR); e = min(s + len(w), len(buf))
            if s < len(buf): buf[s:e] += w[: e - s]
        # 每 8 拍一个军鼓小填充（16 分三连感）
        if di % 8 == 7:
            for j in range(3):
                sf = int((pos + beat * (0.55 + 0.15 * j)) * SR)
                wf = drum_snare(beat * 0.22, 0.14 + 0.04 * j)
                ef = min(sf + len(wf), len(buf))
                if sf < len(buf): buf[sf:ef] += wf[: ef - sf]
        pos += beat
        di += 1

    # ---------- 主奏：过载电吉他单音 ----------
    pos = 0.0
    for n in notes:
        v = n["vel"]
        if n["nutr"] == "钠":
            v = min(v * 1.06, 0.97)
        w = guitar_power(n["freq"], n["dur"] * 0.96, v)
        s = int(pos * SR); e = min(s + len(w), len(buf))
        if s < len(buf): buf[s:e] += w[: e - s]
        pos += n["dur"]

    # ---------- 结尾收束（防"突然结束"） ----------
    # 1) 最后一个音上叠一个渐弱的根音强力和弦（"延音收尾"），长衰减 2.2s
    last = notes[-1]
    root_f = last["freq"] / 2                     # 低八度根音
    tail_start = int((mel_end - beat * 0.5) * SR)
    tail_dur = min(2.2, len(buf) / SR - mel_end + 0.3)
    if tail_dur > 0.4:
        for mul, vv in ((1.0, 0.30), (1.5, 0.22), (2.0, 0.16)):
            w = guitar_power(root_f * mul, tail_dur, vv)
            w *= np.linspace(1, 0, len(w)) ** 0.8   # 线性渐弱
            s = tail_start; e = min(s + len(w), len(buf))
            if s < len(buf): buf[s:e] += w[: e - s]

    peak = np.max(np.abs(buf)) or 1.0
    buf = buf / peak * 0.88
    out_buf = buf.copy()
    for dly, g in ((int(0.07 * SR), 0.13),):
        out_buf[dly:] += buf[:-dly] * g
    # 2) 全局尾部淡出（最后 1.6 秒平滑降到 0），消除任何硬切感
    fade = int(1.6 * SR)
    if len(out_buf) > fade:
        out_buf[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    nz = np.nonzero(np.abs(out_buf) > 0.004)[0]
    if len(nz):
        out_buf = out_buf[: min(len(out_buf), nz[-1] + int(0.3 * SR))]
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
    return (f"[摇滚] BPM {score['bpm']} · {'布鲁斯' if score['minor'] else '大调'} · "
            f"{len(score['notes'])} 音 · 约 {dur:.0f}s\n"
            f"乐句：{' → '.join(seen)}\n"
            f"结尾：{'钙不足 → 上行停在二音' if score['ca_r'] < 0.5 else '钙充足 → 落主音'}")
