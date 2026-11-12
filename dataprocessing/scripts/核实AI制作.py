"""把有出处的AI证据逐条关联月榜，区分单季、系列、平台分类和榜单标签。"""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from 作品匹配 import ROOT, DATA, OUT, normalize, write_csv


def main():
    evidence = json.loads((DATA / "AI制作证据登记.json").read_text())
    for item in evidence:
        path = ROOT / item["source_file"]
        text = BeautifulSoup(path.read_text(), "html.parser").get_text(" ", strip=True)
        missing = [term for term in item["validation_terms"] if term not in text]
        if missing:
            raise ValueError(f"{item['evidence_id']} 留存页缺少核对语句：{missing}")
        item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        item["captured_at"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    by_base = {}
    for item in evidence:
        by_base.setdefault(normalize(item["base_title"]), []).append(item)
    rows = list(csv.DictReader((OUT / "上榜记录_作品系列映射.csv").open(encoding="utf-8-sig")))
    audit = []
    for row in rows:
        items = by_base.get(row["base_key"], [])
        season = int(row["season_number"]) if row["season_number"] else None
        direct = [e for e in items if e["level"].startswith("A_") and season in e["explicit_seasons"] and row['review_status'].startswith('已')]
        exact_work = [e for e in items if e["level"].startswith("A_") and normalize(row['title_raw']) in {normalize(t) for t in e.get('explicit_titles',[])} and row['review_status'].startswith('已')]
        series_a = [e for e in items if e["level"].startswith("A_")]
        if direct:
            status = "有本季AI制作直接证据"
            level = "A"
            reason = "主创/现场报道具体覆盖本季；作品版本身份仍见匹配状态"
        elif exact_work:
            status = "有本作品AI制作直接证据（未标季）"
            level = "A_作品"
            reason = "制作方项目资料明确列出完整剧名与AI制作角色；不默认第一季，平台版本身份另核"
        elif series_a:
            status = "系列有AI制作直接证据，本季待核"
            level = "A_仅系列"
            reason = "系列证据不外推到未点名季数"
        elif items:
            status = "媒体明确报道该系列为AI，单季待核"
            level = "B_系列报道"
            reason = "媒体报道未逐季说明制作流程"
        elif row["ai_status"].startswith("平台AI榜"):
            status = "平台AI分类已留证，制作流程待核"
            level = "C_平台分类"
            reason = "只说明该作品在采集时列于平台AI榜，不能证明整个制作流程"
        elif row["content_type_raw"] == "AI仿真人剧":
            status = "仅DataEye标AI仿真人，独立证据待补"
            level = "D_第三方标签"
            reason = "待补平台/主创等来源；OCR未核记录仍需核查标签"
        else:
            status = "AI制作未知"
            level = "U"
            reason = "3D/2D/漫剧名称不等于AI制作；未见证据不等于非AI"
        row.update({"ai_production_status": status, "ai_evidence_level": level,
                    "ai_evidence_ids": "|".join(e["evidence_id"] for e in items),
                    "ai_independent_urls": "|".join(dict.fromkeys(e["source_url"] for e in items)),
                    "ai_evidence_scope_note": reason})
        audit.append({k: row[k] for k in ["ranking_id", "month", "platform", "title_raw", "season_number", "content_type_raw", "review_status", "identity_status", "ai_production_status", "ai_evidence_level", "ai_evidence_ids", "ai_independent_urls", "ai_evidence_url", "ai_evidence_scope_note"]})
    write_csv(OUT / "上榜记录_作品系列映射.csv", rows)
    write_csv(OUT / "AI制作逐条核实.csv", audit)
    (OUT / "AI制作证据_含留存校验.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    stats = {"ranking_rows": len(rows), "status_counts_ranking_rows": dict(Counter(r["ai_production_status"] for r in rows)),
             "evidence_records": len(evidence), "independent_source_pages": len({e["source_file"] for e in evidence}),
             "limits": "按上榜记录计数，非去重作品数。系列证据不能确认每一季；AI未知不得改为非AI；身份及OCR未核仍影响证据关联。"}
    (OUT / "AI核实统计.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
