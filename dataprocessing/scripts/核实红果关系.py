"""红果出品与改编证据分层；不把书目核实、主创自述或系列证据外推为单季授权。"""
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

from 作品匹配 import normalize
from 持续补采 import ROOT, OUT as COLLECT

BASE = ROOT / 'data/红果400条交付'
SERIES = BASE / '系列合并'
OUT = BASE / '关系核实'
UNKNOWN = {'', '待认领', '待确认', '待核实', '未知', '不详'}


def save(name, rows):
    (OUT / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                     for k, v in r.items()} for r in rows)


def source(path, url, terms=()):
    path = ROOT / path
    text = BeautifulSoup(path.read_text(), 'html.parser').get_text(' ', strip=True).replace('\x00', '')
    assert all(term in text for term in terms), (str(path), terms)
    return {'source_url': url, 'source_file': str(path.relative_to(ROOT)),
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'captured_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            'validation_terms': list(terms)}


def main():
    OUT.mkdir(exist_ok=True)
    works = json.loads((SERIES / '季作品表.json').read_text())
    series = json.loads((SERIES / '系列汇总.json').read_text())
    ranks = json.loads((SERIES / '上榜记录_系列季映射.json').read_text())
    old_edges = json.loads((SERIES / '原著作者_系列季候选关系.json').read_text())
    wi = {w['work_id']: w for w in works}
    bysid = {w['platform_work_id']: w for w in works if w['platform_work_id']}
    si = {s['series_id']: s for s in series}
    books = {b['book_id']: b for b in json.loads((COLLECT / '原著官方书目核验.json').read_text())}
    newbooks = []
    for path in sorted((COLLECT / 'raw').glob('原著补核_*.html')):
        bid = path.stem.split('_')[-1]
        s = BeautifulSoup(path.read_text(), 'html.parser')
        h = s.find('h1')
        page = {}
        for tag in s.select('script'):
            m = re.search(r'window\.__INITIAL_STATE__\s*=\s*', tag.get_text())
            if m:
                page = json.JSONDecoder().raw_decode(tag.get_text()[m.end():])[0].get('page', {})
                break
        assert h and str(page.get('bookId')) == bid, path
        author = s.select_one('.author-name-text')
        intro = s.select_one('.page-abstract-content')
        b = {'book_id': bid, 'official_book_title': h.get_text(strip=True),
             'official_author': author.get_text(strip=True) if author else '',
             'official_author_id': str(page.get('authorId', '')),
             'official_description': intro.get_text('\n', strip=True) if intro else '',
             'identity_status': '公开元数据bookId与请求ID一致',
             **source(str(path.relative_to(ROOT)), 'https://fanqienovel.com/page/' + bid)}
        books[bid] = b
        newbooks.append(b)
    save('新增7本官方书目核验', newbooks)
    usedbooks = {r['book_id_candidate'] for r in old_edges}
    save('红果原著官方书目', [books[bid] for bid in sorted(usedbooks) if bid in books])

    evidence = []
    def add(eid, scope, sid, bid, quote, anchors, kind='A_原著官方改编自述', work_id='', src=None):
        assert sid in si and bid in books
        ww = [wi[x] for x in si[sid]['work_ids']]
        assert all(any(term in w['description'] for w in ww) for term in anchors), (eid, anchors)
        b = books[bid]
        proof = src or source(b['source_file'], b['source_url'], [quote])
        evidence.append({'evidence_id': eid, 'series_id': sid, 'work_id': work_id,
                         'scope': scope, 'book_id': bid, 'book_title': b['official_book_title'],
                         'author': b['official_author'], 'author_id': b['official_author_id'],
                         'relation_direction': '小说→短剧/漫剧', 'evidence_level': kind,
                         'claim_excerpt': quote, 'plot_identity_anchor_terms': anchors,
                         **proof, 'book_source_url': b['source_url'], 'book_source_file': b['source_file'],
                         'book_source_sha256': b['source_sha256'],
                         'limit': '声明与剧情锚点支持该系列；未点名单季不外推单季，未核授权合同或收益关系。上榜身份/OCR状态保留。'})
    m = wi['HG_7687169040510372888-S01']
    mat = next(x for x in json.loads((BASE / '简介封面材料明细.json').read_text())
               if x.get('platform_work_id') == m['platform_work_id'])
    quote = '改编自番茄小说《万人迷神颜顶流只想演炮灰》番茄土豆楠著。'
    assert quote in m['description']
    assert books['7652765843931024446']['official_author'] == '番茄土豆楠'
    add('ADAPT_WORK_001', '具体季', m['series_id'], '7652765843931024446', quote, ['宋时安'],
        kind='A_红果作品简介直接声明', work_id=m['work_id'],
        src=source(mat['source_file'], mat['source_url'], [quote]))
    cases = [
        ('HG_7676739369444576281', '7616151491132279832', '本书已改编动态漫，在红果上线', ['林昭', '马振邦']),
        ('HG_7681286468311976984', '7609931463961627710', '改编剧名《废物垫底皇子，反倒成为千古一帝》', ['李承泽']),
        ('HG_7677959169915243545', '7652183687085165593', '已改编短剧【大将军扛楼养活百万大军】', ['萧镇北']),
        ('HG_7675600333963267096', '7645220011115547710', '本书改编的红果漫剧上线了，《不朽仙秦！》', ['秦天']),
        ('HG_7691305180414872600', '7652970460308589592', '红果已改编同名漫剧', ['林羊']),
        ('HG_7690056402181573657', '7602139476386663449', '同名改编漫剧【人在古代，修为金丹】已上线', ['陈玄']),
    ]
    for i, (sid, bid, quote, anchors) in enumerate(cases, 1):
        add(f'ADAPT_SERIES_{i:03d}', '系列', sid, bid, quote, anchors)
    # 实地采访可支持系列改编报道，和平台/作者自己的声明分级。
    add('ADAPT_MEDIA_001', '系列', 'HG_7624475539960499262', '7544766518324644889',
        '免费申请到了《那妖魔是姜大人！》改编权', ['姜月初'], kind='B_实地采访报道',
        src=source('data/补采/raw/出品_光宇天眼实地报道.html',
                   'https://gz.cri.cn/n/20260824/6d04214e-637e-41e6-8d8c-033bc2d43084.html',
                   ['万妖图录传', '那妖魔是姜大人', '改编权']))

    # 扫全部已缓存的样本详情页；不提取头像、用户ID或联系方式。
    details = {}
    for path in (ROOT / 'data').rglob('*.html'):
        match = re.search(r'(\d{19})', path.name)
        if match and match[1] in bysid and ('detail_' in path.name or '详情_' in path.name):
            details.setdefault(match[1], path)
    claims = []
    for sid, path in details.items():
        s = BeautifulSoup(path.read_text(), 'html.parser')
        h = s.find('h1')
        if not h:
            continue
        w = bysid[sid]
        assert normalize(h.get_text(strip=True)) == normalize(w['title']), (path, w['title'])
        for position, card in enumerate(s.select("article[class*='mobile-review-card']"), 1):
            para = card.select_one("p[class*='mobile-review-content']")
            author = card.select_one("span[class*='user-name']")
            if not para or not author:
                continue
            text = para.get_text(' ', strip=True).replace('\x00', '')
            name = author.get_text(strip=True)
            known = any(name in re.split(r'[，,、/；;]', label) for label in w['producer_labels_as_listed'])
            self_claim = bool(re.search(r'我是.{0,15}出品方|制作人员|主创团队|我们.{0,30}(制作|改编|团队|创作)|本团队', text))
            if not (known and self_claim):
                continue
            date = card.find('time')
            claims.append({'work_id': w['work_id'], 'series_id': w['series_id'], 'title': w['title'],
                           'account_name_as_displayed': name, 'published_on': date.get_text(strip=True) if date else '',
                           'source_position': position, 'claim_text': text,
                           'evidence_level': 'B_平台账号自述，账号名称与榜单署名一致；账号认证主体待核',
                           **source(str(path.relative_to(ROOT)), 'https://hongguoduanju.com/detail?series_id=' + sid)})
    save('平台主创自述线索', claims)
    post_cases = [('HG_7619198149772446782-S07', '7445188900496083992', '香果味奶茶老师的《聚宝仙盆》', ['贺平生']),
                  ('HG_7692730550871657496-S02', '7232639406639680516', '改编自番茄小说《家主是修仙者》', ['程君意'])]
    for i, (wid, bid, quote, anchors) in enumerate(post_cases, 1):
        c = next((c for c in claims if c['work_id'] == wid and quote in c['claim_text']), None)
        if c:
            add(f'ADAPT_POST_{i:03d}', '具体季', wi[wid]['series_id'], bid, quote, anchors,
                kind='B_平台主创账号自述；账号认证及书名别名待核', work_id=wid,
                src={k: c[k] for k in ['source_url', 'source_file', 'source_sha256', 'captured_at', 'validation_terms']})
    save('改编证据登记', evidence)
    bseries = defaultdict(list)
    for e in evidence:
        bseries[e['series_id']].append(e)
    series_books = {}
    for edge in old_edges:
        key = (edge['series_id'], edge['book_id_candidate'])
        series_books.setdefault(key, {'series_id': key[0], 'book_id': key[1], 'ranking_ids': [],
                                      'third_party_source_urls': [], 'direct_evidence_ids': []})
        r = series_books[key]
        if edge['ranking_id'] not in r['ranking_ids']:
            r['ranking_ids'].append(edge['ranking_id'])
        if edge['third_party_evidence_url'] not in r['third_party_source_urls']:
            r['third_party_source_urls'].append(edge['third_party_evidence_url'])
    for e in evidence:
        key = (e['series_id'], e['book_id'])
        r = series_books.setdefault(key, {'series_id': key[0], 'book_id': key[1], 'ranking_ids': [],
                                         'third_party_source_urls': [], 'direct_evidence_ids': []})
        r['direct_evidence_ids'].append(e['evidence_id'])
        r['ranking_ids'] = list(dict.fromkeys(r['ranking_ids'] + si[e['series_id']]['ranking_ids']))
    for r in series_books.values():
        b = books.get(r['book_id'], {})
        r.update(book_title=b.get('official_book_title', ''), author=b.get('official_author', ''),
                 author_id=b.get('official_author_id', ''), book_source_url=b.get('source_url', ''),
                 book_source_file=b.get('source_file', ''), book_source_sha256=b.get('source_sha256', ''),
                 adaptation_status='有公开关系证据，适用范围逐条见证据登记' if r['direct_evidence_ids'] else '第三方候选；改编关系待独立确认')
    save('系列_原著作者关系', list(series_books.values()))
    all_book_ids = {bid for sid, bid in series_books}
    save('红果原著官方书目', [books[bid] for bid in sorted(all_book_ids) if bid in books])
    refreshed_edges = []
    for edge in old_edges:
        b = books.get(edge['book_id_candidate'], {})
        old_title = edge['third_party_original_title']
        refreshed_edges.append({**edge, 'official_book_title': b.get('official_book_title', ''),
                                'official_author': b.get('official_author', ''),
                                'official_author_id': b.get('official_author_id', ''),
                                'official_book_url': b.get('source_url', ''),
                                'official_book_file': b.get('source_file', ''),
                                'official_book_sha256': b.get('source_sha256', ''),
                                'book_identity_status': '官方bookId已核实' if b else '官方书页待核',
                                'title_difference_note': '第三方未提供书名，不当作更名差异' if not old_title else
                                                         '第三方书名与官方现名不同，别名关系仍需核实' if b and normalize(old_title) != normalize(b['official_book_title']) else ''})
    save('原著作者候选_补全书页', refreshed_edges)
    direction = []
    for bid, b in books.items():
        t = b['official_description']
        if re.search(r'短剧.{0,45}(授权改编小说|改编.{0,5}小说)', t):
            direction.append({'book_id': bid, 'book_title': b['official_book_title'],
                              'relation_direction': '短剧→小说', 'scope': '样本内候选' if bid in all_book_ids else '样本外书目',
                              'claim_excerpt': t.splitlines()[0], 'decision': '不可倒置计为短剧原著',
                              'source_url': b['source_url'], 'source_file': b['source_file'], 'source_sha256': b['source_sha256']})
        elif re.search('已改编|同名改编|本书改编', t):
            direction.append({'book_id': bid, 'book_title': b['official_book_title'],
                              'relation_direction': '小说→其他形态；具体剧名依证据核对',
                              'scope': '样本内候选' if bid in all_book_ids else '样本外书目',
                              'claim_excerpt': t.splitlines()[0], 'decision': '泛称已改编但不点名作品的，不自动关联某部短剧',
                              'source_url': b['source_url'], 'source_file': b['source_file'], 'source_sha256': b['source_sha256']})
    save('改编方向核查', direction)
    ranked = []
    for r in ranks:
        ee = bseries.get(r['series_id'], [])
        direct = [e for e in ee if e['work_id'] == r['work_id']]
        broader = [e for e in ee if e['scope'] == '系列']
        status = ('平台作品简介有本季直接改编声明' if any(e['evidence_level'].startswith('A_红果') for e in direct) else
                  '本季有主创账号改编自述，账号身份待核' if direct else
                  '系列有原著官方改编声明，未点名本季' if any(e['evidence_level'].startswith('A_') for e in broader) else
                  '系列有媒体改编报道，未确认本季' if broader else '尚无独立改编确认；不等于原创')
        ranked.append({'ranking_id': r['ranking_id'], 'series_id': r['series_id'], 'work_id': r['work_id'],
                       'title': r['title_raw'], 'review_status': r['review_status'], 'identity_status': r['identity_status'],
                       'adaptation_status': status, 'work_evidence_ids': [e['evidence_id'] for e in direct],
                       'series_evidence_ids': [e['evidence_id'] for e in broader],
                       'book_candidates': sorted({bid for sid, bid in series_books if sid == r['series_id']})})
    save('改编关系_400条覆盖', ranked)
    aliases = {'不鸣文化剧场': '不鸣文化', '不鸣文化官方号': '不鸣文化'}
    entities = {
        '不鸣文化': ('深圳不鸣文化科技有限公司', 'A_品牌官网列明运营主体；具体平台账号认证另核',
                      source('data/补采/raw/出品_不鸣官网新快照.html',
                             'https://szbuming.com/ai-short-drama', ['运营主体', '深圳不鸣文化科技有限公司'])),
        '惊人科技': ('深圳惊人科技有限公司', 'B_展商资料及政府名单支持，具体账号主体另核',
                      source('data/补采/raw/出品_惊人文博会.html',
                             'https://www.sznews.com/news/content/2026-05/15/content_32051419.htm', ['深圳惊人科技有限公司'])),
        '光宇出品': ('贵州梦绘星界动漫有限公司', 'B_媒体实地采访及品牌发声，具体账号主体另核',
                      source('data/补采/raw/出品_光宇天眼实地报道.html',
                             'https://gz.cri.cn/n/20260824/6d04214e-637e-41e6-8d8c-033bc2d43084.html', ['贵州梦绘星界动漫有限公司', '光宇出品'])),
        '梦绘星界': ('贵州梦绘星界动漫有限公司', 'B_媒体实地采访中的公司简称，具体账号主体另核',
                      source('data/补采/raw/出品_光宇天眼实地报道.html',
                             'https://gz.cri.cn/n/20260824/6d04214e-637e-41e6-8d8c-033bc2d43084.html', ['贵州梦绘星界动漫有限公司'])),
    }
    atom_edges = []
    for r in ranks:
        for token in re.split(r'[，,、/；;]', r['producer_raw']):
            token = token.strip()
            if token in UNKNOWN:
                continue
            brand = aliases.get(token, token)
            entity, level, proof = entities.get(brand, ('', '仅榜单品牌署名；企业主体待核', {}))
            atom_edges.append({'ranking_id': r['ranking_id'], 'series_id': r['series_id'], 'work_id': r['work_id'],
                               'producer_raw': r['producer_raw'], 'producer_token': token, 'brand_name': brand,
                               'brand_id': 'BRAND_' + hashlib.sha256(normalize(brand).encode()).hexdigest()[:16],
                               'brand_normalization_note': '只统一不鸣文化明确品牌词及剧场/官方号后缀，账号主体仍待核' if token in aliases else '保留原署名',
                               'entity_name_supported': entity, 'entity_evidence_level': level, **proof,
                               'ranking_source_url': r['source_url'], 'ranking_source_image': r['source_image'],
                               'ranking_review_status': r['review_status'], 'credit_counting': '联合署名拆边，各方均保留；占比不可直接相加'})
    save('出品品牌_主体_系列季关系', atom_edges)
    brands = defaultdict(list)
    for edge in atom_edges:
        brands[edge['brand_id']].append(edge)
    brand_summary = []
    for bid, ee in brands.items():
        brand_summary.append({'brand_id': bid, 'brand_name': ee[0]['brand_name'],
                              'original_tokens': sorted({e['producer_token'] for e in ee}),
                              'ranking_count': len({e['ranking_id'] for e in ee}),
                              'work_count': len({e['work_id'] for e in ee}),
                              'series_unit_count': len({e['series_id'] for e in ee}),
                              'series_ids': sorted({e['series_id'] for e in ee}),
                              'entity_names_supported': sorted({e['entity_name_supported'] for e in ee if e['entity_name_supported']}),
                              'counting_note': '仅品牌署名候选统计，不等于企业家数；联合署名各方保留，不可直接将各方占比相加'})
    save('出品品牌汇总', sorted(brand_summary, key=lambda x: (-x['series_unit_count'], -x['ranking_count'])))
    # 官网对具体项目的工作分工单列，不能把所有参与环节都叫出品。
    project_roles = []
    for project in json.loads((COLLECT / '制作方官网作品资料.json').read_text()):
        for w in works:
            if normalize(w['title']) != normalize(project['title']):
                continue
            proof = source(project['source_file'], project['source_url'], [project['title'], *project['roles_as_listed']])
            project_roles.append({'series_id': w['series_id'], 'work_id': w['work_id'], 'title': w['title'],
                                  'entity_name': '深圳不鸣文化科技有限公司',
                                  'roles_as_listed': project['roles_as_listed'], 'ranking_ids': w['ranking_ids'],
                                  'evidence_level': 'A_公司官网具体作品项目卡片', **proof,
                                  'limit': '只记录卡片列出的内容开发/AI制作/发行运营角色，不自动等同出品或版权所有'})
    save('制作发行_具体作品官网证据', project_roles)
    unknown_claims = []
    unknown_work_ids = {r['work_id'] for r in ranks if r['producer_raw'] in UNKNOWN}
    for sid, path in details.items():
        w = bysid[sid]
        if w['work_id'] not in unknown_work_ids:
            continue
        s = BeautifulSoup(path.read_text(), 'html.parser')
        for position, card in enumerate(s.select("article[class*='mobile-review-card']"), 1):
            para = card.select_one("p[class*='mobile-review-content']")
            author = card.select_one("span[class*='user-name']")
            if not para or not author:
                continue
            text = para.get_text(' ', strip=True).replace('\x00', '')
            if not re.search(r'我是.{0,60}(主创|出品方)|主创团队|制作人员', text):
                continue
            unknown_claims.append({'series_id': w['series_id'], 'work_id': w['work_id'], 'title': w['title'],
                                   'account_candidate': author.get_text(strip=True), 'source_position': position,
                                   'claim_excerpt': text[:250],
                                   **source(str(path.relative_to(ROOT)), 'https://hongguoduanju.com/detail?series_id=' + sid),
                                   'decision': '主创自称线索，账号主体与实际角色待核；不覆盖原榜待认领/待确认值'})
    save('缺署名作品_主创账号候选', unknown_claims)
    save('主体关系与同名排除', [
        {'relation': '股权关系资料，非同一公司别名', 'subject': '深圳不鸣文化科技有限公司', 'object': '深圳惊人科技有限公司',
         'as_reported': '2026-05-15展商资料标注不鸣文化90%控股；仅按该期资料保存，不认定当前股权', **entities['惊人科技'][2]},
        {'relation': '媒体报道的候选主体，未强选一家', 'subject': '半亩文剧社/孤灵剧场',
         'object': ['宜春孤灵文化有限公司', '宜春半亩文网络科技有限公司'],
         **source('data/补采/raw/出品_半亩文报道.html',
                  'https://www.thepaper.cn/newsDetail_forward_34001023', ['半亩文剧社', '宜春孤灵文化有限公司', '宜春半亩文网络科技有限公司'])},
        {'relation': '同名公司不能直接合并', 'subject': '榜单陈柯文化', 'object': '杭州陈柯文化创意有限公司',
         'as_reported': '搜到同名企业官网，但未见聚宝仙盆项目或创作者身份交叉证据，未回填为该剧出品主体',
         **source('data/补采/raw/出品_陈柯同名公司待排除.html',
                  'https://www.chenkecc.com/post/64.html', ['杭州陈柯文化创意有限公司'])}])
    queue = []
    for s in series:
        ee = bseries.get(s['series_id'], [])
        rawr = [r for r in ranks if r['series_id'] == s['series_id']]
        queue.append({'series_id': s['series_id'], 'title': s['series_title'], 'work_count': s['work_count'],
                      'ranking_count': s['ranking_count'], 'platform_group_id': s['platform_group_id'],
                      'producer_labels': s['producer_labels_as_listed'],
                      'producer_gap': '无具名出品署名' if all(r['producer_raw'] in UNKNOWN for r in rawr) else '继续核实品牌/账号与企业主体',
                      'book_ids': sorted({bid for sid, bid in series_books if sid == s['series_id']}),
                      'adaptation_evidence_ids': [e['evidence_id'] for e in ee],
                      'next_step': '逐季核署名或平台改编声明' if ee else '沿出品方/原著官方页找改编声明；缺线索不判原创'})
    save('下一轮系列核查队列', sorted(queue, key=lambda x: (-x['ranking_count'], x['series_id'])))
    stats = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scope': '仅红果7—10月',
             'ranking_rows': len(ranks), 'series_units': len(series), 'new_official_book_pages': len(newbooks),
             'original_candidate_books_now_with_official_pages': sum(bid in books for bid in usedbooks),
             'original_candidate_books': len(usedbooks),
             'all_candidate_books_after_new_evidence': len(all_book_ids),
             'all_candidate_books_with_official_pages': sum(bid in books for bid in all_book_ids),
             'official_authors_in_current_relations': len({books[bid]['official_author_id'] for bid in all_book_ids if bid in books and books[bid]['official_author_id']}),
             'book_relation_series_units': len({sid for sid, bid in series_books}),
             'series_book_candidate_edges': len(series_books),
             'direct_work_adaptation_statements': sum(e['evidence_level'].startswith('A_红果') for e in evidence),
             'official_book_series_adaptation_statements': sum(e['scope'] == '系列' and e['evidence_level'].startswith('A_') for e in evidence),
             'media_series_adaptation_reports': sum(e['evidence_level'].startswith('B_实地') for e in evidence),
             'work_adaptation_self_claims': sum(e['evidence_level'].startswith('B_平台主创') for e in evidence),
             'detail_pages_scanned': len(details), 'producer_self_claim_cards': len(claims),
             'ranking_rows_named_producer': sum(r['producer_raw'] not in UNKNOWN for r in ranks),
             'producer_placeholder_counts': dict(Counter(r['producer_raw'] for r in ranks if r['producer_raw'] in UNKNOWN)),
             'producer_credit_edges': len(atom_edges),
             'work_project_role_statements': len(project_roles),
             'missing_producer_work_self_claim_candidates': len(unknown_claims),
             'brand_names_after_limited_normalization': len({r['brand_id'] for r in atom_edges}),
             'supported_entity_names': sorted({r['entity_name_supported'] for r in atom_edges if r['entity_name_supported']}),
             'ranking_adaptation_status_counts': dict(Counter(r['adaptation_status'] for r in ranked)),
             'limits': '平台作品改编声明、原著系列声明、媒体报道、主创账号自述与第三方线索分层。书目全覆盖不等于改编全确认；公司关系不合并为别名；月榜OCR和历史版本身份仍按原状态保留。'}
    (OUT / '核实统计.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    assert len(ranked) == len({r['ranking_id'] for r in ranked}) == 400
    for e in evidence:
        assert e['series_id'] in si and (not e['work_id'] or e['work_id'] in wi)
        assert hashlib.sha256((ROOT / e['source_file']).read_bytes()).hexdigest() == e['source_sha256']
        assert hashlib.sha256((ROOT / e['book_source_file']).read_bytes()).hexdigest() == e['book_source_sha256']
    (OUT / '说明.md').write_text('\n'.join([
        '# 红果出品方与原著关系核实', '',
        '本目录为关系证据的最新入口；系列合并目录保留原始候选基础，不能以旧候选统计代替本轮核实结果。', '',
        f'新补{len(newbooks)}本官方书页，使原有77本红果候选书均有官方资料；另外将2本已有官方资料的书关联到新发现的系列关系，共{len(all_book_ids)}本候选书、{stats["book_relation_series_units"]}个系列单元、{stats["official_authors_in_current_relations"]}位作者。书目全覆盖不代表改编全部确认。', '',
        f'本轮有{stats["direct_work_adaptation_statements"]}条平台具体季直接声明、{stats["official_book_series_adaptation_statements"]}条官方原著系列声明、{stats["media_series_adaptation_reports"]}条实地采访改编报道、{stats["work_adaptation_self_claims"]}条具体季主创账号自述。系列证据不外推为每季授权。', '',
        '出品方校正：367条具名，20条待认领、12条待确认、1条空。此前379条把待确认误计为具名，已修正。联合署名拆分后保留各方，不能把多方占比相加。', '',
        '品牌与公司：官网列明运营主体和平台账号认证是不同证据；不鸣与惊人分别保存，公司股权资料仅按来源日期记录；陈柯同名企业不据此认定为聚宝仙盆团队。', '',
        '书目与改编：小说→短剧、短剧→小说和未明确命名剧目的改编宣传需区分。书名不同保留现名与第三方旧名，第三方空书名不当作更名证据。', '',
        '文件：改编证据登记、改编关系_400条覆盖、系列_原著作者关系、出品品牌_主体_系列季关系、出品品牌汇总、制作发行_具体作品官网证据、平台主创自述线索、缺署名作品_主创账号候选、主体关系与同名排除、下一轮系列核查队列。', '',
        '所有series_id/work_id沿用系列号—季号规则，证据source_file相对于dataprocessing目录。原平台ID、原署名、原始榜单字段及OCR状态未覆盖。',
        ] ) + '\n')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
