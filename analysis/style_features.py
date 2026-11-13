"""Evidence-bearing title, identity-screening and OCR features for the supplement."""
import argparse
import re
import sys
import time
from collections import Counter
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from common import ROOT, RESULTS, STYLE_OUTPUT, OCR_RUNTIME, load, save, sha256

STYLE_RESULTS = RESULTS / 'style'
OUTPUT = STYLE_OUTPUT
PROTOCOL = load(ROOT / 'style_protocol.json')

TEMPLATES = {
    '谁说…不能…': r'谁说.{1,18}不能.{1,18}',
    '都…了，谁还…': r'都.{1,12}了[，,：:]?谁还.{1,18}',
    '都…了，你…': r'都.{1,12}了[，,：:]你.{1,18}',
    '让你…，没让你…': r'让你.{1,15}[，,]没让你.{1,20}',
    '让你…，你…': r'让你.{1,15}[，,]你.{1,20}',
    '…只想…却被/非要…': r'.{0,10}只想.{1,15}[，,]?(?:却被|却|非要).{1,20}',
    '…，我靠…': r'.{1,20}[，,：:]我靠.{1,20}',
    '…：我靠…': r'.{1,15}[：:]我靠.{1,20}',
    '穿成…，…': r'穿成.{1,15}[，,：:].{1,25}',
    '重生…，…': r'重生.{1,15}[，,：:].{1,25}',
    '…归来：/，…': r'.{1,12}归来[，,：:].{1,25}',
    '…下山，…': r'.{1,12}下山[，,：:].{1,25}',
    '…后，我/她/他…': r'.{1,18}后[，,：:]?[我她他].{1,25}',
    '我在…': r'^我在.{3,25}',
    '…：我的…': r'.{1,15}[：:]我的.{2,25}',
    '…，全班/全家/师兄/大佬…': r'.{1,20}[，,](?:全班|全家|师兄们|大佬).{1,20}',
    '…，我让…': r'.{1,20}[，,]我让.{2,20}',
    '…：从…开始…': r'.{1,20}[：:]从.{1,15}开始.{1,15}',
    '开局＋优势设定': r'(?:^|[：:，,])开局.{2,25}',
    '…，靠…赢/发家/养…': r'.{1,18}[，,]靠.{1,18}(?:赢|发家|养).{0,15}',
    '…，反倒/却/竟…': r'.{1,20}[，,](?:反倒|却|竟).{1,20}',
    '…，你…我…': r'.{1,20}[，,]你.{1,12}我.{1,12}',
    '…明明…为何…': r'.{0,12}明明.{1,12}为何.{1,12}',
    '…，…慌了': r'.{1,20}[，,].{1,15}慌了',
}
CONTENT_CUES = {
    '修仙与境界': r'修仙|修炼|灵根|仙人|剑宗|师尊|大乘|元婴|金丹|炼气|妖祖|魔域|剑神|仙秦|仙盆',
    '重生与穿越': r'重生|穿越|穿书|穿成|重回|回现代',
    '显赫与隐藏身份': r'总裁|大佬|千金|首富|皇子|太子|权臣|反派|纨绔|驸马|贵族|战神|继承者|世家',
    '家庭与抚养': r'萌娃|崽|奶团|奶爸|女儿|养全家|养妻女|后妈|后娘|老爸|哥哥|全家|婆婆|帅府|师兄|亲妈',
    '特殊系统与能力': r'系统|外挂|透视|天师|预言家|神豪|金眼|神明|诡异|神颜|力能|神医',
    '逆袭与强势结果': r'逆袭|整顿|横扫|镇压|称帝|封王|无敌|毁天灭地|封神|暴富|变强|赢麻|发家|旺爆|开挂',
    '婚恋与亲密关系': r'老公|夫人|新娘|甜宠|偏爱|相恋|白月光|初恋|闪婚|网恋|倒追|情书|男友|婚|和离',
    '灾难与求生': r'末世|末日|天灾|求生|灾年|囤货|囤满',
}

