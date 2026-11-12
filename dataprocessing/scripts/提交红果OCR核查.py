"""提交已完成的逐图核查登记；校验范围、原图哈希及字段，保留前后对照。"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from 持续补采 import ROOT

DEST = ROOT / 'data/红果400条交付/OCR核查_20261112'
FIELDS = ['rank_ocr', 'title_raw', 'producer_raw', 'maker_rights_raw', 'content_type_raw', 'metric_raw']
stage = json.loads((DEST / '人工逐图核查登记.json').read_text())
initial = {r['ranking_id']: r for r in json.loads((DEST / '待核261条.json').read_text())}
assert set(stage) == set(initial) and len(stage) == 261
corrections_path = ROOT / 'data/月榜_已核对补录.json'
corrections = json.loads(corrections_path.read_text())
audit, changes = [], []
for rid, r in sorted(stage.items()):
    assert r['fields_reviewed'] == FIELDS
    assert r['before'] == {k: initial[rid][k] for k in FIELDS}
    assert hashlib.sha256((ROOT / r['source_image']).read_bytes()).hexdigest() == r['source_image_sha256']
    assert (ROOT / r['contact_sheet']).is_file()
    assert r['changed_fields'] == [k for k in FIELDS if r['before'][k] != r['after'][k]]
    old = corrections.get(rid, {})
    note = r['after'].get('review_notes', '')
    # 初始机械疑点已经逐图解决，原图特殊信息由本次具体核查注释保留。
    update = {**old, **{k: r['after'][k] for k in FIELDS},
              'review_status': '已对照原图行裁片逐字段核查', 'review_notes': note}
    corrections[rid] = update
    audit.append({'ranking_id': rid, 'review_status': update['review_status'],
                  **{f'before_{k}': r['before'][k] for k in FIELDS},
                  **{f'after_{k}': r['after'][k] for k in FIELDS},
                  'changed_fields': '；'.join(r['changed_fields']),
                  'review_notes': note, **{k: r[k] for k in ['source_image', 'source_image_sha256',
                     'contact_sheet', 'crop_center_y', 'review_method', 'reviewed_at']}})
    for k in r['changed_fields']:
        changes.append({'ranking_id': rid, 'field': k, 'before': r['before'][k],
                        'after': r['after'][k], 'source_image': r['source_image'],
                        'source_image_sha256': r['source_image_sha256'], 'review_notes': note})
tmp = corrections_path.with_suffix('.json.tmp')
tmp.write_text(json.dumps(corrections, ensure_ascii=False, indent=2) + '\n')
tmp.replace(corrections_path)
for name, rows in [('逐条核查前后对照', audit), ('实际字段修正', changes)]:
    (DEST / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    with (DEST / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
summary = {'reviewed_new_rows': len(audit), 'reviewed_by_month': dict(Counter(initial[k]['month'] for k in stage)),
           'changed_rows': sum(bool(r['changed_fields']) for r in stage.values()),
           'changed_fields': len(changes), 'source_anomaly_notes': [r for r in audit if r['review_notes']],
           'scope': '红果7—10月剩余261条；既有139条已核，合计400条。抖音未新增核查。',
           'limits': '核查确认榜图文字转录，不确认作品历史版本、出品企业主体、AI制作或改编授权。已有原榜第84行印为83的注释不改。'}
(DEST / '核查汇总.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k != 'source_anomaly_notes'}, ensure_ascii=False))
