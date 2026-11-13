#!/usr/bin/env bash
set -euo pipefail
comment_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$comment_script_dir/.."
python3 scripts/采集红果全榜评论.py plan "$@"
comment_batch="hg_all_comments_$(date -u +%Y%m%dT%H%M%SZ)"
python3 scripts/原子下载队列.py prepare data/红果400条交付/评论全覆盖/详情页下载任务.json "$comment_batch"
if python3 -c 'import json,sys; from pathlib import Path; p=Path("data/补采")/(sys.argv[1]+"_原子任务.json"); sys.exit(0 if json.loads(p.read_text()) else 1)' "$comment_batch"; then
  # 某个请求失败不阻止其他作品；由逐请求日志决定是否入库。
  curl -L --noproxy '*' --config "data/补采/$comment_batch.curl" || true
fi
python3 scripts/原子下载队列.py finalize "$comment_batch"
python3 scripts/采集红果全榜评论.py extract
