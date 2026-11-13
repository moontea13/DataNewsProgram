"""从冻结的人工可审候选编码生成标注表、四项指标及可视化数据。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent
ANN = BASE / 'annotations'
REVIEW = BASE / 'review'
SEED = 20261113
VERSION = '2026-11-13-candidate-v0.1'
CONFLICT = {'0': '其他／未交代', '1': '受辱排斥', '2': '背叛陷害', '3': '生存威胁', '4': '资源与事业竞争', '5': '婚恋家庭冲突', '6': '修炼与实力竞争', '7': '权力与家国冲突', '8': '探案解谜'}
TURN = {'0': '其他／未交代', '1': '重生预知', '2': '穿越带来的知识技能', '3': '系统奖励', '4': '超常能力或体质', '5': '特殊器物或资源', '6': '身份与权势揭示', '7': '关系支持', '8': '常规知识与训练', '9': '无特殊转机'}
RESPONSE = {'0': '其他／未交代', '1': '武力对抗', '2': '公开揭露与正名', '3': '谋略设局', '4': '经营与资源配置', '5': '专业知识技术破局', '6': '协作互助', '7': '关系协商与修复'}
SCOPES = {'x': '不同系列', 's': '同系列跨季', 'i': '同剧内部', 'u': '未说明', '?': '待人工判断'}
OBJECTS = dict(P='剧情套路', H='人设与人物关系', F='角色外形', V='画风与场景', T='台词', A='配音', B='配乐音效', G='综合未具体说明')
ATTITUDES = dict(n='反感重复', y='接受或喜爱重复', d='肯定差异', m='褒贬混合', o='未表态')
SOURCE_FILES = [ROOT / 'dataprocessing/data/红果400条交付' / name for name in ['系列合并/上榜记录_系列季映射.csv', '系列合并/季作品表.csv', '评论全覆盖/评论主表.csv']]


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    keys = fields or list(dict.fromkeys(k for row in rows for k in row)) or ['status']
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def lines(path):
    return [line.split() for line in path.read_text(encoding='utf-8').splitlines() if line and not line.startswith('#')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate(a, b):
    return a / b if b else None


def novelty(rows):
    seen_work, seen_series, seen_clusters = set(), set(), set()
    result, detail, reuse = [], [], []
    previous_members = defaultdict(set)
    for month in sorted({x['month'] for x in rows}):
        group = [x for x in rows if x['month'] == month]
        works = {x['work_id'] for x in group}
        series = {x['series_id'] for x in group}
        clusters = {x['cluster_id'] for x in group if x['cluster_id']}
        new_series = series - seen_series
        new_work = works - seen_work
        new_clusters = clusters - seen_clusters
        current = {x['series_id']: x for x in group}
        codable = {s for s in new_series if current[s]['cluster_id']}
        reused = {s for s in codable if current[s]['cluster_id'] in seen_clusters}
        result.append(dict(month=month, baseline=not seen_work, new_work_count=len(new_work), new_series_count=len(new_series),
                           new_cluster_count=len(new_clusters), new_work_ids=sorted(new_work), new_series_ids=sorted(new_series),
                           new_cluster_ids=sorted(new_clusters), month_codable_series_count=len({x['series_id'] for x in group if x['cluster_id']}),
                           month_unassigned_series_count=len({x['series_id'] for x in group if not x['cluster_id']})))
        reuse.append(dict(month=month, baseline=not seen_work, reused_series_count=len(reused), new_structure_series_count=len(codable - reused),
                          codable_new_series_count=len(codable), unassigned_new_series_count=len(new_series - codable),
                          reuse_ratio=rate(len(reused), len(codable)) if seen_work else None,
                          status='基线，不解释此前沿用' if not seen_work else '无可分簇新系列' if not codable else '可计算',
                          reused_series_ids=sorted(reused), new_structure_series_ids=sorted(codable - reused)))
        for sid in sorted(new_series):
            row = current[sid]
            cid = row['cluster_id']
            earlier = sorted(previous_members[cid]) if cid else []
            detail.append(dict(month=month, series_id=sid, title=row['title'], cluster_id=cid,
                               reuse_category='基线' if not seen_work else '结构未确定' if not cid else '沿用此前结构' if earlier else '进入当月新结构',
                               earlier_same_cluster_series_ids=earlier, evidence_excerpt=row['evidence_excerpt']))
        # 当月全部判定结束以后才扩充累计集合，防止同月新系列被误算为沿用。
        seen_work |= works
        seen_series |= series
        seen_clusters |= clusters
        for x in group:
            if x['cluster_id']:
                previous_members[x['cluster_id']].add(x['series_id'])
    return result, reuse, detail


def validate_inputs(data):
    r, w, c = data['rankings'], data['works'], data['comments']
    for name, rows, key in [('上榜记录', r, 'ranking_id'), ('作品', w, 'work_id'), ('评论', c, 'comment_key')]:
        assert len(rows) == len({x[key] for x in rows}), f'{name}主键重复'
    work = {x['work_id']: x for x in w}
    assert all(x['work_id'] in work and work[x['work_id']]['series_id'] == x['series_id'] for x in r + c)
    assert all(len([x for x in r if x['month'] == m]) == 100 for m in {x['month'] for x in r})
    assert all(sorted(int(x['rank']) for x in r if x['month'] == m) == list(range(1, 101)) for m in {x['month'] for x in r})
    # 核对冻结编号所对应的原文，防止候选编码错贴到更新后的输入。
    raw = [read_csv(p) for p in SOURCE_FILES]
    for stored, actual, key in zip([r, w, c], raw, ['ranking_id', 'work_id', 'comment_key']):
        assert len(stored) == len(actual)
        actual_map = {x[key]: x for x in actual}
        assert all(all(x[k] == value for k, value in actual_map[x[key]].items()) for x in stored)
    return dict(ranking_count=len(r), work_count=len(w), series_count=len({x['series_id'] for x in w}), comment_count=len(c),
                selected_comment_count=sum(x['selected_for_row'] == 'True' for x in c),
                unselected_comment_count=sum(x['selected_for_row'] != 'True' for x in c),
                original_promo_flags=sum(x['possible_creator_or_promo'] == 'True' for x in c))


def load_structure(data):
    codes = {x[0]: x[1:] for x in lines(ANN / 'description_codes.tsv')}
    core_codes = {x[0]: x[1:] for x in lines(ANN / 'series_core_codes.tsv')}
    assert set(codes) == {d['id'] for d in data['descriptions']}
    cluster_specs, assignment = [], {}
    for cid, name, rule, members, boundary in lines(ANN / 'cluster_design.tsv'):
        series = members.split(',')
        cluster_specs.append(dict(cluster_id=cid, cluster_name=name, common_chain=rule, inclusion_rule=rule,
                                  nearest_cluster_difference=boundary, anonymous_members=series, review_status='AI初标'))
        for member in series:
            assert member not in assignment
            assignment[member] = cid
    unresolved = {x[0]: x[1] for x in lines(ANN / 'series_unresolved.tsv')}
    assert not set(assignment) & set(unresolved)
    assert set(assignment) | set(unresolved) == {x['anon_series'] for x in data['works']}
    catalog = {x['cluster_id']: x for x in cluster_specs}
    works = []
    for w in data['works']:
        a, b, d = codes[w['description_id']]
        tags = [CONFLICT[a], TURN[b], RESPONSE[d]]
        evidence = w['description']
        complete = '0' not in [a, b, d]
        works.append(dict(work_id=w['work_id'], series_id=w['series_id'], anonymous_series=w['anon_series'], title=w['title'],
                          season_code=w['season_code'], description_id=w['description_id'], description=evidence,
                          core_conflict=tags[0], turning_mechanism=tags[1], response_path=tags[2],
                          conflict_evidence=evidence, mechanism_evidence=evidence, response_evidence=evidence,
                          label_reason='逐简介语义初标；三个字段分别依据该简介全段。未交代的字段保留缺项，不补推结局。',
                          template_key='|'.join(tags), three_fields_complete=complete,
                          material_ids=w['material_ids'], source_url=w['description_source_url'],
                          source_file=w['group_evidence_file'], source_sha256=w['group_evidence_sha256'],
                          review_status='信息不足' if not evidence else 'AI初标' if complete else '待人工判断'))
    first_rank = {}
    for r in data['rankings']:
        pair = (r['month'], int(r['rank']))
        if r['work_id'] not in first_rank or pair < first_rank[r['work_id']]:
            first_rank[r['work_id']] = pair
    grouped = defaultdict(list)
    for w in works:
        grouped[w['series_id']].append(w)
    series = []
    for sid, ws in sorted(grouped.items()):
        ordered = sorted(ws, key=lambda w: first_rank[w['work_id']])
        core=core_codes[ordered[0]['anonymous_series']]
        core_tags=[CONFLICT[core[0]],TURN[core[1]],RESPONSE[core[2]]]
        candidates = [w for w in ordered if w['three_fields_complete'] and [w['core_conflict'],w['turning_mechanism'],w['response_path']]==core_tags]
        representative = (candidates or ordered)[0]
        anon = representative['anonymous_series']
        cid = assignment.get(anon, '')
        incomplete = unresolved.get(anon, '')
        reason = catalog[cid]['inclusion_rule'] if cid else incomplete
        member_reason=(f'该系列候选核心为“{core_tags[0]}→{core_tags[1]}→{core_tags[2]}”；'
                       f'与候选簇共享“{reason}”。原文及逐季差异分别保留，可逐成员核对。') if cid else incomplete
        series.append(dict(series_id=sid, anonymous_series=anon,
                           series_title=next(w['series_title'] for w in data['works'] if w['series_id'] == sid),
                           representative_work_id=representative['work_id'], representative_title=representative['title'],
                           representative_selection='能够完整支持共同核心三字段的简介中，观察期入榜最早；同月按排名' if candidates else '无完整支持共同核心的简介，保留最早材料待审',
                           core_conflict=core_tags[0], turning_mechanism=core_tags[1],
                           response_path=core_tags[2], template_key='|'.join(core_tags),
                           core_narrative=reason, cluster_id=cid, cluster_name=catalog[cid]['cluster_name'] if cid else '',
                           assignment_reason=member_reason,
                           evidence_excerpt=representative['description'], source_url=representative['source_url'],
                           season_evidence=[dict(work_id=w['work_id'], title=w['title'], description=w['description'],
                                                 template_key=w['template_key'], source_url=w['source_url']) for w in ordered],
                           disagreement_note=incomplete or '逐季细标签保留差异；共同核心与成员边界等待人工校审。',
                           review_status='信息不足' if not representative['description'] else '待人工判断' if incomplete else 'AI初标'))
    for cluster in cluster_specs:
        members = [s for s in series if s['cluster_id'] == cluster['cluster_id']]
        cluster.update(member_series_ids=[s['series_id'] for s in members], member_titles=[s['series_title'] for s in members],
                       member_count=len(members), representative_series_id=members[0]['series_id'],
                       representative_title=members[0]['series_title'], representative_evidence=members[0]['evidence_excerpt'],
                       member_reasons=[dict(series_id=s['series_id'], rule=cluster['inclusion_rule'], assignment_reason=s['assignment_reason'],
                                            actual_evidence=s['evidence_excerpt'], fine_tag_difference=s['template_key']) for s in members],
                       variant_explanation='各成员的场景、道具和次要事件保留在各季原文；归入候选簇依据共同叙事规则，细标签差异须逐项人工校审。',
                       color=f'hsl({(int(cluster["cluster_id"][1:]) * 137.508) % 360:.2f}, 56%, 47%)')
    return works, series, cluster_specs


def load_comments(data):
    raw_opinions = defaultdict(list)
    for rid, scope, relation, objects, attitude, target in lines(ANN / 'comment_opinions.tsv'):
        for obj in objects:
            raw_opinions[rid].append(dict(comparison_scope=SCOPES[scope], similarity_relation='指出相似' if relation == 'S' else '强调不同',
                                          object=OBJECTS[obj], attitude=ATTITUDES[attitude], comparison_target=target))
    overrides = read_json(ANN / 'creator_overrides.json')
    trial_ids = set(read_json(ANN / 'trial_comment_ids.json'))
    read_ids = set(read_json(ANN / 'semantic_read_ids.json')) | trial_ids | set(raw_opinions)
    comments, opinions = [], []
    for c in data['comments']:
        rid = c['local_id']
        role = c['possible_creator_or_promo'] == 'True' or rid in overrides
        text = c['text'].strip()
        selected = c['selected_for_row'] == 'True'
        interpretable = bool(re.search(r'[\u4e00-\u9fffA-Za-z0-9]', text))
        eligibility = '未选定版本' if not selected else '作者角色待判断' if role else '空内容或无法解释' if not interpretable else '有效观众候选'
        # 合并同一评论、对象、范围，避免一句多次表达增加计数。
        merged = defaultdict(list)
        for row in raw_opinions[rid]:
            merged[(row['comparison_scope'], row['object'])].append(row)
        for (scope, obj), rs in merged.items():
            attitudes = {x['attitude'] for x in rs} - {'未表态'}
            att = '褒贬混合' if '褒贬混合' in attitudes or ('反感重复' in attitudes and (attitudes & {'接受或喜爱重复', '肯定差异'})) else next(iter(sorted(attitudes)), '未表态')
            rel = '指出相似' if any(x['similarity_relation'] == '指出相似' for x in rs) else '强调不同'
            opinions.append(dict(comment_key=c['comment_key'], local_id=rid, work_id=c['work_id'], series_id=c['series_id'],
                                 comparison_scope=scope, similarity_relation=rel, object=obj, attitude=att,
                                 comparison_target='；'.join(dict.fromkeys(x['comparison_target'] for x in rs)),
                                 evidence_quote=c['text'], source_url=c['source_url'], source_file=c['source_file'],
                                 review_status='待人工判断' if scope == '待人工判断' else 'AI初标'))
        explicit = any(x['comparison_scope'] == '不同系列' and x['similarity_relation'] == '指出相似' for x in raw_opinions[rid])
        retained_source={k:v for k,v in c.items() if k!='identity_status'}
        comments.append(dict(retained_source, eligibility=eligibility, eligibility_reason=overrides.get(rid, c['role_flag_reason']) if role else
                             '未使用选定材料版本' if not selected else '只含空白或不可解释符号' if not interpretable else '所选材料中的可解释观众留言候选',
                             semantic_stage='试标全文语义初标' if rid in trial_ids else '候选语句语义初标，全文待校审' if rid in read_ids else '全量规则预筛未命中，尚待语义复核',
                             explicit_cross_series_similarity=explicit, comparison_candidate=bool(raw_opinions[rid]),
                             review_status='待人工判断' if role or any(x['comparison_scope'] == '待人工判断' for x in raw_opinions[rid]) else 'AI初标' if rid in read_ids else '待人工抽查',
                             annotation_version=VERSION))
    return comments, opinions


def ranking_assignments(data, series):
    smap = {s['series_id']: s for s in series}
    rows = []
    for r in data['rankings']:
        s = smap[r['series_id']]
        n = int(r['rank'])
        rows.append(dict(ranking_id=r['ranking_id'], month=r['month'], rank=n,
                         rank_group='head' if n <= 20 else 'tail' if n >= 81 else 'middle',
                         work_id=r['work_id'], series_id=r['series_id'], title=r['current_title'] or r['title_raw'], season_code=r['season_code'],
                         **{key: s[key] for key in ['template_key', 'cluster_id', 'cluster_name', 'core_conflict', 'turning_mechanism', 'response_path',
                                                   'assignment_reason', 'evidence_excerpt', 'review_status']},
                         work_description=r['description'], description_source_url=r['description_source_url']))
    return rows


def group_counts(rankings):
    output = []
    for month in sorted({r['month'] for r in rankings}):
        for group in ['head', 'middle', 'tail']:
            rows = [r for r in rankings if r['month'] == month and r['rank_group'] == group]
            codable = [r for r in rows if r['cluster_id']]
            for cid in sorted({r['cluster_id'] for r in codable}):
                members = [r for r in codable if r['cluster_id'] == cid]
                output.append(dict(month=month, rank_group=group, cluster_id=cid, cluster_name=members[0]['cluster_name'],
                                   ranking_count=len(members), work_count=len({x['work_id'] for x in members}),
                                   series_count=len({x['series_id'] for x in members}), codable_ranking_count=len(codable),
                                   original_ranking_count=len(rows), unassigned_count=len(rows)-len(codable),
                                   group_share=rate(len(members), len(codable)), member_ranking_ids=[x['ranking_id'] for x in members],
                                   member_work_ids=sorted({x['work_id'] for x in members}), member_series_ids=sorted({x['series_id'] for x in members})))
    return output


def comment_statistics(comments, opinions):
    valid = [c for c in comments if c['eligibility'] in ['有效观众候选', '有效观众']]
    valid_keys = {c['comment_key'] for c in valid}
    similar_keys = {o['comment_key'] for o in opinions if o['comment_key'] in valid_keys and o['comparison_scope']=='不同系列' and o['similarity_relation']=='指出相似'}
    works, series = defaultdict(list), defaultdict(list)
    for c in valid:
        works[c['work_id']].append(c)
        series[c['series_id']].append(c)
    covered_works = sorted(w for w, cs in works.items() if any(c['comment_key'] in similar_keys for c in cs))
    covered_series = sorted(s for s, cs in series.items() if any(c['comment_key'] in similar_keys for c in cs))
    series_rows = [dict(series_id=s, valid_comment_count=len(cs), similar_comment_count=sum(c['comment_key'] in similar_keys for c in cs),
                        mention_rate=rate(sum(c['comment_key'] in similar_keys for c in cs),len(cs))) for s, cs in sorted(series.items())]
    metric3 = [dict(metric='评论提及率', numerator=len(similar_keys), denominator=len(valid_keys), ratio=rate(len(similar_keys),len(valid_keys)),
                    counting_basis='comment_key去重', member_ids=sorted(similar_keys)),
               dict(metric='作品覆盖率', numerator=len(covered_works), denominator=len(works), ratio=rate(len(covered_works),len(works)),
                    counting_basis='保留季号的work_id', member_ids=covered_works),
               dict(metric='系列等权提及率', numerator=sum(r['mention_rate'] for r in series_rows), denominator=len(series_rows),
                    ratio=rate(sum(r['mention_rate'] for r in series_rows),len(series_rows)), counting_basis='各系列内部提及率的简单平均，分子为比例之和', member_ids=covered_series)]
    work_rows = [dict(work_id=w, series_id=cs[0]['series_id'], title=cs[0]['work_title_as_captured'],
                      valid_comment_count=len(cs), similar_comment_count=sum(c['comment_key'] in similar_keys for c in cs),
                      mention_rate=rate(sum(c['comment_key'] in similar_keys for c in cs),len(cs))) for w, cs in sorted(works.items())]
    eligible_ops = [o for o in opinions if o['comment_key'] in valid_keys]
    stats = []
    groups = sorted({(o['comparison_scope'],o['object']) for o in eligible_ops})
    for scope,obj in groups:
        rs = [o for o in eligible_ops if o['comparison_scope']==scope and o['object']==obj]
        total = len({o['comment_key'] for o in rs})
        for relation in ['指出相似','强调不同']:
            for att in ATTITUDES.values():
                ids = sorted({o['comment_key'] for o in rs if o['similarity_relation']==relation and o['attitude']==att})
                stats.append(dict(comparison_scope=scope, object=obj, similarity_relation=relation, attitude=att, comment_count=len(ids),
                                  object_comment_count=total, object_share=rate(len(ids),total), valid_comment_count=len(valid_keys),
                                  valid_comment_share=rate(len(ids),len(valid_keys)), comment_keys=ids))
    screening = [dict(eligibility=key, comment_count=n, total_comment_count=len(comments)) for key,n in sorted(Counter(c['eligibility'] for c in comments).items())]
    return metric3, work_rows, series_rows, stats, screening


def render_packet(path, title, sections):
    note='已落实用户确认及执行会话授权复核。原始意见与修改来源分别保留，定稿字段见各条记录。' if '定稿' in title else '全部为候选初标。人工修改请填写同目录校审表，保留审核人、日期与理由。'
    content = [f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{html.escape(title)}</title>',
               '<style>body{font:16px/1.8 system-ui;max-width:1100px;margin:36px auto;padding:0 24px;color:#253347;background:#f7f9fc}article{background:white;padding:24px;margin:20px 0;border:1px solid #dce3ee;border-radius:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 system-ui}h1{font-size:28px}h2{font-size:20px}a{color:#245a9b}</style>',
               f'<h1>{html.escape(title)}</h1><p>{note}</p>']
    for label, value in sections:
        content.append(f'<article><h2>{html.escape(label)}</h2><pre>{html.escape(json.dumps(value,ensure_ascii=False,indent=2))}</pre></article>')
    path.write_text('\n'.join(content)+'</html>', encoding='utf-8')


def prepare_review(data, series, catalog, comments, opinions):
    REVIEW.mkdir(exist_ok=True)
    trial_series = set(read_json(ANN/'trial_series_ids.json'))
    trial_comments = set(read_json(ANN/'trial_comment_ids.json'))
    opmap = defaultdict(list)
    for op in opinions:
        opmap[op['comment_key']].append(op)
    srows = [dict(s, annotation_version=VERSION, human_review_status='', reviewer='', reviewed_at='', final_cluster_id=s['cluster_id'],
                  final_core_conflict=s['core_conflict'], final_turning_mechanism=s['turning_mechanism'], final_response_path=s['response_path'],
                  final_core_narrative=s['core_narrative'], final_reason='', trial_sample=s['series_id'] in trial_series) for s in series]
    crows = [dict(c, annotation_version=VERSION, human_review_status='', reviewer='', reviewed_at='', final_cluster_name=c['cluster_name'], final_rule=c['inclusion_rule'],
                  final_boundary=c['nearest_cluster_difference'], final_reason='') for c in catalog]
    comment_rows = [dict(c, opinions=opmap[c['comment_key']], human_review_status='', reviewer='', reviewed_at='',
                         final_eligibility='有效观众' if c['eligibility']=='有效观众候选' else c['eligibility'], final_opinions=opmap[c['comment_key']],
                         final_reason='', missed_feedback_found='', trial_sample=c['local_id'] in trial_comments) for c in comments]
    # 不覆盖人工已经填写的校审表。
    for name,rows in [('系列校审表.csv',srows),('簇校审表.csv',crows),('评论校审表.csv',comment_rows)]:
        if not (REVIEW/name).exists():
            write_csv(REVIEW/name,rows)
    trial_srows = [s for s in srows if s['trial_sample']]
    trial_crows = [c for c in comment_rows if c['trial_sample']]
    write_csv(REVIEW/'试标_24系列.csv',trial_srows)
    write_csv(REVIEW/'试标_120评论.csv',trial_crows)
    render_packet(REVIEW/'试标校审阅读包.html','试标校审：24系列与120条评论',
                  [('系列 '+s['anonymous_series']+' '+s['series_title'],s) for s in trial_srows]+
                  [('评论 '+c['local_id']+' '+c['work_title_as_captured'],c) for c in trial_crows])
    render_packet(REVIEW/'全量结构与簇阅读包.html','全量系列结构与候选簇',
                  [('候选簇 '+c['cluster_id']+' '+c['cluster_name'],c) for c in catalog]+
                  [('系列 '+s['anonymous_series']+' '+s['series_title'],s) for s in srows])
    first_work = {w['work_id']:min(r['month'] for r in data['rankings'] if r['work_id']==w['work_id']) for w in data['works']}
    # 抽查框为尚未标注为相似或差异的选定版本、非作者存疑评论。
    negatives = [c for c in comments if not c['comparison_candidate'] and c['eligibility']=='有效观众候选']
    rng = random.Random(SEED)
    audit, layers = [], []
    for month in sorted(set(first_work.values())):
        pool=sorted([c for c in negatives if first_work[c['work_id']]==month],key=lambda c:c['comment_key'])
        take=math.ceil(len(pool)*0.2)
        sampled=rng.sample(pool,take)
        audit.extend(dict(c,work_first_month=month,audit_layer_count=len(pool),audit_layer_sample_count=take) for c in sampled)
        layers.append(dict(work_first_month=month,negative_population_count=len(pool),sample_count=take,seed=SEED))
    write_csv(REVIEW/'未命中20%分层抽查.csv',audit)
    write_csv(REVIEW/'未命中抽查分层数量.csv',layers)
    write_csv(REVIEW/'相似差异与作者角色全审清单.csv',[dict(c,opinions=opmap[c['comment_key']]) for c in comments if c['comparison_candidate'] or c['eligibility']=='作者角色待判断'])
    write_json(REVIEW/'抽查评论编号.json',[c['comment_key'] for c in audit])
    confirmation = REVIEW/'试标确认.json'
    if not confirmation.exists():
        write_json(confirmation,dict(confirmed=False,reviewer='',reviewed_at='',codebook_version=VERSION,notes='审核试标后填写；未确认期间全量结果均保持候选预览'))
    review_existing = read_csv(REVIEW/'评论校审表.csv')
    missed_months={first_work[c['work_id']] for c in review_existing if c.get('missed_feedback_found','').lower() in ['true','1','是']}
    write_csv(REVIEW/'发现漏标后整层扩查.csv',[dict(c,work_first_month=first_work[c['work_id']]) for c in negatives if first_work[c['work_id']] in missed_months])
    return dict(trial_series_count=len(trial_srows),trial_comment_count=len(trial_crows), negative_population_count=len(negatives),
                negative_audit_count=len(audit), required_full_review_count=sum(c['comparison_candidate'] or c['eligibility']=='作者角色待判断' for c in comments),
                triggered_recheck_months=sorted(missed_months))


def approved(row):
    return row.get('human_review_status')=='人工已审' and bool(row.get('reviewer','').strip()) and bool(row.get('reviewed_at','').strip()) and bool(row.get('final_reason','').strip())


def apply_reviews(data,series,catalog,comments,opinions):
    confirmed=read_json(REVIEW/'试标确认.json')
    trial_ok=confirmed['confirmed'] is True and bool(confirmed['reviewer']) and bool(confirmed['reviewed_at'])
    cr={x['cluster_id']:x for x in read_csv(REVIEW/'簇校审表.csv') if approved(x)} if trial_ok else {}
    sr={x['series_id']:x for x in read_csv(REVIEW/'系列校审表.csv') if approved(x)} if trial_ok else {}
    cm={x['comment_key']:x for x in read_csv(REVIEW/'评论校审表.csv') if approved(x)} if trial_ok else {}
    first_work={w['work_id']:min(r['month'] for r in data['rankings'] if r['work_id']==w['work_id']) for w in data['works']}
    negative_layers=defaultdict(set)
    for c in comments:
        if not c['comparison_candidate'] and c['eligibility']=='有效观众候选':
            negative_layers[first_work[c['work_id']]].add(c['comment_key'])
    audit_rows=read_csv(REVIEW/'未命中20%分层抽查.csv')
    audit_layers=defaultdict(set)
    for a in audit_rows:
        audit_layers[a['work_first_month']].add(a['comment_key'])
    accepted_layers=set()
    for month, keys in negative_layers.items():
        sampled=audit_layers[month]
        sampled_done=sampled <= cm.keys() and all(cm[k]['missed_feedback_found'].lower() in ['true','false','是','否','1','0'] for k in sampled)
        missed=any(cm[k]['missed_feedback_found'].lower() in ['true','是','1'] for k in sampled if k in cm)
        if sampled_done and (not missed or keys <= cm.keys()):
            accepted_layers.add(month)
    result_series=[]
    for s in series:
        row=dict(s)
        a=sr.get(s['series_id'])
        cid=a['final_cluster_id'] if a else ''
        if a and (not cid or cid in cr):
            row.update(cluster_id=cid,cluster_name=cr[cid]['final_cluster_name'] if cid else '', review_status='人工已审',
                       assignment_reason=a['final_reason'],core_narrative=a['final_core_narrative'],
                       core_conflict=a['final_core_conflict'],turning_mechanism=a['final_turning_mechanism'],response_path=a['final_response_path'])
            row['template_key']='|'.join(row[x] for x in ['core_conflict','turning_mechanism','response_path'])
        else:
            row.update(cluster_id='',cluster_name='',review_status='待人工校审')
        result_series.append(row)
    result_comments=[]
    result_opinions=[]
    for c in comments:
        row=dict(c)
        a=cm.get(c['comment_key'])
        if a:
            assert a['final_eligibility'] in ['有效观众','未选定版本','作者角色待判断','作者角色无法确定，排除','主创推广','空内容或无法解释']
            if c['selected_for_row']!='True':
                assert a['final_eligibility']!='有效观众', '未选定版本不能混入主分母'
            row.update(eligibility=a['final_eligibility'],review_status='人工已审',semantic_stage=a.get('final_semantic_stage') or c['semantic_stage'])
            for op in json.loads(a['final_opinions'] or '[]'):
                assert op['comparison_scope'] in SCOPES.values() and op['object'] in OBJECTS.values() and op['attitude'] in ATTITUDES.values()
                assert op['similarity_relation'] in ['指出相似','强调不同']
                assert op['evidence_quote'] and op['evidence_quote'] in c['text']
                result_opinions.append(dict(op,comment_key=c['comment_key'],work_id=c['work_id'],series_id=c['series_id'],review_status='人工已审'))
        else:
            if c['eligibility'] in ['未选定版本','空内容或无法解释']:
                row.update(review_status='规则排除，未人工已审')
            elif not c['comparison_candidate'] and c['eligibility']=='有效观众候选' and first_work[c['work_id']] in accepted_layers:
                row.update(eligibility='有效观众',review_status='所属未命中层已完成抽查，非逐条人工审核')
            else:
                row.update(eligibility='尚未人工审核',review_status='待人工校审')
        result_comments.append(row)
    result_catalog=[]
    for c in catalog:
        if c['cluster_id'] in cr:
            a=cr[c['cluster_id']]
            members=[s for s in result_series if s['cluster_id']==c['cluster_id']]
            result_catalog.append(dict(c,cluster_name=a['final_cluster_name'],inclusion_rule=a['final_rule'],common_chain=a['final_rule'],
                                       nearest_cluster_difference=a['final_boundary'],member_series_ids=[s['series_id'] for s in members],
                                       member_titles=[s['series_title'] for s in members],member_count=len(members),
                                       member_reasons=[dict(series_id=s['series_id'],reason=s['assignment_reason']) for s in members],review_status='人工已审'))
    return result_series,result_catalog,result_comments,result_opinions,dict(trial_confirmed=trial_ok,
        approved_series_count=sum(s['review_status']=='人工已审' for s in result_series),approved_cluster_count=len(cr),approved_comment_count=len(cm),
        accepted_negative_layers=sorted(accepted_layers),required_negative_layers=sorted(negative_layers),
        remaining_required_candidate_comment_count=sum((c['comparison_candidate'] or c['eligibility']=='作者角色待判断') and c['comment_key'] not in cm for c in comments),
        remaining_unread_viewer_comment_count=sum(c['semantic_stage'].startswith('全量规则') and c['eligibility']=='有效观众候选' and c['comment_key'] not in cm for c in comments))


def export_bundle(data,works,series,catalog,comments,opinions,mode):
    out=BASE/'results'/mode
    rankings=ranking_assignments(data,series)
    groups=group_counts(rankings)
    m1,m2,reuse_detail=novelty(rankings)
    smap={s['series_id']:s for s in series}
    for row in reuse_detail:
        row['earlier_series_evidence']=[dict(series_id=sid,title=smap[sid]['series_title'],evidence=smap[sid]['evidence_excerpt']) for sid in row['earlier_same_cluster_series_ids']]
    m3,work_comments,series_comments,m4,screening=comment_statistics(comments,opinions)
    tables={'作品结构初标.csv':works,'系列结构标注.csv':series,'结构簇目录.csv':catalog,'榜单簇归属.csv':rankings,'分组簇统计.csv':groups,
            '评论筛选与标签.csv':comments,'评论观点明细.csv':opinions,'指标1_三层换新.csv':m1,'指标2_新系列结构沿用.csv':m2,
            '指标2_新系列结构沿用明细.csv':reuse_detail,'指标3_相似反馈统计.csv':m3,'指标3_作品评论明细.csv':work_comments,
            '指标3_系列等权明细.csv':series_comments,'指标4_对象态度分布.csv':m4,'评论筛选数量.csv':screening}
    for name,rows in tables.items():
        write_csv(out/name,[dict(row,analysis_status='候选预览' if mode=='preview' else '确认与授权复核后的定稿统计',annotation_version=VERSION) for row in rows])
    write_json(out/'可视化数据.json',dict(status='候选预览' if mode=='preview' else '确认与授权复核后的定稿统计',version=VERSION,
        ranking_nodes=rankings,clusters=catalog,group_cluster_counts=groups,novelty=m1,reuse=m2,comment_metrics=m3,
        object_attitudes=m4))
    valid_ids={c['comment_key'] for c in comments if c['eligibility'] in ['有效观众','有效观众候选']}
    cdict={c['comment_key']:c for c in comments}
    cases=[]
    for scope in ['不同系列','同系列跨季','同剧内部','未说明','待人工判断']:
        for rel in ['指出相似','强调不同']:
            pool={o['comment_key']:o for o in opinions if o['comment_key'] in valid_ids and o['comparison_scope']==scope and o['similarity_relation']==rel}
            ordered=sorted(pool,key=lambda k: (-int(cdict[k]['likes_native'] or 0),k))[:8]
            cases.extend(dict(pool[k],text=cdict[k]['text'],likes_native=cdict[k]['likes_native'],title=cdict[k]['work_title_as_captured']) for k in ordered)
    write_csv(out/'典型评论案例.csv',cases)
    verify_outputs(data,series,catalog,comments,opinions,rankings,groups)
    return dict(structure_codable_series_count=sum(bool(s['cluster_id']) for s in series),unassigned_series_count=sum(not s['cluster_id'] for s in series),
                cluster_count=len(catalog),ranking_codable_count=sum(bool(r['cluster_id']) for r in rankings),
                comment_eligibility_counts=dict(Counter(c['eligibility'] for c in comments)),semantic_stage_counts=dict(Counter(c['semantic_stage'] for c in comments)),
                opinion_comment_count=len({o['comment_key'] for o in opinions}),opinion_count=len(opinions),metrics=dict(novelty=m1,reuse=m2,feedback=m3))


def verify_outputs(data,series,catalog,comments,opinions,rankings,groups):
    assert len(rankings)==len(data['rankings'])==len({r['ranking_id'] for r in rankings})
    original={r['ranking_id']:r for r in data['rankings']}
    assert all(original[r['ranking_id']]['month']==r['month'] and int(original[r['ranking_id']]['rank'])==r['rank'] for r in rankings)
    for sid in {r['series_id'] for r in rankings}:
        assert len({r['cluster_id'] for r in rankings if r['series_id']==sid})==1
    cluster_ids={c['cluster_id'] for c in catalog}
    assert all(not s['cluster_id'] or s['cluster_id'] in cluster_ids for s in series)
    for month,group in {(r['month'],r['rank_group']) for r in rankings}:
        rs=[r for r in rankings if (r['month'],r['rank_group'])==(month,group)]
        gs=[r for r in groups if (r['month'],r['rank_group'])==(month,group)]
        assert sum(x['ranking_count'] for x in gs)==sum(bool(x['cluster_id']) for x in rs)
        assert not gs or math.isclose(sum(x['group_share'] for x in gs),1)
        assert len(rs)==sum(bool(x['cluster_id']) for x in rs)+sum(not x['cluster_id'] for x in rs)
    assert all(1<=r['rank']<=20 if r['rank_group']=='head' else 81<=r['rank']<=100 if r['rank_group']=='tail' else 21<=r['rank']<=80 for r in rankings)
    cdict={c['comment_key']:c for c in comments}
    assert len({(o['comment_key'],o['object'],o['comparison_scope']) for o in opinions})==len(opinions)
    assert all(o['evidence_quote'] in cdict[o['comment_key']]['text'] for o in opinions)
    descriptions={w['description'] for w in data['works']}
    registered=set()
    if (ANN/'supplemental_sources.json').exists():
        registered|={s['summary'] for s in read_json(ANN/'supplemental_sources.json') if s['used']}
    if (ANN/'user_adjudications.json').exists():
        registered|=set(read_json(ANN/'user_adjudications.json')['decisions'].values())
    assert all(s['evidence_excerpt'] in descriptions|registered for s in series)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    data=read_json(ANN/'input_index.json')
    inventory=validate_inputs(data)
    works,series,catalog=load_structure(data)
    comments,opinions=load_comments(data)
    review=prepare_review(data,series,catalog,comments,opinions)
    preview=export_bundle(data,works,series,catalog,comments,opinions,'preview')
    ss,cc,cs,ops,coverage=apply_reviews(data,series,catalog,comments,opinions)
    ready=coverage['trial_confirmed'] and coverage['approved_series_count']==len(series) and coverage['approved_cluster_count']==len(catalog) \
        and coverage['remaining_required_candidate_comment_count']==0 and coverage['accepted_negative_layers']==coverage['required_negative_layers'] \
        and coverage['remaining_unread_viewer_comment_count']==0
    reviewed=export_bundle(data,[],ss,cc,cs,ops,'reviewed') if ready else None
    write_json(BASE/'results/reviewed/审核覆盖.json',dict(coverage,formal_release_ready=ready,
               status='已审核并重新计算' if ready else '尚未发布正式统计；正式比例留空，不用候选数替代'))
    manifest=dict(execution_date='2026-11-13',seed=SEED,annotation_version=VERSION,cluster_version=VERSION,
                  source_files=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size) for p in SOURCE_FILES],
                  annotation_files=[dict(path=str(p.relative_to(BASE)),sha256=sha(p)) for p in sorted(ANN.iterdir()) if p.is_file()],
                  counts=inventory,review_requirements=review,human_review_coverage=coverage,preview=preview,reviewed=reviewed)
    write_json(BASE/'logs/执行清单.json',manifest)
    write_json(BASE/'验收结果.json',dict(technical_checks_passed=True,source_row_counts=inventory,
               original_rankings_preserved=True,global_cluster_consistent=True,opinion_evidence_verified=True,
               structured_evidence_is_original_excerpt=True,review_requirements=review,human_review_coverage=coverage,
               formal_release_ready=ready,
               status='技术校验通过；人工校审尚未完成' if not coverage['trial_confirmed'] else '见人工覆盖数量'))
    print(json.dumps(dict(inventory=inventory,preview={k:v for k,v in preview.items() if k!='metrics'},review=review,coverage=coverage),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
