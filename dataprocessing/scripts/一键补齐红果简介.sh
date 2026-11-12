#!/bin/sh
# 在项目内自动生成下载队列、下载公开作品页、扩展同名/分季线索、提取简介。
# search_*.json 检索索引先由批量公开搜索生成；不调用受限的站内搜索接口。
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
round=1
status=0
while [ "$round" -le 6 ]; do
    python3 scripts/批量补齐红果简介.py plan
    count=$(python3 -c 'import json; print(len(json.load(open("data/红果简介封面/补采/作品页下载任务.json"))))')
    [ "$count" -gt 0 ] || break
    echo "第 $round 轮：批量下载 $count 个公开作品页"
    # 单个HTTP失败不会取消其他URL；提取阶段将另记失败和缺失。
    curl -L --config data/红果简介封面/补采/作品页下载.curl || true
    downloaded=$(python3 -c 'import json; from pathlib import Path; print(sum(Path(j["file"]).exists() for j in json.load(open("data/红果简介封面/补采/作品页下载任务.json"))))')
    python3 scripts/批量补齐红果简介.py extract
    if [ "$downloaded" -eq 0 ]; then
        echo "本轮没有新页面落盘，停止重复请求。下载清单和缺失清单已保留。" >&2
        status=2
        break
    fi
    round=$((round + 1))
done
python3 scripts/批量补齐红果简介.py extract
exit "$status"
