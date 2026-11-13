"""下载 2026 年 7—10 月月榜材料，保存出处、时间和 SHA256。

python3 scripts/采集月榜原始材料.py --direct --allow-missing-images
--direct 适用于本机环境变量指向失效代理的情况，不涉及网站权限。
"""
import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from 项目路径 import ROOT
SOURCES = {
    "2026-07": "https://www.thepaper.cn/newsDetail_forward_33750460",
    "2026-08": "https://www.thepaper.cn/newsDetail_forward_34022517",
    "2026-09": "https://www.thepaper.cn/newsDetail_forward_34223675",
    "2026-10": "https://www.thepaper.cn/newsDetail_forward_34442821",
}


def fetch(url, target, direct=False, offline=False):
    if offline:
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError(f"离线文件不存在或为空：{target}")
        return datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat()
    temp = target.with_suffix(target.suffix + ".part")
    cmd = ["curl", "-L", "--fail", "--silent", "--show-error", "--retry", "2", "--connect-timeout", "15", "--max-time", "60"]
    if direct:
        cmd += ["--noproxy", "*"]
    cmd += [url, "-o", str(temp)]
    subprocess.run(cmd, check=True)
    if temp.stat().st_size == 0:
        raise ValueError(f"空响应：{url}")
    temp.replace(target)
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--offline", action="store_true", help="从已下载文件生成清单，不联网")
    parser.add_argument("--allow-missing-images", action="store_true", help="记录缺失榜图并继续，绝不补造榜单行")
    parser.add_argument("--out", type=Path, default=ROOT / "data/raw/monthly_rankings")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    coverage = []
    for month, url in SOURCES.items():
        page = args.out / f"{month}.html"
        page_time = fetch(url, page, args.direct, args.offline)
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        title = soup.find("h1")
        if title is None or not re.search(rf"{int(month[-2:])}月AI剧/?漫剧百强榜", title.get_text()):
            raise ValueError(f"网页标题不符合预期：{url}")
        images = soup.select("img[data-src*='imgpai.thepaper.cn/pphimage/']")
        if len(images) != 2:
            if args.allow_missing_images and len(images) == 0:
                coverage.append({"month": month, "article_url": url, "status": "已保存文字报告，缺红果完整榜图", "expected_rows": 100, "acquired_rows": 0})
                print(f"{month}：缺少完整榜图，仅保留文字报告", flush=True)
                continue
            raise ValueError(f"预期两张榜图，实际 {len(images)} 张；请人工检查，未推断平台。")
        coverage.append({"month": month, "article_url": url, "status": "红果完整榜图已保存，OCR核查另计", "expected_rows": 100, "acquired_rows": 100})
        for platform, image in [("红果", images[1])]:
            # 已核对原文中红果榜为第二张，仍需核对图片内表头。
            image_url = image["data-src"]
            target = args.out / f"{month}_{platform}.jpg"
            if not args.offline:
                time.sleep(1)
            image_time = fetch(image_url, target, args.direct, args.offline)
            manifest.append({
                "month": month, "platform": platform,
                "article_title": title.get_text(strip=True),
                "article_url": url, "article_file": str(page.relative_to(ROOT)) if page.is_relative_to(ROOT) else str(page),
                "article_captured_at": page_time,
                "article_sha256": hashlib.sha256(page.read_bytes()).hexdigest(),
                "image_url": image_url,
                "image_file": str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target),
                "image_captured_at": image_time,
                "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "width_as_listed": image.get("data-width"),
                "height_as_listed": image.get("data-height"),
                "expected_rows": 100,
                "metric": "月内峰值热度",
                "source_scope": "DataEye研究院AI剧漫剧百强榜，澎湃号转载；研究样本已由项目负责人核实为AI短剧",
            })
            # 逐张保存清单，中断后也能追溯已下载的原图。
            (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"已保存 {month} {platform} 原图", flush=True)
    (args.out / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
