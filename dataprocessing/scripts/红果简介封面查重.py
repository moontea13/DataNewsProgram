"""检查已采集红果样本的重复上榜、相同简介和相同/近似封面。

python3 scripts/红果简介封面查重.py
相似度只生成核查线索，不自动删除作品、不改月榜映射。
"""
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageOps, ImageStat

from 采集红果简介封面 import ROOT, OUT, normalized, now, save_json, save_records


def trigrams(text):
    text = normalized(text)
    return Counter(text[i:i + 3] for i in range(len(text) - 2))


def cosine(a, b):
    denom = math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    return sum(v * b[k] for k, v in a.items()) / denom if denom else 0.0


def cover_features(path):
    with Image.open(path) as im:
        rgb = ImageOps.exif_transpose(im).convert("RGB")
        pixel_sha = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        gray = rgb.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px = list(gray.get_flattened_data())
        bits = sum(int(px[y * 9 + x] > px[y * 9 + x + 1]) << (y * 8 + x)
                   for y in range(8) for x in range(8))
        return {"pixel_sha256": pixel_sha, "dhash": bits,
                "grayscale_stdev": ImageStat.Stat(rgb.convert("L")).stddev[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=OUT / "红果简介封面.jsonl")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--text-threshold", type=float, default=0.8)
    parser.add_argument("--cover-distance", type=int, default=6)
    args = parser.parse_args()
    if not 0 < args.text_threshold <= 1 or not 0 <= args.cover_distance <= 64:
        parser.error("阈值超出范围")
    works = [json.loads(line) for line in args.input.read_text().splitlines()]
    args.out.mkdir(parents=True, exist_ok=True)
    if len({w["platform_work_id"] for w in works}) != len(works):
        raise ValueError("输入同一作品ID出现多次；先修复采集主键")
    features, grams, audits, repeats = {}, {}, [], []
    for work in works:
        sid = work["platform_work_id"]
        grams[sid] = trigrams(work.get("description", ""))
        src = Path(work.get("source_file", ""))
        if not src.is_absolute():
            src = ROOT / src
        good_source = src.is_file() and hashlib.sha256(src.read_bytes()).hexdigest() == work.get("source_sha256")
        raw = work.get("cover_file", "")
        cover = Path(raw) if raw else None
        if cover and not cover.is_absolute():
            cover = ROOT / cover
        good_cover = bool(cover and cover.is_file() and hashlib.sha256(cover.read_bytes()).hexdigest() == work.get("cover_sha256"))
        if good_cover:
            features[sid] = cover_features(cover)
        audits.append({"platform_work_id": sid, "title": work["title"], "source_hash_ok": good_source,
                       "cover_hash_ok": good_cover, "description_nonempty": bool(work.get("description"))})
        if len(work.get("ranking_ids", [])) > 1:
            repeats.append({"platform_work_id": sid, "title": work["title"],
                            "ranking_count": len(work["ranking_ids"]), "ranking_ids": work["ranking_ids"],
                            "months": work["ranking_months"],
                            "decision": "同ID只保留一份简介和封面；每月上榜记录全部保留；榜单身份仍为匹配候选"})
    pairs = []
    for a, b in combinations(works, 2):
        aid, bid = a["platform_work_id"], b["platform_work_id"]
        text_exact = bool(a.get("description")) and normalized(a["description"]) == normalized(b.get("description", ""))
        score = cosine(grams[aid], grams[bid])
        enough_text = min(len(normalized(a.get("description", ""))), len(normalized(b.get("description", "")))) >= 60
        text_near = enough_text and score >= args.text_threshold
        fa, fb = features.get(aid), features.get(bid)
        cover_exact = bool(fa and fb and fa["pixel_sha256"] == fb["pixel_sha256"])
        distance = (fa["dhash"] ^ fb["dhash"]).bit_count() if fa and fb else None
        cover_near = distance is not None and distance <= args.cover_distance and min(fa["grayscale_stdev"], fb["grayscale_stdev"]) > 5
        if not (text_exact or text_near or cover_exact or cover_near):
            continue
        ag, bg = a.get("platform_group_id"), b.get("platform_group_id")
        same_group = bool(ag and bg and ag == bg)
        relation = "同一平台系列编号" if same_group else "平台系列编号不同" if ag and bg else "系列关系尚不明确"
        signals = (["规范化后简介全文相同"] if text_exact else ["简介文字高度相似"] if text_near else [])
        signals += ["封面像素完全相同"] if cover_exact else ["封面dHash接近"] if cover_near else []
        pairs.append({"id_a": aid, "title_a": a["title"], "id_b": bid, "title_b": b["title"],
                      "signals": signals, "description_exact": text_exact, "text_cosine_3gram": round(score, 6),
                      "cover_pixel_exact": cover_exact, "cover_dhash_distance": distance,
                      "series_relation": relation, "platform_group_id_a": ag, "platform_group_id_b": bg,
                      "description_a": a.get("description", ""), "description_b": b.get("description", ""),
                      "cover_file_a": a.get("cover_file", ""), "cover_file_b": b.get("cover_file", ""),
                      "source_url_a": a["source_url"], "source_url_b": b["source_url"],
                      "review_status": "待人工核查",
                      "decision": "同系列不同编号作品保留；可能共享宣传素材" if same_group else "需核查版本/宣传素材来源；不凭相似度合并作品"})
    pairs.sort(key=lambda p: (p["series_relation"] == "同一平台系列编号", -p["description_exact"], -p["text_cosine_3gram"]))
    pair_fields = ["id_a", "title_a", "id_b", "title_b", "signals", "description_exact", "text_cosine_3gram",
                   "cover_pixel_exact", "cover_dhash_distance", "series_relation", "platform_group_id_a", "platform_group_id_b",
                   "description_a", "description_b", "cover_file_a", "cover_file_b", "source_url_a", "source_url_b", "review_status", "decision"]
    save_records(args.out, "简介封面重复核查", pairs, pair_fields)
    save_records(args.out, "同ID跨月上榜", repeats)
    save_records(args.out, "素材校验", audits)
    stats = {"generated_at": now(), "unique_work_ids_checked": len(works),
             "ranking_rows_linked": sum(len(w["ranking_ids"]) for w in works),
             "repeated_ranking_work_ids": len(repeats),
             "extra_ranking_rows_for_same_ids": sum(len(w["ranking_ids"]) - 1 for w in works if w["ranking_ids"]),
             "pair_comparisons": len(works) * (len(works) - 1) // 2,
             "candidate_pairs": len(pairs), "pairs_with_exact_description": sum(p["description_exact"] for p in pairs),
             "pairs_with_exact_cover_pixels": sum(p["cover_pixel_exact"] for p in pairs),
             "candidate_pairs_in_same_series": sum(p["series_relation"] == "同一平台系列编号" for p in pairs),
             "candidate_pairs_outside_known_same_series": sum(p["series_relation"] != "同一平台系列编号" for p in pairs),
             "text_threshold": args.text_threshold, "text_method": "规范化中文字符3-gram词频余弦；不是语义相似度",
             "cover_dhash_threshold": args.cover_distance,
             "audit_failures": sum(not all(r[k] for k in ["source_hash_ok", "cover_hash_ok", "description_nonempty"]) for r in audits),
             "limits": "只覆盖已匹配ID的红果子样本；候选不是最终重复作品、抄袭判定或全样本同质化比例；所有作品ID和800条月榜记录保留"}
    save_json(args.out / "查重统计.json", stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats["audit_failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
