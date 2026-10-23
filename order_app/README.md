# 麦当劳 - 你的专属营养光谱&旋律

手机优先的点餐界面：点餐 → 取餐号 → 一键生成这单专属的  
**营养光谱图**（带饼图定稿版）与**营养旋律**（民乐 / 爵士 / 摇滚）。

项目初衷：根据在麦当劳点的餐品生成一些有趣的图片和旋律，让大家等待取餐的时间不会那么无聊。因此在这个项目里，点餐台只是个简化演示。

> 本应用为学习演示项目，与麦当劳官方无关；菜单与营养数据来自官方公开渠道，商标权归麦当劳所有。

## 启动

```bash
python order_app/app.py              # 本机预览 http://127.0.0.1:8765
python order_app/app.py --lan        # 手机真机访问（同一 WiFi，启动时打印地址）
python order_app/app.py --port 9000  # 换端口
```

Windows 可双击 `start.bat`，macOS/Linux 用 `./start.sh`。

快速看效果：浏览器打开 `http://127.0.0.1:8765/?demo=1`  
（自动下一单样例餐并直接跳到光谱+旋律页）。

## 页面流程

| 屏        | 内容                                                |
| -------- | ------------------------------------------------- |
| S0 点餐    | 三分类 26 个官方单品，色块插画卡片，底部结算条                         |
| S1 取餐号   | 大号取餐号（A001 递增）+ 小票 + 「想知道你的餐品营养光谱和旋律吗？」           |
| S2 生成中   | 骨架屏（光谱 ≈1.7s + 旋律 ≈0.7s，实测约 2.4s）                 |
| S3 光谱+旋律 | 顶部常驻取餐号；上：营养光谱 + 分享按钮；下：三曲风切换 + 播放器 + 一行概括 + 专属落款 |

完整用户流程见 `USER_CASE.md`。

## 接口

| 方法   | 路径                      | 说明                                         |
| ---- | ----------------------- | ------------------------------------------ |
| GET  | `/api/menu`             | 菜单（分类 / 价格 / 热量 / 卡片色）                     |
| POST | `/api/order`            | `{items:[{code,qty}]}` → 取餐号 + 小票          |
| POST | `/api/portrait`         | `{order_no, style}` → 光谱 URL + 旋律 URL + 说明 |
| GET  | `/media/<order>/<file>` | 产物（png / wav），支持 Range（手机拖动进度条）            |
| GET  | `/health`               | 健康检查                                       |

## 设计要点

- **开启点餐台时同步一次 MCP**：Agent 会话调用麦当劳官方 MCP（最近门店 +  
  全量营养）写入 `data/mcp_cache.json`；服务启动时覆盖 CATALOG 营养值、  
  顶栏显示最近门店与同步时间；使用期间不再调 MCP，全部走内存缓存。  
  无缓存文件时降级为本地快照（详见 `../MCP_INTEGRATION.md`）。
- **营养数值按 SKU code 精确计算**（`portrait_service._parsed`），不走文本解析，  
  避免「玉米杯」被别名匹配成小杯、数量丢失。
- **指纹铭文 = 取餐号，时间 = 下单时刻**：同一单反复进出图/曲不变（缓存命中），  
  不同单必然不同。光谱图落款直接印取餐号。
- 每单每曲风只生成一次，产物在 `out/<order_no>/`；台账 `data/orders.json`  
  重启续号。
- `melody_style.generate(..., agg=...)` 支持直接传聚合结果，供结构化场景复用。

## E2E（可选）

`tests/e2e_flow.js` 用 playwright-core 驱动本机 Edge 走全流程（点餐 → 取餐号 →  
光谱 → 切摇滚），需 `NODE_PATH` 指向含 playwright-core 的 node_modules，  
先启动服务再运行。

## 文件

```
app.py               HTTP 服务 + API（标准库，零第三方依赖）
menu.py              CATALOG → 前端菜单 JSON（含门店与同步时间）
mcp_cache.py         MCP 缓存层：启动时用 data/mcp_cache.json 覆盖 CATALOG
portrait_service.py  订单 → 光谱 + 旋律（核心业务）
static/              index.html / app.css / app.js（无框架、无 CDN）
tests/e2e_flow.js    全流程自动化验证（playwright-core + Edge）
start.bat / start.sh 一键启动脚本
out/                 运行时产物（按订单分目录，git 忽略）
data/orders.json     订单台账（运行时数据，git 忽略）
data/mcp_cache.json  麦当劳 MCP 缓存（门店 + 营养，开启点餐台时刷新，git 忽略）
```
