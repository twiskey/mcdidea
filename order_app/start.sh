#!/usr/bin/env bash
# 麦当劳点餐台启动脚本（macOS / Linux）
cd "$(dirname "$0")/.."
python3 order_app/app.py "$@"
