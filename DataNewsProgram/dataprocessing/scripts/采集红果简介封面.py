"""按作品编号采集红果公开简介和封面；默认只处理已有月榜映射中的红果样本。

python3 scripts/采集红果简介封面.py --direct
python3 scripts/采集红果简介封面.py --offline
python3 scripts/采集红果简介封面.py --id 7673067074104593432 --direct --out /private/tmp/红果试采

依赖 beautifulsoup4、Pillow。缓存优先、逐个请求；不采播放资源和用户数据。
CSV 是便于核查的原始数据导出，JSONL 保留列表和完整字段结构。
"""
import argparse
import csv
import hashlib
import json
import re
import shlex
import subprocess
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from PIL import Image

from 项目路径 import ROOT
MAPPING = ROOT / "data/作品匹配/上榜记录_作品系列映射.csv"
RAW = ROOT / "data/raw/work_catalogs"
OUT = ROOT / "data/红果简介封面"
BASE = "https://hongguoduanju.com"
USER_AGENT = "CourseDataJournalism/1.0 (public metadata collection)"
MAX_BYTES = 12 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def location(path):
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(c for c in text if unicodedata.category(c)[0] not in "PZC" and not c.isspace())


def parse_work(html, expected_id):
    """仅从公开嵌入 JSON 中取白名单字段，并校验页面作品身份。"""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        match = re.match(r"\s*(?:window\.)?_ROUTER_DATA\s*=\s*", script.get_text())
        if not match:
            continue
        data = json.JSONDecoder().raw_decode(script.get_text()[match.end():])[0]
        loaders = data.get("loaderData", {})
        for value in loaders.values():
            sd = value.get("seriesDetail") if isinstance(value, dict) else None
            if not isinstance(sd, dict) or str(sd.get("series_id")) != expected_id:
                continue
            title = str(sd.get("series_name") or "").strip()
            if not title:
                raise ValueError("公开元数据没有剧名")
            intro = str(sd.get("series_intro") or "").strip()
            season = sd.get("season_info") or {}
            group = season.get("series_group_id", "") if isinstance(season, dict) else ""
            return {
                "platform": "红果", "platform_work_id": expected_id, "title": title,
                "platform_group_id": str(group) if group else "",
                "description": intro, "description_status": "已取得" if intro else "页面简介为空",
                "description_char_count": len(intro),
                "description_normalized_sha256": sha(normalized(intro).encode()) if intro else "",
                "tags": sd.get("tags") or [], "episode_count": sd.get("episode_cnt", ""),
                "record_number": sd.get("record_number", ""),
                "first_visible_time": str(sd.get("first_visible_time") or ""),
                "cover_url": str(sd.get("series_cover") or ""),
                "metadata_method": "公开HTML内_ROUTER_DATA.loaderData.*.seriesDetail",
            }
    raise ValueError("没有找到与请求作品编号相同的公开 seriesDetail；不使用推荐卡片代替")


class Fetcher:
    def __init__(self, direct=False, interval=1.0):
        self.direct = direct
        self.interval = interval
        self.last_request = 0.0

    def download(self, url):
        if urlparse(url).scheme != "https":
            raise ValueError("仅接受HTTPS地址")
        time.sleep(max(0.0, self.interval - (time.monotonic() - self.last_request)))
        command = ["curl", "-L", "--fail", "--silent", "--show-error", "--ipv4",
                   "--connect-timeout", "8", "--max-time", "35", "--max-filesize", str(MAX_BYTES),
                   "--proto", "=https", "--proto-redir", "=https", "--user-agent", USER_AGENT]
        if self.direct:
            command += ["--noproxy", "*"]
        self.last_request = time.monotonic()
        result = subprocess.run(command + [url], capture_output=True, timeout=40)
        if result.returncode:
            message = result.stderr.decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"下载失败({result.returncode}): {message}")
        if len(result.stdout) > MAX_BYTES:
            raise ValueError("响应超过12MB")
        return result.stdout


def image_info(data):
    with Image.open(BytesIO(data)) as im:
        fmt, size = im.format, im.size
        if fmt not in {"JPEG", "PNG", "WEBP", "GIF", "AVIF"}:
            raise ValueError(f"封面格式不支持: {fmt}")
        im.verify()
    return {"cover_format": fmt, "cover_width": size[0], "cover_height": size[1],
            "cover_sha256": sha(data), "cover_bytes": len(data)}


