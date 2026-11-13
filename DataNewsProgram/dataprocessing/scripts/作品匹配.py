"""从月榜和已保存公开页面生成作品/季数/系列匹配表及核查队列。

python3 scripts/作品匹配.py
python3 scripts/作品匹配.py --plan-fetch：另列出尚未下载的公开播放页地址。
仅解析公开页面的作品元数据；不读取或请求受保护的播放资源。
"""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from 项目路径 import ROOT
DATA = ROOT / "data"
RAW = DATA / "raw/work_catalogs"
OUT = DATA / "作品匹配"
CN_DIGITS = dict(zip("零〇一二三四五六七八九两", [0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 2]))


def visible_before_month_end(work, month):
    """首见时间晚于上榜月的同名版本排除；未知时间保留为待核候选。"""
    value=str(work.get('first_visible_time',''))
    if not value.isdigit():return True
    year,number=map(int,month.split('-'))
    cutoff=datetime(year+(number==12),1 if number==12 else number+1,1,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
    return int(value)<cutoff


def cn_number(value):
    if value.isascii() and value.isdigit():
        return int(value)
    if all(c in CN_DIGITS for c in value):
        return int("".join(str(CN_DIGITS[c]) for c in value))
    total = digit = 0
    for char in value:
        if char in CN_DIGITS:
            digit = CN_DIGITS[char]
        elif char in "十百千":
            total += (digit or 1) * {"十": 10, "百": 100, "千": 1000}[char]
            digit = 0
        else:
            raise ValueError(value)
    return total + digit


def normalize(text):
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return "".join(c for c in text if unicodedata.category(c)[0] not in "PZC" and not c.isspace())


def parse_title(title):
    cleaned = unicodedata.normalize("NFKC", title).strip()
    match = re.search(r"第([0-9零〇一二三四五六七八九十百千两]+)(季|部|卷|篇)(完结篇|完结|大结局|全集)?[!！。\s]*$", cleaned)
    if match:
        base = cleaned[:match.start()].rstrip(" ：:，,·—-!！ ")
        number = cn_number(match[1])
        return {"base_title": base, "base_key": normalize(base), "season_number": number,
                "installment_unit": match[2], "title_key": f"{normalize(base)}|{match[2]}:{number}",
                "season_parse_status": "剧名明确标季/部；系列关系另核实"}
    # 不把标题中的年份、金额、正文数字或末尾的数字直接当季数。
    return {"base_title": cleaned, "base_key": normalize(cleaned), "season_number": "",
            "installment_unit": "", "title_key": normalize(cleaned), "season_parse_status": "未明确标季；不默认第一季"}


def stable(prefix, text):
    return prefix + hashlib.sha256(text.encode()).hexdigest()[:14]


def write_csv(path, rows, fields=None):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields or (list(rows[0]) if rows else []))
        writer.writeheader()
        writer.writerows(rows)


def router_data(soup):
    for tag in soup.find_all("script"):
        text = tag.get_text().strip()
        if text.startswith("_ROUTER_DATA = "):
            return json.JSONDecoder().raw_decode(text[len("_ROUTER_DATA = "):])[0].get("loaderData", {})
    return {}


def source_url(path):
    name = path.stem
    if name.startswith("detail_"):
        return "https://hongguoduanju.com/detail?series_id=" + name.split("_")[-1]
    if name.startswith("player_"):
        return "https://hongguoduanju.com/player/" + name.split("_")[-1]
    match = re.fullmatch(r"hongguo_(ai_must|ai|comic)_(\d+)", name)
    if match:
        slug = {"ai": "hot-ai-drama", "comic": "hot-comic-drama", "ai_must": "must-watch-ai-drama"}[match[1]]
        return f"https://hongguoduanju.com/rank/{slug}" + (f"?page={match[2]}" if match[2] != "1" else "")
    return "https://novelcatch.com/drama/new" if name == "novelcatch_new" else ""


