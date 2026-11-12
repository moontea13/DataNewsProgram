"""从已下载的网文情报站公开榜单提取出品方及原著线索。

运行：python3 提取出品与改编线索.py data/novelcatch.html
依赖：beautifulsoup4。结果为第三方页面记录，保留来源供后续核对。
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("html", type=Path)
parser.add_argument("--source", default="https://novelcatch.com/drama/new")
parser.add_argument("--out", type=Path)
args = parser.parse_args()
soup = BeautifulSoup(args.html.read_text(encoding="utf-8"), "html.parser")
rows = {}
for card in soup.select("article[data-drama-card]"):
    title = card.select_one("h3 a")
    if not title:
        continue
    meta = card.select_one("div[class$='__meta']")
    parts = meta.find_all("span", recursive=False) if meta else []
    episode = next((x.get_text(strip=True) for x in parts if re.fullmatch(r"\d+\s*集", x.get_text(strip=True))), None)
    released = card.select_one("span[title*='上线']")
    companies = [x for x in parts if not x.get("class") and not x.get("title") and x.get_text(strip=True) != episode]
    producer = "".join(str(x) for x in companies[0].children if isinstance(x, NavigableString)).strip() if companies else None
    original = card.select_one("div[class$='__orig'] a[href^='/book/']")
    author = original.find_next_sibling("span") if original else None
    book_id = original["href"].rstrip("/").split("/")[-1] if original else None
    identifier = card["data-drama-card"]
    rows[identifier] = {
        "series_id": identifier,
        "title": title.get_text(strip=True),
        "source_content_type": parts[0].get_text(strip=True) if parts else None,
        "episode_count": int(re.search(r"\d+", episode).group()) if episode else None,
        "release_note": released["title"] if released else None,
        "producer_as_listed": producer,
        "original_title_as_listed": original.get_text(strip=True).strip("《》") if original else None,
        "author_as_listed": author.get_text(strip=True).lstrip(" ·") if author else None,
        "book_id": book_id,
        "original_record_url": urljoin(args.source, original["href"]) if original else None,
        "drama_record_url": urljoin(args.source, title["href"]),
        "evidence_status": "第三方页面标注",
        "source_url": args.source,
        "source_file_modified_at": datetime.fromtimestamp(args.html.stat().st_mtime, timezone.utc).isoformat(),
    }
if not rows:
    raise SystemExit("未识别到作品卡片，请检查输入网页。")
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
target = args.out or Path(__file__).resolve().parents[1] / "data" / f"出品改编线索_{stamp}.jsonl"
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("x", encoding="utf-8") as f:
    for row in rows.values():
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(f"提取 {len(rows)} 部作品；{sum(bool(r['producer_as_listed']) for r in rows.values())} 条出品方记录；{sum(bool(r['book_id']) for r in rows.values())} 条原著线索。保存至 {target}")
