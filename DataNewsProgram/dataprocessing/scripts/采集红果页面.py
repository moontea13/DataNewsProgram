"""采集红果公开 AI 榜单当前快照；不提供历史榜单回溯。

依赖：python3 -m pip install beautifulsoup4
运行：python3 采集红果页面.py --pages 1
离线解析已保存网页：python3 采集红果页面.py --html 页面.html
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import urlopen

from bs4 import BeautifulSoup


BASE = "https://hongguoduanju.com/rank/hot-ai-drama"


def parse_page(html, source_url, page_number, captured_at):
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for article in soup.select("article[aria-labelledby^='rank-title-']"):
        title = article.select_one("h2[id^='rank-title-']")
        link = article.select_one("a[href*='series_id=']")
        description = article.select_one("p[class*='description']")
        cover = article.select_one("img")
        rank = article.select_one("span[class*='badge-number']")
        if not title or not link:
            continue
        detail_url = urljoin(BASE, link["href"])
        records.append({
            "platform": "红果",
            "series_id": parse_qs(urlparse(detail_url).query)["series_id"][0],
            "title": title.get_text(strip=True),
            "description": description.get_text(strip=True) if description else None,
            "raw_tags": [x.get_text(strip=True) for x in article.select("p[class*='categories'] span")],
            "cover_url": urljoin(BASE, cover["src"]) if cover and cover.get("src") else None,
            "detail_url": detail_url,
            "source_url": source_url,
            "page_number": page_number,
            "displayed_rank": rank.get_text(strip=True) if rank else None,
            "captured_at": captured_at,
            "source_scope": "当前AI剧榜单快照，非历史月榜；页内名次未转换为全榜名次",
        })
    if not records:
        raise ValueError("未识别到作品，请检查返回网页及页面结构；不写入空结果。")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not 1 <= args.pages <= 10:
        parser.error("--pages 应为 1 至 10")
    captured_at = datetime.now(timezone.utc).isoformat()
    records = {}
    for page in range(1, (1 if args.html else args.pages) + 1):
        url = BASE if page == 1 else f"{BASE}?page={page}"
        if args.html:
            html = args.html.read_text(encoding="utf-8")
        else:
            if page > 1:
                time.sleep(1)
            with urlopen(url, timeout=30) as response:
                html = response.read().decode("utf-8")
        new_rows = parse_page(html, url, page, captured_at)
        if all(row["series_id"] in records for row in new_rows):
            break
        for row in new_rows:
            records.setdefault(row["series_id"], row)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = args.out or Path(__file__).resolve().parents[1] / "data" / f"红果试采_{stamp}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:
        for row in records.values():
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"已保存 {len(records)} 部作品：{target}")


if __name__ == "__main__":
    main()