def load_catalog():
    works = {}
    snapshots = []

    def add(sid, title, url, path, method, **extra):
        if not sid or not title:
            return
        item = works.setdefault(str(sid), {"platform": "红果", "platform_work_id": str(sid), "title": title,
                                           "sources": [], "platform_group_id": "", "description": "", "tags": [],
                                           "episode_count": "", "cover_url": "",
                                           "group_evidence_url": "", "group_evidence_file": ""})
        if item["title"] != title:
            item.setdefault("title_aliases", []).append(title)
        item["sources"].append({"url": url, "file": str(path.relative_to(ROOT)), "method": method})
        for key, value in extra.items():
            if value:
                item[key] = value
        return item

    for path in sorted(RAW.glob("*.html")):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        url = source_url(path)
        snapshots.append({"file": str(path.relative_to(ROOT)), "source_url": url,
                          "captured_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        heading = soup.find("h1")
        rank_title = heading.get_text(strip=True) if heading else ""
        for card in soup.select("article[aria-labelledby^='rank-title-']"):
            title = card.select_one("h2")
            link = card.select_one("a[href*='series_id=']")
            if not title or not link:
                continue
            sid = parse_qs(urlparse(link["href"]).query)["series_id"][0]
            description = card.select_one("p[class*='description']")
            cover = card.select_one("picture img")
            item = add(sid, title.get_text(strip=True), url, path, "平台榜单作品卡片",
                       description=description.get_text(strip=True) if description else "",
                       cover_url=cover.get("src", "") if cover else "")
        # 播放页的“推荐短剧”只作为作品链接来源；推荐关系不是系列关系。
        for card in soup.select("a[href^='/player/']"):
            title = card.select_one("p[class*='title']")
            match = re.fullmatch(r"/player/(\d+)", card["href"])
            if title and match:
                add(match[1], title.get_text(strip=True), url, path, "平台推荐卡片；不据此认定同系列")
        for card in soup.select("article[data-drama-card]"):
            title = card.select_one("h3 a")
            if title:
                add(card["data-drama-card"], title.get_text(strip=True), url, path, "第三方网文情报站线索")
        for value in router_data(soup).values():
            if not isinstance(value, dict) or not isinstance(value.get("seriesDetail"), dict):
                continue
            sd = value["seriesDetail"]
            group = (sd.get("season_info") or {}).get("series_group_id", "")
            add(sd.get("series_id"), sd.get("series_name"), url, path, "平台详情/播放页公开作品元数据",
                platform_group_id=str(group) if group else "", group_evidence_url=url if group else "",
                group_evidence_file=str(path.relative_to(ROOT)) if group else "",
                description=sd.get("series_intro", ""), tags=sd.get("tags", []),
                episode_count=sd.get("episode_cnt", ""), cover_url=sd.get("series_cover", ""),
                first_visible_time=str(sd.get('first_visible_time') or ''))
    return works, snapshots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-fetch", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ranks = list(csv.DictReader((DATA / "月榜_OCR待核查.csv").open(encoding="utf-8-sig")))
    works, snapshots = load_catalog()
    by_title = defaultdict(list)
    rank_bases = {parse_title(r["title_raw"])["base_key"] for r in ranks}
    rank_keys = {parse_title(r["title_raw"])["title_key"] for r in ranks}
    for work in works.values():
        parsed = parse_title(work["title"])
        work.update(parsed)
        for name in {work["title"], *work.get("title_aliases", [])}:
            key = parse_title(name)["title_key"]
            if all(w["platform_work_id"] != work["platform_work_id"] for w in by_title[key]):
                by_title[key].append(work)
    fetch = []
    # 每个与榜单相关的文字系列先选一个种子页；推荐中发现的具体季再核实自己的 group_id。
    groups = defaultdict(list)
    for work in works.values():
        # 数字尾缀只用于扩展查找线索，绝不在这里确认季号或系列。
        prefix = re.sub(r"\d+$", "", work["base_key"])
        related_numeric = bool(prefix and any(re.sub(r"\d+$", "", base) == prefix for base in rank_bases))
        if work["base_key"] in rank_bases or related_numeric:
            groups[work["base_key"]].append(work)
    seeds = [max(group, key=lambda w: len(w["sources"])) for group in groups.values()]
    needed = {w["platform_work_id"] for w in seeds}
    needed.update(w["platform_work_id"] for w in works.values() if w["title_key"] in rank_keys)
    for sid in sorted(needed):
        path = RAW / f"player_{sid}.html"
        if not path.exists():
            fetch.append({"platform_work_id": sid, "title": works[sid]["title"],
                          "url": f"https://hongguoduanju.com/player/{sid}", "file": str(path.relative_to(ROOT))})
    (OUT / "待采公开作品页.json").write_text(json.dumps(fetch, ensure_ascii=False, indent=2) + "\n")
    (OUT / "页面留存清单.json").write_text(json.dumps(snapshots, ensure_ascii=False, indent=2) + "\n")
    with (OUT / "平台作品索引.jsonl").open("w") as f:
        for work in works.values():
            f.write(json.dumps(work, ensure_ascii=False) + "\n")
    mapping = []
    for rank in ranks:
        parsed = parse_title(rank["title_raw"])
        candidates = by_title.get(parsed["title_key"], [])
        eligible = [w for w in candidates if visible_before_month_end(w,rank['month'])]
        unique = eligible[0] if len(eligible) == 1 else None
        is_hongguo = rank["platform"] == "红果"
        official_sources = [s for s in unique["sources"] if urlparse(s["url"]).hostname == "hongguoduanju.com"] if unique else []
        direct = unique if is_hongguo and official_sources else None
        # 作品编号仅采用具有来源证据的同名版本。
        work_id = f"HG_{direct['platform_work_id']}" if direct else ""
        group_id = f"HG_GROUP_{direct['platform_group_id']}" if direct and direct["platform_group_id"] else ""
        numeric_candidate = ""
        numeric_note = ""
        suffix = re.fullmatch(r"(.+?)(\d{1,3})", normalize(rank["title_raw"]))
        if direct and group_id and not parsed["season_number"] and suffix:
            siblings = [w for w in works.values() if w["platform_group_id"] == direct["platform_group_id"]
                        and normalize(w["title"]).startswith(suffix[1])]
            if len({normalize(w["title"]) for w in siblings}) >= 2:
                numeric_candidate = int(suffix[2])
                numeric_note = "同平台group_id存在多个同名前缀版本；尾数作为编号候选，不直接当季号"
        mapping.append({**rank, **parsed,
                        "work_id": work_id,
                        "candidate_work_id": work_id or stable("CAND_", rank["platform"] + "|" + parsed["title_key"] + "|" + rank["content_type_raw"]),
                        "platform_work_id": direct["platform_work_id"] if direct else "",
                        "installment_number_candidate": numeric_candidate,
                        "numbering_evidence_note": numeric_note,
                        "identity_status": "平台同名唯一候选；榜单版本仍需核对" if direct else ("同名多ID，禁止自动合并" if len(candidates) > 1 and is_hongguo else "未匹配平台ID"),
                        "candidate_platform_ids": "|".join(w["platform_work_id"] for w in candidates),
                        "eligible_platform_ids": "|".join(w["platform_work_id"] for w in eligible),
                        "identity_timing_note": f'排除{len(candidates)-len(eligible)}个首见时间晚于上榜月的同名ID；未知时间不等于历史身份已确认',
                        "identity_evidence_url": official_sources[0]["url"] if direct else "",
                        "identity_evidence_file": official_sources[0]["file"] if direct else "",
                        "franchise_id": group_id,
                        "franchise_candidate_id": stable("SERIES_CAND_", parsed["base_key"]),
                        "franchise_status": "平台group_id已提取；榜单身份待复核" if group_id else "仅按剧名形成系列候选；未确认",
                        "franchise_evidence_url": direct["group_evidence_url"] if direct else ""})
    write_csv(OUT / "上榜记录_作品系列映射.csv", mapping)
    # 只用平台自己的 group_id 汇总已知系列；名称候选在上表单列，不混进这里。
    indexed_relevant = [w for w in works.values() if w["title_key"] in rank_keys or w["base_key"] in rank_bases]
    season_rows = []
    for w in indexed_relevant:
        season_rows.append({"platform_work_id": w["platform_work_id"], "title": w["title"],
                            "season_number": w["season_number"], "season_parse_status": w["season_parse_status"],
                            "platform_group_id": w["platform_group_id"],
                            "group_status": "平台公开元数据已核" if w["platform_group_id"] else "待核",
                            "evidence_url": w["group_evidence_url"], "evidence_file": w["group_evidence_file"]})
    write_csv(OUT / "平台系列分季表.csv", season_rows)
    group_sets = defaultdict(list)
    for w in indexed_relevant:
        if w["platform_group_id"]:
            group_sets[w["platform_group_id"]].append(w)
    series_rows = []
    for gid, members in group_sets.items():
        series_rows.append({"franchise_id": "HG_GROUP_" + gid,
                            "base_names": "|".join(sorted({w["base_title"] for w in members})),
                            "indexed_work_count": len(members),
                            "indexed_seasons": "|".join(str(v) for v in sorted({w["season_number"] for w in members if w["season_number"] != ""})),
                            "platform_work_ids": "|".join(w["platform_work_id"] for w in members),
                            "matched_ranking_count": sum(r["franchise_id"] == "HG_GROUP_" + gid for r in mapping),
                            "status": "所列平台作品同group_id；榜单身份匹配和完整季数另核"})
    write_csv(OUT / "平台系列汇总.csv", series_rows)
    candidate_groups = defaultdict(list)
    for r in mapping:
        candidate_groups[r["candidate_work_id"]].append(r)
    candidates = []
    for key, group in candidate_groups.items():
        producers = sorted({normalize(r["producer_raw"]) for r in group if r["producer_raw"] not in ["", "待确认", "待认领"]})
        candidates.append({"candidate_work_id": key, "platform": group[0]["platform"], "title": group[0]["title_raw"],
                           "season_number": group[0]["season_number"], "base_title": group[0]["base_title"],
                           "ranking_count": len(group), "months": "|".join(sorted({r["month"] for r in group})),
                           "ranking_ids": "|".join(r["ranking_id"] for r in group),
                           "platform_work_ids": "|".join(sorted({r["platform_work_id"] for r in group if r["platform_work_id"]})),
                           "producer_conflict": "同名出品方不一致，待核" if len(producers) > 1 else "",
                           "status": "去重候选，不等于已核实独立作品"})
    write_csv(OUT / "作品去重候选表.csv", candidates)
    # 名称接近只提出人工核查任务；不改写原始剧名，也不自动合并。
    keys = sorted({(r["title_raw"], r["title_key"], str(r["season_number"]), r["installment_unit"]) for r in mapping})
    fuzzy = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if a[2:] != b[2:] or a[1] == b[1]:
                continue
            na, nb = re.fullmatch(r"(.+?)(\d{1,3})", a[1]), re.fullmatch(r"(.+?)(\d{1,3})", b[1])
            if na and nb and na[1] == nb[1] and na[2] != nb[2]:
                ga = {w["platform_group_id"] for w in by_title.get(a[1], []) if w["platform_group_id"]}
                gb = {w["platform_group_id"] for w in by_title.get(b[1], []) if w["platform_group_id"]}
                if ga & gb:
                    continue  # 已用平台group_id确认是同系列不同编号，保留不同作品，不作OCR错字处理。
            score = SequenceMatcher(None, a[1], b[1]).ratio()
            if score >= 0.88:
                fuzzy.append({"title_a": a[0], "title_b": b[0], "score": round(score, 4), "status": "疑似OCR/别名差异；未合并"})
    write_csv(OUT / "近名与OCR疑点.csv", fuzzy, ["title_a", "title_b", "score", "status"])
    missing = []
    for item in candidates:
        if not item["platform_work_ids"]:
            missing.append({"candidate_work_id": item["candidate_work_id"], "platform": item["platform"],
                            "title": item["title"], "months": item["months"], "ranking_ids": item["ranking_ids"],
                            "reason": "当前公开目录未找到唯一同名ID，需定向检索",
                            "priority": "先核对榜图标题，再查平台详情或出品方资料"})
    write_csv(OUT / "未匹配作品待查清单.csv", missing)
    summary = {"target_months": [f"2026-{m:02}" for m in range(7, 11)],
               "complete_months_acquired": sorted({r["month"] for r in ranks}),
               "ranking_rows": len(ranks), "catalog_unique_platform_ids": len(works),
               "candidate_works_within_platform": len(candidates),
               "matched_hongguo_ranking_rows": sum(bool(r["platform_work_id"]) for r in mapping),
               "matched_hongguo_unique_ids": len({r["platform_work_id"] for r in mapping if r["platform_work_id"]}),
               "official_group_mapped_ranking_rows": sum(bool(r["franchise_id"]) for r in mapping),
               "title_season_parsed_rows": sum(r["season_number"] != "" for r in mapping),
               "numeric_installment_candidate_rows": sum(r["installment_number_candidate"] != "" for r in mapping),
               "near_name_pairs": len(fuzzy),
               "remaining_public_page_jobs": len(fetch),
               "official_relevant_series_groups": len(series_rows),
               "limits": "上榜记录、独立作品和系列分别统计；作品及系列候选仍需身份核查；本轮仅处理红果7—10月。"}
    (OUT / "处理统计.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