def normalized(text):
    return re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', text).lower()

def seasonless(row):
    text = row['title_raw']
    if re.fullmatch(r'S\d+', row['season_code']):
        # The season was confirmed in the source. Other numerical content is preserved.
        text = re.sub(r'第[零〇一二两三四五六七八九十百\d]+季', '', text)
    return text.strip(' ，,：:')

def bigrams(text):
    return set(re.findall(r'(?=([\u4e00-\u9fff]{2}))', text))

def title_features(row):
    text = seasonless(row)
    template = [{'label': label, 'evidence': m.group(), 'start': m.start(), 'end': m.end()}
                for label, exp in TEMPLATES.items() if (m := re.search(exp, text))]
    cues = [{'label': label, 'evidence': m.group(), 'start': m.start(), 'end': m.end()}
            for label, exp in CONTENT_CUES.items() if (m := re.search(exp, text))]
    rhetoric = []
    for label, exp in {'第一人称': r'我|咱|老子', '疑问或反问': r'[？?]|谁说|谁还|为何|何时|怎么|究竟',
                       '否定或反预期词': r'不是|不能|没让|却|反倒|明明|错把|竟|不装|没我份',
                       '强势或极值词': r'全是|全家|全班|最|第一|无敌|横扫|镇压|毁天灭地|亿倍|通天'}.items():
        m = re.search(exp, text)
        if m:
            rhetoric.append({'label': label, 'evidence': m.group(), 'start': m.start(), 'end': m.end()})
    return {'series_id': row['series_id'], 'title_raw': row['title_raw'], 'title_style': text,
            'season_code': row['season_code'], 'content_type': row['content_type'], 'source_url': row['source_url'],
            'char_count': len(normalized(text)), 'comma': bool(re.search('[，,]', text)),
            'colon': bool(re.search('[：:]', text)), 'question': bool(re.search('[？?]', text)),
            'clauses': [x for x in re.split('[，,：:！？!?。]', text) if x],
            'templates': template, 'content_cues': cues, 'rhetoric': rhetoric}

def prepare():
    reps = load(RESULTS / 'representatives.json')
    rows = [r for r in reps if r['modality'] == 'title']
    desc = {r['series_id']: r['description'] for r in reps if r['modality'] == 'description'}
    bg = {sid: bigrams(text) for sid, text in desc.items()}
    df = Counter(t for terms in bg.values() for t in terms)
    identity = {}
    for a, b in PROTOCOL['identity']['known_pending_pairs']:
        identity[tuple(sorted([a, b]))] = {'series_a': min(a,b), 'series_b': max(a,b),
            'reason': '前次报告发现近名与相同人物/设定，改名、同故事或不同版本关系未解决',
            'evidence_kind': '阅读现存代表简介发现关联疑点', 'status': '待核；主配对排除，不合并系列'}
    for x in load(RESULTS / 'excluded_pairs.json'):
        identity[tuple(sorted([x['series_a'], x['series_b']]))] = {**x, 'status': '原排除表待核关系'}
    for a, b in combinations(rows, 2):
        similarity = SequenceMatcher(None, a['title_core'], b['title_core'], autojunk=False).ratio()
        if similarity < PROTOCOL['identity']['min_title_sequence_ratio']:
            continue
        shared = sorted(x for x in bg[a['series_id']] & bg[b['series_id']] if df[x] <= PROTOCOL['identity']['rare_bigram_max_document_frequency'])
        if len(shared) >= PROTOCOL['identity']['min_shared_rare_bigrams']:
            key = tuple(sorted([a['series_id'], b['series_id']]))
            record = identity.setdefault(key, {'series_a': key[0], 'series_b': key[1], 'reason': '近名且简介共享低频文字片段，自动关联疑点',
                         'evidence_kind': '自动筛查，非身份认定', 'status': '待核；主配对排除，不合并系列'})
            record.update(title_sequence_ratio=similarity, shared_rare_bigrams=shared)
    features = [title_features(r) for r in rows]
    for row in features:
        row['genre'] = next(x['genre_primary'] for x in load(RESULTS / 'story_coding.json') if x['series_id'] == row['series_id'])
    save(STYLE_RESULTS / 'identity_exclusions.json', sorted(identity.values(), key=lambda r:(r['series_a'],r['series_b'])))
    save(STYLE_RESULTS / 'title_features.json', features)
    save(STYLE_RESULTS / 'title_codebook.json', {'templates': TEMPLATES, 'content_cues': CONTENT_CUES})
    save(STYLE_RESULTS / 'protocol_lock.json', {'protocol': PROTOCOL, 'protocol_sha256': sha256(ROOT / 'style_protocol.json'),
          'representatives_sha256': sha256(RESULTS / 'representatives.json'), 'design_status': PROTOCOL['design_status']})
    print('title features',len(features),'identity exclusions',len(identity),flush=True)