def save_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def save_records(directory, stem, rows, fields=None):
    target = directory / (stem + ".jsonl")
    tmp = target.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(target)
    if fields is None:
        fields = list(dict.fromkeys(k for row in rows for k in row))
    if fields:
        target = directory / (stem + ".csv")
        tmp = target.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                                 for k, v in row.items()})
        tmp.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", action="append", default=[], help="指定作品ID，可重复")
    parser.add_argument("--mapping", type=Path, default=MAPPING)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--offline", action="store_true", help="只读已保存页面与封面")
    parser.add_argument("--skip-covers", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="重新请求作品页；不改旧页面")
    parser.add_argument("--direct", action="store_true", help="curl绕过本机代理")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--export-download-plan", action="store_true", help="导出缺失封面的独立curl下载清单/脚本；可与离线模式配合")
    args = parser.parse_args()
    if args.interval < 0.5:
        parser.error("请求间隔至少0.5秒")
    if args.refresh and args.offline:
        parser.error("--refresh 不能与 --offline 同用")
    ranks = list(csv.DictReader(args.mapping.open(encoding="utf-8-sig"))) if args.mapping.exists() else []
    by_id = defaultdict(list)
    for row in ranks:
        if row["platform"] == "红果" and row["platform_work_id"]:
            by_id[row["platform_work_id"]].append(row)
    ids = sorted(set(args.id) if args.id else by_id)
    if not ids or any(not re.fullmatch(r"\d{10,25}", sid) for sid in ids):
        parser.error("缺少有效作品ID；先完成样本映射，或通过 --id 指定")
    args.out.mkdir(parents=True, exist_ok=True)
    cover_dir = args.out / "covers"
    cover_dir.mkdir(exist_ok=True)
    snapshots = args.out / "pages"
    snapshots.mkdir(exist_ok=True)
    fetcher = Fetcher(args.direct, args.interval)
    robots = None
    robots_capture = ""
    if not args.offline:
        robots_bytes = fetcher.download(BASE + "/robots.txt")
        (args.out / "robots.txt").write_bytes(robots_bytes)
        robots_capture = now()
        robots = RobotFileParser()
        robots.parse(robots_bytes.decode("utf-8").splitlines())
    previous = args.out / "红果简介封面.jsonl"
    cache = {r["platform_work_id"]: r for r in
             (json.loads(line) for line in previous.read_text().splitlines())} if previous.exists() else {}
    output = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for i, sid in enumerate(ids, 1):
        url = f"{BASE}/player/{sid}"
        matches = by_id.get(sid, [])
        record = {"platform": "红果", "platform_work_id": sid, "source_url": url,
                  "ranking_ids": [r["ranking_id"] for r in matches],
                  "ranking_titles": sorted({r["title_raw"] for r in matches}),
                  "ranking_months": sorted({r["month"] for r in matches}),
                  "identity_status": "同名/季号匹配候选；榜单版本仍待核实" if matches else "手动指定ID；未关联月榜",
                  "extracted_at": now(), "cover_status": "未处理", "error": ""}
        try:
            # 新快照独立保存，原先用于匹配和核实的页面、哈希保持原样。
            stored = cache.get(sid, {}).get("source_file", "")
            prior = Path(stored) if stored else None
            if prior and not prior.is_absolute():
                prior = ROOT / prior
            path = prior if prior and prior.exists() else args.raw / f"player_{sid}.html"
            if args.refresh or not path.exists():
                if args.offline:
                    raise FileNotFoundError("离线模式没有已保存作品页")
                if not robots.can_fetch(USER_AGENT, url):
                    raise ValueError("作品页不在robots允许范围")
                data = fetcher.download(url)
                work = parse_work(data.decode("utf-8"), sid)
                path = snapshots / f"player_{sid}_{stamp}.html"
                path.write_bytes(data)
                captured, capture_basis = now(), "本脚本下载时间"
            else:
                data = path.read_bytes()
                work = parse_work(data.decode("utf-8"), sid)
                prev = cache.get(sid, {})
                same = prev.get("source_sha256") == sha(data)
                captured = prev.get("source_captured_at") if same else None
                captured = captured or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                capture_basis = prev.get("source_time_basis", "文件修改时间；非服务器发布时间") if same else "文件修改时间；非服务器发布时间"
            record.update(work, source_file=location(path), source_sha256=sha(data),
                          source_captured_at=captured, source_time_basis=capture_basis,
                          snapshot_scope="采集时简介与封面，不代表上榜当月历史版本")
            if args.skip_covers:
                record["cover_status"] = "本次跳过下载"
            elif not work["cover_url"]:
                record["cover_status"] = "页面无封面地址"
            else:
                old = cache.get(sid, {})
                images = sorted(cover_dir.glob(sid + ".*"))
                if images and not args.refresh:
                    image_path = images[0]
                    blob = image_path.read_bytes()
                    info = image_info(blob)
                    if old.get("cover_sha256") and old["cover_sha256"] != info["cover_sha256"]:
                        raise ValueError("已保存封面校验不一致；保留现场，未自动覆盖")
                    cover_capture = old.get("cover_captured_at") or datetime.fromtimestamp(image_path.stat().st_mtime, timezone.utc).isoformat()
                    cover_time_basis = old.get("cover_time_basis") or "文件修改时间；非服务器发布时间"
                    download_url = old.get("cover_download_url", work["cover_url"])
                    if image_path.suffix == ".image":
                        ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif", "AVIF": "avif"}[info["cover_format"]]
                        proper = image_path.with_suffix("." + ext)
                        if not proper.exists():
                            image_path.rename(proper)
                            image_path = proper
                elif args.offline:
                    record["cover_status"] = "离线模式缺封面文件"
                    info = None
                else:
                    host = urlparse(work["cover_url"]).hostname or ""
                    if not (host.endswith(".byteimg.com") or host == "byteimg.com"):
                        raise ValueError("封面地址不是已确认的byteimg图片域名，需另行核查")
                    blob = fetcher.download(work["cover_url"])
                    info = image_info(blob)
                    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif", "AVIF": "avif"}[info["cover_format"]]
                    image_path = cover_dir / f"{sid}.{ext}"
                    if image_path.exists():
                        # 刷新另留文件，不覆盖之前采集的封面快照。
                        image_path = cover_dir / f"{sid}_{stamp}.{ext}"
                    image_path.write_bytes(blob)
                    cover_capture, download_url = now(), work["cover_url"]
                    cover_time_basis = "本脚本下载时间"
                if info:
                    record.update(info, cover_file=location(image_path), cover_captured_at=cover_capture,
                                  cover_time_basis=cover_time_basis,
                                  cover_download_url=download_url, cover_status="已下载并校验")
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            if record.get("cover_status") == "未处理":
                record["cover_status"] = "采集失败"
        output.append(record)
        # 每部完成即更新，意外中断后可以重跑；失败也有单独状态。
        save_records(args.out, "红果简介封面", output)
        print(f"[{i}/{len(ids)}] {record.get('title', sid)} | 简介{record.get('description_char_count', 0)}字 | {record['cover_status']}"
              + (f" | {record['error']}" if record["error"] else ""), flush=True)
    selected = {r["platform_work_id"]: r for r in output}
    joined = []
    for rank in ranks:
        work = selected.get(rank["platform_work_id"]) if rank["platform"] == "红果" else None
        state = ("已关联候选作品简介" if work and work.get("description") else
                 "作品简介采集失败或为空" if work else
                 "非本轮平台；未套用红果简介" if rank["platform"] != "红果" else
                 "未列入本次指定ID" if rank["platform_work_id"] else "尚未匹配作品ID")
        joined.append({"ranking_id": rank["ranking_id"], "month": rank["month"], "platform": rank["platform"],
                       "rank": rank["rank"], "ranking_title": rank["title_raw"],
                       "platform_work_id": rank["platform_work_id"], "candidate_work_id": rank["candidate_work_id"],
                       "link_status": state, "work_title": work.get("title", "") if work else "",
                       "description": work.get("description", "") if work else "",
                       "cover_file": work.get("cover_file", "") if work else "",
                       "source_url": work.get("source_url", "") if work else ""})
    save_records(args.out, "上榜记录_简介封面关联", joined)
    if args.export_download_plan:
        jobs = []
        commands = ["#!/bin/sh", "# 仅下载缺失封面；运行后再用 --offline 验证图片并生成关联表。", "set -eu",
                    "mkdir -p " + shlex.quote(str(cover_dir.resolve()))]
        for row in output:
            url = row.get("cover_url", "")
            host = urlparse(url).hostname or ""
            if row["cover_status"] == "已下载并校验" or not url or urlparse(url).scheme != "https":
                continue
            if not (host == "byteimg.com" or host.endswith(".byteimg.com")):
                continue
            path = cover_dir.resolve() / (row["platform_work_id"] + ".image")
            jobs.append({"platform_work_id": row["platform_work_id"], "url": url, "file": str(path)})
            command = ["curl", "-L", "--fail", "--silent", "--show-error", "--ipv4", "--connect-timeout", "8",
                       "--max-time", "35", "--max-filesize", str(MAX_BYTES), "--proto", "=https", "--proto-redir", "=https"]
            if args.direct:
                command += ["--noproxy", "*"]
            command += [url, "-o", str(path) + ".part"]
            commands += [shlex.join(command), "mv " + shlex.quote(str(path) + ".part") + " " + shlex.quote(str(path)),
                         f"sleep {args.interval}"]
        save_json(args.out / "封面下载任务.json", jobs)
        (ROOT / "scripts/下载缺失封面.sh").write_text("\n".join(commands) + "\n", encoding="utf-8")
    stats = {"generated_at": now(), "selected_unique_ids": len(ids),
             "works_with_description": sum(bool(r.get("description")) for r in output),
             "works_with_cover_file": sum(r["cover_status"] == "已下载并校验" for r in output),
             "work_error_count": sum(bool(r["error"]) for r in output),
             "ranking_rows_preserved": len(joined),
             "ranking_rows_with_description": sum(bool(r["description"]) for r in joined),
             "ranking_link_status": dict(Counter(r["link_status"] for r in joined)),
             "robots_checked_at": robots_capture, "offline": args.offline,
             "download_plan_exported": args.export_download_plan,
             "limits": "样本ID为同名/季号匹配候选；简介封面为采集时快照；同简介或同封面不能直接合并作品或季数"}
    save_json(args.out / "采集统计.json", stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)
    if stats["work_error_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
