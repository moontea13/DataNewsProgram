#!/usr/bin/env bash
# 只使用已落盘材料，不执行下载，不自动确认新的OCR或作品身份。
set -euo pipefail
rebuild_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$rebuild_dir/.."
export PYTHONDONTWRITEBYTECODE=1
python3 scripts/识别月榜草稿.py --reuse-ocr
python3 scripts/作品匹配.py
python3 scripts/批量补齐红果简介.py extract
python3 scripts/持续补采.py audit-covers
python3 scripts/解析百科与扩展.py
python3 scripts/解析作品证据.py
python3 scripts/解析原著页.py
python3 scripts/关联原著与作者.py
python3 scripts/红果剩余材料.py
python3 scripts/整合红果交付.py
python3 scripts/合并红果系列.py
python3 scripts/核实红果关系.py
python3 scripts/合并红果系列.py
python3 scripts/采集红果全榜评论.py extract
python3 scripts/核查交付重复.py
python3 scripts/生成覆盖与续跑报告.py
python3 scripts/检查采集结果.py
python3 scripts/生成交付索引.py