def title_mask(record, side=64):
    import cv2
    mask = np.zeros((side, side), dtype=np.uint8)
    for box in record.get('title_boxes', []):
        poly = np.rint(np.array(box['polygon_normalized']) * (side-1)).astype(np.int32)
        cv2.fillPoly(mask, [poly], 1)
    return mask

def ocr():
    if OCR_RUNTIME.exists():
        sys.path.insert(0, str(OCR_RUNTIME))
    import cv2
    import rapidocr_onnxruntime
    import onnxruntime
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR(intra_op_num_threads=4, inter_op_num_threads=2)
    rows = [r for r in load(RESULTS / 'representatives.json') if r['modality'] == 'cover']
    (OUTPUT / 'assets/ocr').mkdir(parents=True, exist_ok=True)
    cached = {x['series_id']:x for x in load(STYLE_RESULTS / 'cover_ocr.json')} if (STYLE_RESULTS / 'cover_ocr.json').exists() else {}
    fingerprint = {
        'input_sha256': sha256(RESULTS / 'representatives.json'),
        'protocol_sha256': sha256(ROOT / 'style_protocol.json'),
        'feature_code_sha256': sha256(Path(__file__)),
    }
    meta_path = STYLE_RESULTS / 'ocr_metadata.json'
    previous = load(meta_path) if meta_path.exists() else {}
    if any(previous.get(k) != v for k, v in fingerprint.items()):
        cached = {}
    start = time.time()
    output=[]
    def render_overlay(record, source_path):
        with Image.open(source_path) as im:
            image=im.convert('RGB')
        draw=ImageDraw.Draw(image)
        for b in record['boxes']:
            points=[tuple(p) for p in b['polygon']]
            draw.line(points+[points[0]],fill='#999999',width=2)
        for b in record['title_boxes']:
            points=[tuple(p) for p in b['polygon']]
            draw.line(points+[points[0]],fill='#00cc88' if record['valid_title_layout'] else '#ff9922',width=4)
        image.thumbnail((600,900)); image.save(OUTPUT/record['overlay'],quality=88)
    for i,row in enumerate(rows):
        sid = row['series_id']
        if sid in cached and cached[sid]['image_sha256'] == sha256(row['cover_path']):
            if not (OUTPUT/cached[sid]['overlay']).exists():
                render_overlay(cached[sid],row['cover_path'])
            output.append(cached[sid]); continue
        with Image.open(row['cover_path']) as im:
            im = im.convert('RGB'); image = np.array(im); w,h = im.size
        raw,elapsed = engine(image)
        raw = raw or []
        boxes=[]; title_boxes=[]; title_chars=set(normalized(seasonless(row)))
        for polygon,text,score in raw:
            text_norm = normalized(text)
            common = set(text_norm) & title_chars
            box={'text':text,'confidence':float(score),'polygon':[[float(a),float(b)] for a,b in polygon],
                 'polygon_normalized':[[float(a)/w,float(b)/h] for a,b in polygon],
                 'title_char_overlap':len(common)/len(set(text_norm)) if text_norm else 0}
            boxes.append(box)
            if score>=PROTOCOL['ocr']['confidence_min'] and len(text_norm)>=2 and len(common)>=2 and box['title_char_overlap']>=.60:
                title_boxes.append(box)
        covered = set(''.join(normalized(b['text']) for b in title_boxes)) & title_chars
        coverage=len(covered)/len(title_chars) if title_chars else 0
        valid= bool(title_boxes) and coverage>=.25 and len(covered)>=min(4,len(title_chars))
        record={'series_id':sid,'title':row['series_title'],'image_sha256':sha256(row['cover_path']),
                'width':w,'height':h,'boxes':boxes,'title_boxes':title_boxes,'title_character_coverage':coverage,
                'valid_title_layout':valid,'status':'可用OCR标题区域' if valid else '标题匹配不足，排版指标记缺失',
                'overlay':'assets/ocr/'+sid+'.jpg'}
        if valid:
            mask=title_mask(record,256)
            ys,xs=np.where(mask>0); area=float(mask.mean());cx=float(xs.mean()/255);cy=float(ys.mean()/255)
            dirs=[]
            for b in title_boxes:
                ar=np.array(b['polygon_normalized']);bw=float(ar[:,0].max()-ar[:,0].min());bh=float(ar[:,1].max()-ar[:,1].min())
                dirs.append('横向' if bw/bh>=1.5 else '竖向' if bw/bh<=.67 else '近方形')
            direction=Counter(dirs).most_common(1)[0][0] if len(set(dirs))==1 else '混合'
            position='上部' if cy<1/3 else '中部' if cy<2/3 else '下部'
            area_band='小文字区' if area<.10 else '中文字区' if area<.25 else '大文字区'
            boxes_band=str(len(title_boxes)) if len(title_boxes)<4 else '4+'
            hsv=cv2.cvtColor(cv2.resize(image,(256,256)),cv2.COLOR_RGB2HSV)
            hist=cv2.calcHist([hsv],[0,1],mask,[12,4],[0,180,0,256]).ravel()
            hist=hist/(np.linalg.norm(hist)+1e-12)
            record.update(area_fraction=area,centroid=[cx,cy],position=position,area_band=area_band,direction=direction,
                 box_count=len(title_boxes),box_count_band=boxes_band,
                 layout_signature=' / '.join([position,area_band,direction,boxes_band+'框']),
                 region_color_histogram=hist.tolist())
        render_overlay(record,row['cover_path'])
        output.append(record)
        if (i+1)%10==0:
            save(STYLE_RESULTS/'cover_ocr.json',output)
            print('OCR',i+1,'/',len(rows), 'valid',sum(x['valid_title_layout'] for x in output),round(time.time()-start,1),'s',flush=True)
    save(STYLE_RESULTS/'cover_ocr.json',output)
    modeldir=Path(rapidocr_onnxruntime.__file__).resolve().parent/'models'
    save(STYLE_RESULTS/'ocr_metadata.json',{**fingerprint,'package':'rapidocr_onnxruntime==1.4.4','onnxruntime':onnxruntime.__version__,
         'models':{p.name:sha256(p) for p in modeldir.glob('*.onnx')},'confidence_min':.55,'elapsed_seconds':round(time.time()-start,2),
         'limits':PROTOCOL['ocr']['limits']})
    print('OCR completed',len(output),'valid',sum(x['valid_title_layout'] for x in output),flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','ocr']);a=p.parse_args()
    STYLE_RESULTS.mkdir(parents=True,exist_ok=True)
    {'prepare':prepare,'ocr':ocr}[a.mode]()
