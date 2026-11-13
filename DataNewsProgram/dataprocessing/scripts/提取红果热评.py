"""从已下载的红果作品详情页提取网页热评。依赖 beautifulsoup4。"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_url")
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    series_ids = parse_qs(urlparse(args.source_url).query).get("series_id")
    if not series_ids:
        parser.error("作品链接需要包含 series_id。")

    soup = BeautifulSoup(args.html.read_text(encoding="utf-8"), "html.parser")
    heading = soup.find("h1")
    cards = soup.select("article[class*='mobile-review-card']")
    if heading is None or not cards:
        parser.error("页面没有识别到作品标题或网页热评。")

    captured_at = datetime.fromtimestamp(args.html.stat().st_mtime, timezone.utc).isoformat()
    for position, card in enumerate(cards, 1):
        content = card.select_one("p[class*='mobile-review-content']")
        published = card.find("time")
        likes = card.select_one("div[class*='mobile-review-meta'] small")
        if content is None:
            continue
        print(json.dumps({
            "platform": "红果",
            "series_id": series_ids[0],
            "title": heading.get_text(strip=True),
            "source_url": args.source_url,
            "entry_type": "作品详情页热评",
            "source_position": position,
            "published_on": published.get_text(strip=True) if published else None,
            "text": content.get_text().replace("\x00", "").strip(),
            "likes_display": likes.get_text(strip=True) if likes else None,
            "account_role": "待核对",
            "captured_at": captured_at,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
