"""将已下载月榜分块 OCR；输出待核查草稿，不自动确认剧名和系列。

依赖：rapidocr-onnxruntime、pillow。首次可安装：
python3 -m pip install rapidocr-onnxruntime pillow
运行：python3 scripts/识别月榜草稿.py
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from statistics import median, linear_regression

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-cache", type=Path, help="可选：使用本机已有 uv archive-v0 依赖目录，仅用于离线运行")
    parser.add_argument("--month", choices=[f"2026-{m:02}" for m in range(5, 11)])
    parser.add_argument("--reuse-ocr", action="store_true", help="复用已保存文本框，只重新生成草稿表")
    args = parser.parse_args()
    if args.package_cache:
        # 仅添加已安装包的位置，不写入用户缓存；Python 主版本应与缓存包相符。
        for name in ["rapidocr_onnxruntime", "cv2", "onnxruntime", "numpy", "PIL", "yaml", "shapely", "pyclipper", "packaging", "flatbuffers"]:
            matches = sorted(args.package_cache.glob(f"*/{name}"))
            if matches:
                sys.path.insert(0, str(matches[0].parent))
    from PIL import Image
    engine = None
    if not args.reuse_ocr:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
    raw_dir = ROOT / "data/raw/monthly_rankings"
    ocr_dir = ROOT / "data/ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((raw_dir / "manifest.json").read_text())
    verified_path = ROOT / "data/月榜_已核对补录.json"
    verified = json.loads(verified_path.read_text()) if verified_path.exists() else {}
    records = []
    for source in manifest:
        if args.month and source["month"] != args.month:
            continue
        stem = f'{source["month"]}_{source["platform"]}'
        image = Image.open(ROOT / source["image_file"]).convert("RGB")
        if image.size != (1080, 6606):
            raise ValueError("当前行定位只适用于已核对的 1080×6606 版式，请重新检查原图")
        boxes = json.loads((ocr_dir / f"{stem}.json").read_text()) if args.reuse_ocr else []
        # 分块避免超长图整体缩小后文字无法识别；上下重叠，按中心归属去重。
        for top in ([] if args.reuse_ocr else range(0, image.height, 800)):
            crop_top = max(0, top - 40)
            crop_bottom = min(image.height, top + 840)
            tile = image.crop((0, crop_top, image.width, crop_bottom))
            result, _ = engine(np.array(tile)[:, :, ::-1].copy())
            for box, text, confidence in result or []:
                box = [[float(x), float(y + crop_top)] for x, y in box]
                cy = sum(p[1] for p in box) / 4
                if top <= cy < min(top + 800, image.height):
                    boxes.append({"text": text, "confidence": float(confidence), "box": box})
        boxes.sort(key=lambda r: (sum(p[1] for p in r["box"]) / 4, r["box"][0][0]))
        (ocr_dir / f"{stem}.json").write_text(json.dumps(boxes, ensure_ascii=False, indent=2) + "\n")
        # 第 1—3 名在海报卡片中，保留原文供单独校对，不按表格列推断。
        top_text = "\n".join(r["text"] for r in boxes if sum(p[1] for p in r["box"]) / 4 < 1128)
        (ocr_dir / f"{stem}_前三名.txt").write_text(top_text + "\n")
        # 各月列结构不同：7月抖音的“关联方”不是“出品方”；7月红果有制作方列。
        labels = {"排名": "rank_ocr", "剧名": "title_raw", "出品方": "producer_raw",
                  "关联方": "affiliate_raw", "制作方/版权方": "maker_rights_raw",
                  "类型": "content_type_raw", "漫剧类型": "content_type_raw",
                  "播放增量": "metric_raw", "峰值热度": "metric_raw"}
        headers = []
        for item in boxes:
            cy = sum(p[1] for p in item["box"]) / 4
            if 1135 < cy < 1180 and item["text"] in labels:
                headers.append((sum(p[0] for p in item["box"]) / 4, labels[item["text"]]))
        headers.sort()
        if len(headers) not in [5, 6] or len({x[1] for x in headers}) != len(headers):
            raise ValueError(f"{stem} 表头识别不完整或重复：{headers}")
        # 用左侧 OCR 名次拟合各行中心，检查异常锚点，避免固定行高累积偏移。
        anchors = []
        for item in boxes:
            cx = sum(p[0] for p in item["box"]) / 4
            cy = sum(p[1] for p in item["box"]) / 4
            if cx < 145 and 1180 < cy < 6400 and re.fullmatch(r"\d{1,3}", item["text"]):
                value = int(item["text"])
                if 4 <= value <= 100:
                    anchors.append((value, cy))
        if len(anchors) < 50:
            raise ValueError(f"{stem} 不足 50 个名次锚点，请检查原图")
        # 先用该版式的约 52.77px 行高和中位截距排除 OCR 把 90 读成 9 等异常。
        initial_intercept = median([a[1] - 52.77 * a[0] for a in anchors])
        good = [a for a in anchors if abs(52.77 * a[0] + initial_intercept - a[1]) < 15]
        if len(good) < 50:
            raise ValueError(f"{stem} 行位置不稳定，请检查版式")
        slope, intercept = linear_regression([a[0] for a in good], [a[1] for a in good])
        if not 48 < slope < 57:
            raise ValueError(f"{stem} 行高不符合预期：{slope}")
        for rank in range(1, 101):
            cells = {name: [] for _, name in headers}
            conf = []
            if rank >= 4:
                cy_expected = slope * rank + intercept
                for item in boxes:
                    box = item["box"]
                    cx = sum(p[0] for p in box) / 4
                    cy = sum(p[1] for p in box) / 4
                    if abs(cy - cy_expected) > slope / 2 - 1:
                        continue
                    column = min(headers, key=lambda h: abs(cx - h[0]))[1]
                    cells[column].append(item)
                    conf.append(item["confidence"])
            texts = {}
            for name, cell in cells.items():
                cell.sort(key=lambda x: (x["box"][0][1], x["box"][0][0]))
                texts[name] = " ".join(x["text"] for x in cell)
            rank_ocr, title, producer, rights, content_type, metric = [texts.get(name, "") for name in ["rank_ocr", "title_raw", "producer_raw", "maker_rights_raw", "content_type_raw", "metric_raw"]]
            problems = []
            if rank <= 3:
                problems.append("前三名卡片需单独转录")
            else:
                if not title:
                    problems.append("剧名为空")
                if re.sub(r"\s", "", rank_ocr) != str(rank):
                    problems.append("OCR名次与位置推定不一致")
                if not metric:
                    problems.append("指标为空")
                elif not re.fullmatch(r"\d+(?:\.\d+)?[万亿]", metric):
                    problems.append("指标格式需核查")
                if conf and min(conf) < 0.9:
                    problems.append("存在低置信度文字")
            record = {
                "ranking_id": f'{source["month"]}_{source["platform"]}_{rank:03}',
                "month": source["month"], "platform": source["platform"], "rank": rank,
                "rank_ocr": rank_ocr, "title_raw": title, "producer_raw": producer,
                "affiliate_raw": texts.get("affiliate_raw", ""),
                "maker_rights_raw": rights, "content_type_raw": content_type,
                "metric_raw": metric, "metric_name": source["metric"],
                "source_url": source["article_url"], "source_image": source["image_file"],
                "review_status": "待对照原图逐行核查", "review_notes": "；".join(problems),
                "work_id": "", "ai_status": "待核实",
            }
            if record["ranking_id"] in verified:
                record.update(verified[record["ranking_id"]])
            records.append(record)
        print(f"{stem}: {len(boxes)} 个文本框，100 个核查槽位", flush=True)
    suffix = f"_{args.month}" if args.month else ""
    out = ROOT / f"data/月榜_OCR待核查{suffix}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"已写入 {out}；槽位数不等于已完整识别数。", flush=True)


if __name__ == "__main__":
    main()
