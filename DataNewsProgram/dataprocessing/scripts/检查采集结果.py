"""检查月榜覆盖、去重映射、平台系列编号与来源文件。"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from 作品匹配 import ROOT, DATA, OUT


def read_csv(path):
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def main():
    ranks = read_csv(DATA / "月榜_OCR待核查.csv")
    rows = read_csv(OUT / "上榜记录_作品系列映射.csv")
    assert len(ranks) == len({r["ranking_id"] for r in ranks}) == len(rows)
    assert {r["ranking_id"] for r in ranks} == {r["ranking_id"] for r in rows}
    raw_by_id={r['ranking_id']:r for r in ranks}
    source_fields=['month','platform','rank','rank_ocr','title_raw','producer_raw','affiliate_raw','maker_rights_raw','content_type_raw','metric_raw','metric_name','source_url','source_image','review_status','review_notes']
    for row in rows:
        assert all(row[k]==raw_by_id[row['ranking_id']][k] for k in source_fields), '月榜核对更新尚未同步至映射：'+row['ranking_id']
    for group in {(r["month"], r["platform"]) for r in ranks}:
        assert sorted(int(r["rank"]) for r in ranks if (r["month"], r["platform"]) == group) == list(range(1, 101))
    assert all(r["title_raw"] and r["metric_raw"] for r in ranks)
    for r in ranks:
        if r['review_status'].startswith('已') and int(r['rank'])>=4:
            assert r['rank_ocr']==r['rank'] or (r['rank']=='84' and r['rank_ocr']=='83' and '原图该行名次印为83' in r['review_notes']), '已核记录名次尚未回填，或原图名次异常未另记：'+r['ranking_id']
    manifest = json.loads((DATA / "raw/monthly_rankings/manifest.json").read_text())
    for source in manifest:
        assert hashlib.sha256((ROOT / source["image_file"]).read_bytes()).hexdigest() == source["image_sha256"]
    works = {w["platform_work_id"]: w for w in map(json.loads, (OUT / "平台作品索引.jsonl").read_text().splitlines())}
    by_id = defaultdict(set)
    for row in rows:
        if row["platform_work_id"]:
            assert row["work_id"] == "HG_" + row["platform_work_id"]
            by_id[row["platform_work_id"]].add(row["candidate_work_id"])
        if row["franchise_id"]:
            w = works[row["platform_work_id"]]
            assert row["franchise_id"] == "HG_GROUP_" + w["platform_group_id"]
            assert (ROOT / w["group_evidence_file"]).exists()
    assert all(len(group) == 1 for group in by_id.values()), "同一个平台ID被拆成多个去重候选"
    candidates = read_csv(OUT / "作品去重候选表.csv")
    assert sum(int(c["ranking_count"]) for c in candidates) == len(rows)
    report = {"total_rows": len(ranks), "verified_rows": sum(r["review_status"].startswith("已") for r in ranks),
              "pending_rows": sum(r["review_status"].startswith("待") for r in ranks),
              "empty_title_rows": sum(not r["title_raw"] for r in ranks), "empty_metric_rows": sum(not r["metric_raw"] for r in ranks),
              "image_hashes_passed": len(manifest),
              "mechanically_flagged_pending_rows": sum(bool(r["review_notes"]) and r["review_status"].startswith("待") for r in ranks),
              "limits": "机械检查通过不代表待核OCR和所有作品身份已人工核实；本轮范围为7—10月，5—6月不纳入补采。"}
    (DATA / "月榜_采集检查.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    result = {"checks": "通过：主键、每榜名次覆盖、映射不丢行、ID一致性、平台group_id来源、来源文件哈希",
              "ranking_rows": len(rows), "candidate_works": len(candidates),
              "work_metadata_files": len(list((DATA / "raw/work_catalogs").glob("*.html"))),
              "monthly_review": report}
    (OUT / "结果检查.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
