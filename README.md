# 营养肖像 · 最终方案总览

> 非官方声明：本项目为学习演示，与麦当劳官方无关；菜单与营养数据采集于 2026-10  
> 官方公开渠道，价格以门店实际为准；「麦当劳」及商标权归麦当劳公司所有。  

**项目初衷**：整个任务是根据在麦当劳点的餐品生成一些有趣的图片和旋律，让大家等待取餐的时间不会那么无聊。

一句话输入 → **营养光谱图**（PNG）+ **营养旋律**（WAV，三曲风可选）+ **说明文案**（专业版/大众版）。编曲方面是新手，编出来可能未必好听，待日后再提升。  
也可走完整产品链路：**点餐 → 取餐号 → 光谱 + 旋律**（`order_app/`，手机适配）。

## 文件结构

| 文件                                      | 职责                                         |
| --------------------------------------- | ------------------------------------------ |
| `nutrition_core.py`                     | S1+S2 核心：菜单解析（26 官方单品+别名）、营养聚合、交互指纹        |
| `spectrum_toy.py`                       | S3 光谱渲染（**定稿视觉**，详见下方"视觉定稿"）               |
| `melody_minyue.py`                      | S4 民乐引擎（二胡/古筝/竹笛，五声调式）                     |
| `melody_jazz.py`                        | S4 爵士引擎（电钢琴/行走贝斯/刷鼓，Swing）                 |
| `melody_rock.py`                        | S4 摇滚引擎（过载电吉他/贝斯/鼓组，Power Chord）           |
| `melody_style.py`                       | S4 统一入口：`generate(style=...)`，含大众版/专业版说明生成 |
| `nutrition_portrait.py`                 | **总入口 CLI**：一句话 → 图 + 曲 + 说明               |
| `.workbuddy/skills/nutrition-spectrum/` | **Skill：营养光谱画**（SKILL.md + 可执行脚本）          |
| `.workbuddy/skills/nutrition-melody/`   | **Skill：营养旋律·编曲规划师**（SKILL.md + 合成/规划单脚本）  |
| `order_app/`                            | **点餐台 Web 应用**（点餐→取餐号→光谱+旋律，详见其 README）    |
| `光谱B_光谱加饼图.png`                         | 光谱定稿视觉参考样张                                 |
| `营养旋律_{民乐/爵士/摇滚}_单餐.wav`                | 三曲风样例音频                                    |
| `配器规划单_民乐版_v1.0.md`                     | 民乐配器规划文档样例（编号 ARR-2026-1018-001）           |
| `requirements.txt` / `.gitignore`       | 依赖（numpy+Pillow）与版本控制忽略规则                  |
| `MCP_INTEGRATION.md`                    | **麦当劳官方 MCP 的使用说明**（数据源、Tool、调用流程、业务价值）    |
| `old/`                                  | 过程中间产物（风格探索、旧引擎、旧说明样例等），不参与运行，git 忽略       |

## 用法

```bash
# 单餐：图 + 曲 一次生成
python nutrition_portrait.py "我今天吃了板烧、玉米杯和纯牛奶" \
    --time 2026-10-17T23:50 --style jazz --name 麦当当 --price 47.5 --label 午餐

# 多餐日谱
python nutrition_portrait.py "早饭吃了脆薯饼和纯牛奶，午饭板烧加玉米杯" --day --style rock

# 只出图 / 只出曲
python nutrition_portrait.py "..." --no-melody
python nutrition_portrait.py "..." --no-spectrum
```

```python
from nutrition_portrait import portrait
res = portrait("我今天吃了板烧、玉米杯和纯牛奶",
               when=datetime.now(), inscription="麦当当", style="jazz")
# res["spectrum"] 光谱图路径
# res["melody"]["audio"] 旋律路径；["plain"] 大众版；["headline"] 一句话；["mapping"] 逐条映射
```

## 视觉定稿（光谱，2026-10-18 用户确认）

- 带饼图版（灰边 160,160,160 + 高对比马卡龙配色，饼图右上、图例右列动态居中）
- 分区：宏量营养物质 MACRONUTRIENTS（碳水/糖/蛋白质/脂肪）+ 微量营养物质 MICRONUTRIENTS（钠/钙），中间竖虚线分界
- 谱带顺序：碳水→糖→蛋白质→脂肪→钠→钙；段宽=存在感，峰高=达成率（余弦插值，段中心严格等于标注百分比）
- 亮度定稿 lum (1.00, 1.48)；糖为推算值（碳水×0.35）图上明示
- **颜色不再调整**（用户已确认沿用）

## 旋律映射口径（三曲风共用）

1. 调式 = 钠>80% 且钙<50% → 转暗色小调，否则明亮大调
2. BPM = 能量达成率 × 各曲风基准：民乐 80+38r、爵士 96+30r、摇滚 114+36r（三档听感必须分开）
3. 引子 = 三甲营养素的音程签名（起音级 = 第一名达成率×2.5 + 能量档位；第二名定跳进、第三名定回落）  
   —— 民乐长音滑音 / 爵士上行三连音 pickup / 摇滚根音+四度点弦
4. 乐句顺序 = 碳水→糖→蛋白质→脂肪→钠→钙（与光谱同序）
5. 句长 = 2.6 + 达成率×2.2 拍；骨干音级 = 达成率×8；力度 = 0.50+0.36×达成率
6. 句尾 = 三曲风各不相同：民乐下沉二级（落腔）/ 爵士上下句交替（问答）/ 摇滚落回 riff 根音
7. 结尾 = 钙<50% → 悬置（民乐二度/爵士九音/摇滚上扬二音）；钙足 → 落主音
8. 装饰音插位 = 交互指纹第 16–20 位（同餐不同时 → 骨架相同、装饰不同）
9. 三曲风均要求欢快、积极、温暖；收尾一律自然渐弱，无硬切

## 工程备忘

- Python venv：`C:/Users/wiskey/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
- `fingerprint(when: datetime, order, raw_text, custom: dict)`，custom 需 dict，支持键：`name`（铭文）/ `number` / `color`
- 依赖：numpy、Pillow（无 matplotlib / 无音频库，纯波形合成）
- 不入库（`.gitignore` 已配置）：`old/`、`.workbuddy/memory/`、`order_app/out/`、`order_app/data/orders.json`、`order_app/data/mcp_cache.json`（含门店细节）、`test/out/`、`out/`
