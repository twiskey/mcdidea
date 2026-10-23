@echo off
rem 麦当劳点餐台启动脚本（Windows）
cd /d "%~dp0.."
python order_app\app.py %*
