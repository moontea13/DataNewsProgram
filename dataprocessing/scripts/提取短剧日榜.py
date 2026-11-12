"""将已下载的短剧工程日榜 HTML 转成 JSONL。依赖 beautifulsoup4。"""

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", type=date.fromisoformat)
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    source = f"https://www.duanjugongcheng.com/cn/bangdan/{args.date.isoformat()}"
    soup = BeautifulSoup(args.html.read_text(encoding="utf-8"), "html.parser")
    heading = soup.find("h1")
    date_label = f"{args.date.year}年{args.date.month}月{args.date.day}日"
    if not heading or date_label not in heading.get_text(strip=True) or "周榜" in heading.get_text(strip=True):
        parser.error("网页标题与指定日期的日榜不符。")
    table = next((item for item in soup.find_all("table") if "当日热播指数" in item.get_text(" ", strip=True)), None)
    if table is None:
        parser.error("页面缺少当日热播指数表。")
    for row in table.select("tbody tr"):
        rank, _, drama, genre, index = row.find_all("td", recursive=False)
        link = drama.find("a", href=True)
        print(json.dumps({
            "date": args.date.isoformat(),
            "rank": int(rank.get_text(strip=True)),
            "title": link.get_text(strip=True),
            "genre": genre.get_text(strip=True),
            "daily_index": int(index.get_text(strip=True).replace(",", "")),
            "series_url": urljoin(source, link["href"]),
            "source_url": source,
            "metric": "短剧工程当日热播指数（该页注明依据抖音榜单数据）",
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
