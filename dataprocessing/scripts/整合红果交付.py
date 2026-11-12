"""整合红果 400 条榜单材料；区分原始 HTML、网页工具快照和补充来源。"""
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from 持续补采 import ROOT, OUT

DEST = ROOT / 'data/红果400条交付'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_records(name, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    for suffix in ['json', 'csv']:
        path = DEST / (name + '.' + suffix)
        tmp = path.with_suffix(path.suffix + '.tmp')
        if suffix == 'json':
            tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        else:
            with tmp.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fields)
                writer.writeheader()
                writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                  for k, v in r.items()} for r in rows)
        tmp.replace(path)


def attach_files(r, material_id, source_kind):
    r = dict(r)
    src = ROOT / r['source_file']
    assert src.exists() and digest(src) == r['source_sha256'], str(src)
    cover = ROOT / r['cover_file']
    with Image.open(cover) as im:
        im.load()
        fmt, width, height = im.format, im.width, im.height
    sha = digest(cover)
    assert sha == r.get('cover_sha256', sha), str(cover)
    ext = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'AVIF': 'avif'}[fmt]
    portable = Path('covers') / (material_id + '.' + ext)
    target = DEST / portable
    if not target.exists() or digest(target) != sha:
        shutil.copyfile(cover, target)
    assert digest(target) == sha
    r.update(material_id=material_id, source_kind=source_kind,
             original_cover_file=r['cover_file'], cover_file=str(portable),
             cover_sha256=sha, cover_format=fmt, cover_width=width, cover_height=height,
             description_char_count=len(r['description']))
    assert len(r['description'].strip()) > 20
    return r


def cached_primary(rid, sid, stem, title, episode_count, cover_url):
    src = OUT / 'raw' / (stem + '_红果网页工具快照.json')
    snapshot = json.loads(src.read_text())
    result = snapshot['result']
    assert isinstance(result, str) and title in result
    description = re.search(r'^L26: (?:简介：)?(.+)$', result, re.M)[1]
    cover = OUT / 'covers' / (sid + '.jpg')
    return {'ranking_id': rid, 'ranking_title': title, 'title': title,
            'platform_work_id': sid, 'episode_count': episode_count,
            'description': description, 'cover_url': cover_url,
            'cover_file': str(cover.relative_to(ROOT)),
            'source_url': snapshot['source_url'], 'source_file': str(src.relative_to(ROOT)),
            'source_sha256': digest(src), 'captured_at': snapshot['retrieved_at']['current_time'],
            'metadata_method': snapshot['method'],
            'first_visible_time': '',
            'identity_status': '红果网页工具快照中完整剧名/季数一致；历史版本身份待核实',
            'snapshot_scope': '网页工具返回的已抓取页面文本，不等于当前HTTP原始HTML；未取得首见时间'}


