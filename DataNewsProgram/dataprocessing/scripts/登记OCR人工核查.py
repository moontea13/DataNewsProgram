"""人工看过联系表后登记指定图；不自行识别或将未查看记录批量标已核。"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from 持续补采 import ROOT, OUT

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('month')
p.add_argument('sheets', nargs='+', type=int)
p.add_argument('--fixes', default='{}', help='ranking_id后缀到字段更正的JSON')
args = p.parse_args()
dest = ROOT / 'data/红果400条交付/OCR核查_20261112'
stage = dest / '人工逐图核查登记.json'
current = json.loads(stage.read_text()) if stage.exists() else {}
rows = json.loads((OUT / ('OCR全核_' + args.month + '_记录.json')).read_text())
fixes = json.loads(args.fixes)
fields = ['rank_ocr', 'title_raw', 'producer_raw', 'maker_rights_raw', 'content_type_raw', 'metric_raw']
for sheet in args.sheets:
    selected = rows[sheet * 10:sheet * 10 + 10]
    for r in selected:
        rid = r['ranking_id']
        updates = fixes.get(rid[-3:], {})
        before = {k: r[k] for k in fields}
        after = {**before, **updates}
        image = ROOT / r['source_image']
        assert hashlib.sha256(image.read_bytes()).hexdigest() == r['source_image_sha256']
        current[rid] = {'before': before, 'after': after,
                        'changed_fields': [k for k in fields if before[k] != after[k]],
                        'contact_sheet': r['contact_sheet'], 'crop_center_y': r['crop_center_y'],
                        'source_image': r['source_image'], 'source_image_sha256': r['source_image_sha256'],
                        'review_method': '逐图视觉比对原榜图行裁片与现表，非仅复跑OCR',
                        'fields_reviewed': fields,
                        'reviewed_at': datetime.now(timezone.utc).isoformat()}
tmp = stage.with_suffix('.json.tmp')
tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n')
tmp.replace(stage)
print('reviewed staged', len(current), 'changed rows', sum(bool(r['changed_fields']) for r in current.values()))