def main():
    DEST.mkdir(exist_ok=True)
    (DEST / 'covers').mkdir(exist_ok=True)
    ranks = [r for r in csv.DictReader((ROOT / 'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig'))
             if r['platform'] == '红果']
    ranks.sort(key=lambda r: (r['month'], int(r['rank'])))
    assert len(ranks) == len({r['ranking_id'] for r in ranks}) == 400
    strict = json.loads((OUT / '上榜记录_简介封面增量.json').read_text())
    byid = {r['ranking_id']: attach_files(r, 'HG_' + r['platform_work_id'], '红果原始HTML') for r in strict}
    # 两个本地 HTTP 返回 404 的入口仍有网页工具可读快照，单独保存取回方法。
    cache = [
        cached_primary('2026-10_红果_066', '7689391734379269144', '牢狱', '牢狱蒙尘，都市起风云第一季', 100,
                       'https://p6-novel.byteimg.com/novel-pic/a11326a79d9ad1f4a51249a9ac32393e~tplv-shrink:640:0.image'),
        cached_primary('2026-10_红果_067', '7690596204589091864', '硬币', '一块钱硬币，玩出万亿商业帝国', 298,
                       'https://p3-novel.byteimg.com/novel-pic/d461eca2ace4579870d8c78243c39eb2~tplv-shrink:640:0.image'),
    ]
    for r in cache:
        if r['ranking_id'] not in byid:
            byid[r['ranking_id']] = attach_files(r, 'HG_' + r['platform_work_id'], '红果网页工具快照')
    supplement = json.loads((OUT / '红果9条公开补充资料.json').read_text())
    for r in supplement:
        if r['ranking_id'] not in byid:
            byid[r['ranking_id']] = attach_files(r, 'SUP_' + r['ranking_id'], '其他公开来源')
    ambiguous = [json.loads(l) for l in (ROOT / 'data/红果简介封面/补采/同名各版本_全部候选简介.jsonl').read_text().splitlines()]
    alternate = {}
    for r in ambiguous:
        if r['ranking_id'] in byid or not r['visible_before_month_end']:
            continue
        sid = r['platform_work_id']
        r['cover_file'] = str((OUT / 'covers' / ('version_' + sid + '.jpg')).relative_to(ROOT))
        alternate.setdefault(r['ranking_id'], []).append(attach_files(r, 'HG_' + sid, '红果原始HTML'))
    assert set(byid) | set(alternate) == {r['ranking_id'] for r in ranks}
    rows, materials, pending = [], [], []
    for rank in ranks:
        rid = rank['ranking_id']
        bundle = [byid[rid]] if rid in byid else alternate[rid]
        selected = bundle[0] if len(bundle) == 1 else {}
        kind = selected.get('source_kind', '同名多版本待判定')
        usage = ('红果同源候选材料；正式分析前核实榜图及历史身份' if kind.startswith('红果') else
                 '其他公开来源，暂不混入红果同源简介主分析' if kind == '其他公开来源' else
                 '两个7月前已存在的同名版本都已保存；未确定榜单对应哪一个，主分析暂排除')
        r = {**rank, 'material_status': kind, 'material_count': len(bundle),
             'material_ids': [m['material_id'] for m in bundle],
             'selected_material_id': selected.get('material_id', ''),
             'platform_work_id': selected.get('platform_work_id', ''),
             'current_title': selected.get('title', selected.get('ranking_title', '')),
             'description': selected.get('description', ''),
             'cover_file': selected.get('cover_file', ''),
             'description_source_url': selected.get('source_url', ''),
             'source_file': selected.get('source_file', ''),
             'source_sha256': selected.get('source_sha256', ''),
             'cover_url': selected.get('cover_url', ''),
             'cover_sha256': selected.get('cover_sha256', ''),
             'identity_status': selected.get('identity_status', usage),
             'analysis_usage': usage}
        rows.append(r)
        for m in bundle:
            materials.append({**m, 'ranking_id': rid, 'month': rank['month'], 'rank': rank['rank'],
                              'ranking_title': rank['title_raw'], 'selected_for_row': len(bundle) == 1})
        if not kind.startswith('红果'):
            pending.append({k: r[k] for k in ['ranking_id', 'month', 'rank', 'title_raw', 'material_status',
                                              'material_ids', 'description_source_url', 'identity_status', 'analysis_usage']})
    counts = Counter(r['material_status'] for r in rows)
    unique = {m['material_id']: m for m in materials}
    # 真正检验全部材料的文件、来源和主键，而不是只统计非空字符串。
    assert len(rows) == 400 and len(materials) >= 400
    assert all((DEST / m['cover_file']).exists() for m in materials)
    summary = {'generated_at': datetime.now(timezone.utc).isoformat(), 'ranking_rows': len(rows),
               'rows_with_description_and_cover_materials': len(rows),
               'rows_with_single_selected_material': sum(r['material_count'] == 1 for r in rows),
               'source_counts': dict(counts), 'material_links': len(materials),
               'unique_materials_and_valid_covers': len(unique), 'pending_primary_or_version_rows': len(pending),
               'limits': '材料覆盖400条不代表400条红果版本已核实。392条原始HTML候选、2条网页工具快照候选、5条其他来源、1条两个同名版本。封面和简介为采集时或工具可读快照，不代表上榜当月版本。',
               'validation': '400条主键与原始红果榜表一致；每条至少一套完整简介和可解码封面；原始来源及封面SHA256逐项一致；同名版本未强制选择；复制后封面哈希一致'}
    write_records('红果400条_简介封面总表', rows)
    write_records('简介封面材料明细', materials)
    write_records('仍需核实的6条', pending)
    (DEST / '采集校验结果.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    lines = ['# 红果400条简介与封面材料', '',
             '范围为2026年7—10月红果月榜，每月100条。总表保留榜单原名、名次和OCR核查状态。', '',
             f'- {counts["红果原始HTML"]}条：已取得红果原始HTML、对应简介和封面。',
             f'- {counts["红果网页工具快照"]}条：取得网页工具返回的红果页面文本与原图，当前本地HTTP请求返回404；取回方法另列。',
             f'- {counts["其他公开来源"]}条：已有同名/同季公开简介和封面，红果原页与版本待补核。',
             f'- {counts["同名多版本待判定"]}条：《这个神医会功夫！》77集和98集两套材料均保存，未强选其一。', '',
             f'400条都有至少一套可查的简介与封面材料，399条有单一材料选择，共{len(unique)}套去重材料。不得将这一覆盖率写成400条红果原页版本全部核实。', '',
             '## 文件使用', '',
             '- `红果400条_简介封面总表.csv`：一行一条上榜记录，UTF-8 BOM；同名JSON保留列表字段，不另存重复JSONL。',
             '- `简介封面材料明细.csv`：一行一条材料关联。同名未定行对应两条材料；同一作品跨月仍保留每条上榜记录。',
             '- `covers/`：按材料编号保存原图，扩展名按实际文件格式填写，未重绘或改图。',
             '- `仍需核实的6条.csv`：5条缺红果原页和1条版本歧义。后续优先只处理此表。',
             '- `采集校验结果.json`：主键、文件解码、来源及图片哈希检验结果。', '',
             '这里按作品候选版本保存封面文件，文件份数不等于内容不同的图片数。最新图片内容去重与重复上榜统计见`重复核查/查重统计.json`；`重复核查/封面到作品和榜单对应.csv`逐项关联图片内容分组、作品版本和上榜记录。', '',
             '按系列合并的最新版在`系列合并/`，包含系列汇总、以系列号—季号为ID的季作品表、400条上榜映射、封面对应、出品署名及原著作者候选关系。', '',
             '出品方与原著的最新证据核实在`关系核实/说明.md`、`关系核实/改编证据登记.csv`、`关系核实/系列_原著作者关系.csv`与`关系核实/出品品牌_主体_系列季关系.csv`。基础候选与证据核实分开维护。', '',
             '全部上榜作品的公开热评采集见`评论全覆盖/说明.md`、`评论全覆盖/评论主表.csv`与`评论全覆盖/上榜记录覆盖.csv`。覆盖作品入口与抓取全部历史评论不同，旧分层样本单独保留。', '',
             '表内cover_file相对于本目录；source_file和original_cover_file相对于dataprocessing目录，原始来源快照保留在原有data目录，未重复复制HTML。', '',
             '## 分析口径', '',
             '红果原始HTML与网页工具快照均保留候选身份标签，不能自动声称已核实历史月榜版本。人工核对的改名和同名版本证据见identity_review_file及data/补采/红果身份人工核对.json。', '',
             '其他来源的简介可能重写或使用不同版本，只作补充材料，不直接混入红果同源简介主分析。同名未定作品未填单一description或cover_file，请按material_ids查看两套材料。月榜还有待核OCR行，正式结论应保留该限制。', '',
             '## 仍需核实', '']
    lines.extend(f'- {r["ranking_id"]} {r["title_raw"]}：{r["material_status"]}' for r in pending)
    (DEST / '说明.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
