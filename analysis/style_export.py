"""Export the separate, offline-ready style experiment and corrected comparisons."""
import json
import math
import re
import shutil
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from difflib import SequenceMatcher
import numpy as np
from common import ROOT, RESULTS, DEFAULT_OUTPUT, MODEL_CACHE, load, save, csv_save, ratio, quantiles, sha256
from style_features import STYLE_RESULTS, OUTPUT, PROTOCOL, title_mask

LIMITS = [
    '169个统计对象是确认平台系列，不等于169个已确认互不相关的故事；已发现关联疑点配对排除，未知关系仍可能存在。',
    '补充实验为浏览已有材料后设计的探索分析，不是独立预注册验证；不以比例高低选择最终方法。',
    '风格组合覆盖率、文字布局接近率、模型余弦命中率是不同指标，不能相互替换或直接平均。',
    '全自动提取未作人工语义准确性核验；重复运行和证据位置正确不等于准确率。',
    '采集时封面不是已核实的历史上榜封面；全榜不等于已确认AI制作作品集合。',
]

def run():
    lock=load(STYLE_RESULTS/'protocol_lock.json')
    assert lock['protocol_sha256']==sha256(ROOT/'style_protocol.json'), 'Protocol changed after lock'
    assert lock['representatives_sha256']==sha256(RESULTS/'representatives.json'), 'Representatives changed'
    for name in ['ocr', 'dinov2', 'chinese_clip']:
        meta_path = STYLE_RESULTS/f'{name}_metadata.json'
        if name == 'chinese_clip' and not meta_path.exists():
            continue
        meta = load(meta_path)
        assert meta.get('input_sha256') == lock['representatives_sha256'], f'{name}: stale inputs; rerun inference'
        assert meta.get('protocol_sha256') == lock['protocol_sha256'], f'{name}: stale protocol; rerun inference'
        code = 'style_features.py' if name == 'ocr' else 'style_models.py'
        field = 'feature_code_sha256' if name == 'ocr' else 'model_code_sha256'
        assert meta.get(field) == sha256(ROOT/code), f'{name}: code changed; rerun inference'
        if name == 'dinov2':
            assert meta.get('ocr_sha256') == sha256(STYLE_RESULTS/'cover_ocr.json'), 'OCR changed; rerun DINOv2'
    reps=load(RESULTS/'representatives.json')
    covers=[x for x in reps if x['modality']=='cover']; ids=[x['series_id'] for x in covers]; n=len(ids)
    for modality in ['cover', 'title', 'description']:
        meta = load(RESULTS/f'{modality}_model.json')
        assert meta['input_sha256'] == lock['representatives_sha256'], f'{modality}: base embeddings stale'
        assert meta['series_ids'] == ids, f'{modality}: base embedding order differs'
    title=load(STYLE_RESULTS/'title_features.json'); td={x['series_id']:x for x in title}
    ocr=load(STYLE_RESULTS/'cover_ocr.json'); od={x['series_id']:x for x in ocr}
    exclusions=load(STYLE_RESULTS/'identity_exclusions.json')
    blocked={tuple(sorted([x['series_a'],x['series_b']])) for x in exclusions}
    index_pairs=[(i,j) for i,j in combinations(range(n),2) if tuple(sorted([ids[i],ids[j]])) not in blocked]
    allowed={tuple(sorted([ids[i],ids[j]])) for i,j in index_pairs}
    metrics=[]; data={}
    for folder in ['data','tables','assets/covers','preview']:(OUTPUT/folder).mkdir(parents=True,exist_ok=True)

    def dataset(name,label,values,method,limits=None):
        record={'id':name,'title':label,'scope':'2026年7—10月红果月榜的169个确认平台系列固定代表材料',
                'status':'探索分析','method':method,'data':values,'limits':limits or LIMITS,'sources':['data/series.json','data/protocol.json']}
        data[name]=record;save(OUTPUT/'data'/f'{name}.json',record)
    def metric(id_,label,num,den,definition,method,unit='%',limits=None):
        r={'id':id_,'title':label,'value':ratio(num,den)['percent'] if unit=='%' else num,
           'unit':unit,**ratio(num,den),'denominator_definition':definition,'method':method,
           'scope':'169个确认平台系列固定代表材料','status':'探索分析','limits':limits or LIMITS,'sources':['data/series.json','data/protocol.json']}
        metrics.append(r);return r
    def pair_summary(selected, valid_ids):
        selected=list(selected);valid=set(valid_ids)
        eligible=[(a,b) for a,b in allowed if a in valid and b in valid]
        connected={a for p in eligible for a in p};members={a for p in selected for a in p}
        return {'series_rate':ratio(len(members),len(connected)),'share_all_series':ratio(len(members),n),
                'pair_rate':ratio(len(selected),len(eligible)),'series_ids':sorted(members),'pairs':[list(p) for p in sorted(selected)],
                'eligible_series_ids':sorted(connected)}
    def pairs_from_members(members):
        return {tuple(sorted(p)) for p in combinations(sorted(members),2) if tuple(sorted(p)) in allowed}
    def members_rows(groups,valid_ids):
        out=[]
        for label,members in groups.items():
            pairs=pairs_from_members(members)
            involved={a for p in pairs for a in p}
            out.append({'label':label,'count':len(members),'series_ids':sorted(members),
                        'share_valid':ratio(len(members),len(valid_ids)),'share_all':ratio(len(members),n),
                        'repeat_series_count':len(involved),'allowed_pair_count':len(pairs)})
        return sorted(out,key=lambda x:(-x['count'],x['label']))

    # Stable series registry: no local absolute paths are copied into the delivery.
    series=[]
    base=load(DEFAULT_OUTPUT/'data/series.json')
    base_series={x['series_id']:x for x in (base['data'] if isinstance(base,dict) else base)}
    for r in covers:
        sid=r['series_id'];base=base_series[sid]
        source=DEFAULT_OUTPUT/r['asset'];shutil.copy2(source,OUTPUT/r['asset'])
        series.append({'series_id':sid,'title':base['title'],'title_raw':td[sid]['title_raw'],'title_style':td[sid]['title_style'],
             'cover':r['asset'],'ocr_overlay':od[sid]['overlay'],'description':r['description'],'genre':td[sid]['genre'],
             'content_type':r['content_type'],'source_url':r['source_url'],'work_id':r['work_id'],
             'ranking_id':r['ranking_id'],'season_code':r['season_code'],'producer_brands':base['producer_brands']})
    dataset('series','统一系列资料',series,'沿用原实验代表版本；每系列每模态一个版本，不复制续季或跨月权重')
    dataset('protocol','冻结的补充实验方案',lock,'方案文件指纹在提取前保存；已浏览原结果，明确探索属性')
    dataset('identity','配对排除与身份疑点',{'rows':exclusions,'blocked_inside_sample':sum(p[0] in ids and p[1] in ids for p in blocked),
             'valid_pairs':len(allowed),'series_count':n},'沿用原排除表，补充两组关联疑点与固定自动筛查；排除配对但不擅自合并系列')
    csv_save(OUTPUT/'tables/identity_exclusions.csv',exclusions)

    # Specific title templates, distinct from coarse formal features.
    groups=defaultdict(set)
    for r in title:
        for t in r['templates']:groups[t['label']].add(r['series_id'])
    template_rows=members_rows(groups,ids);template_pairs=set(); compound_pairs=set()
    for members in groups.values():
        template_pairs |= pairs_from_members(members)
    for a,b in template_pairs:
        if {x['label'] for x in td[a]['content_cues']} & {x['label'] for x in td[b]['content_cues']}:compound_pairs.add((a,b))
    template_summary=pair_summary(template_pairs,ids);compound_summary=pair_summary(compound_pairs,ids)
    frequency=[]
    for minimum in PROTOCOL['title']['frequency_levels']:
        pairs=set()
        for members in groups.values():
            if len(members)>=minimum:pairs |= pairs_from_members(members)
        frequency.append({'minimum_series_per_template':minimum,**pair_summary(pairs,ids)})
    top5=set()
    for r in template_rows[:5]:top5.update(r['series_ids'])
    coarse=[]
    for key,label in [('comma','含逗号分句'),('colon','含冒号分题'),('question','含问号')]:
        matched=[r['series_id'] for r in title if r[key]];coarse.append({'label':label,**ratio(len(matched),n),'series_ids':matched})
    for category in ['rhetoric','content_cues']:
        for label in sorted({x['label'] for r in title for x in r[category]}):
            members=[r['series_id'] for r in title if label in {x['label'] for x in r[category]}]
            coarse.append({'label':label,'kind':category,**ratio(len(members),n),'series_ids':members})
    # Permute content cue sets only, retaining templates and within-stratum marginals.
    rng=np.random.default_rng(20261113); strata=defaultdict(list)
    for i,r in enumerate(title):strata[(r['genre'],r['content_type'])].append(i)
    cue_sets=[{x['label'] for x in r['content_cues']} for r in title];tindex={r['series_id']:i for i,r in enumerate(title)}
    tp=[(tindex[a],tindex[b]) for a,b in template_pairs]; null_counts=[]
    for _ in range(500):
        shuffled=list(cue_sets)
        for indices in strata.values():
            order=rng.permutation(indices)
            for i,j in zip(indices,order):shuffled[i]=cue_sets[j]
        union={x for i,j in tp if shuffled[i]&shuffled[j] for x in [i,j]}
        null_counts.append(len(union))
    null={'iterations':500,'seed':20261113,'strata':'自动题材×原内容形态','strata_count':len(strata),
          'series_in_nonsingleton_strata':sum(len(v) for v in strata.values() if len(v)>1),
          'observed_series':compound_summary['series_rate']['numerator'],'permutation_quantiles':quantiles(null_counts),
          'fraction_null_at_least_observed':sum(x>=compound_summary['series_rate']['numerator'] for x in null_counts)/500,
          'monte_carlo_tail_plus_one':(1+sum(x>=compound_summary['series_rate']['numerator'] for x in null_counts))/501,
          'limits':'只检验本样本内具体模板与词项类别的关联，非外部同质化基准，不是因果或语义准确率；标签和规则本身带有关联。'}
    dataset('title_style','标题句式与命名风格',{'rows':title,'templates':template_rows,'template_coverage':template_summary,
       'specific_and_content':compound_summary,'frequency_sensitivity':frequency,'top5_template_union':ratio(len(top5),n),
       'coarse_features':coarse,'length_distribution':[{'length':k,'count':v} for k,v in sorted(Counter(r['char_count'] for r in title).items())],
       'null_reference':null,'codebook':load(STYLE_RESULTS/'title_codebook.json')},
       '保留标点、仅移除确认季号；具体触发词及顺序匹配并保留字符偏移。普通标点和单词不当具体模板；不同语义角色尚未人工核验。')
    csv_save(OUTPUT/'tables/title_features.csv',title);csv_save(OUTPUT/'tables/title_templates.csv',template_rows);csv_save(OUTPUT/'tables/title_coarse_features.csv',coarse)
    title_pair_rows=[]
    for a,b in sorted(allowed):
        shared_templates=sorted({x['label'] for x in td[a]['templates']} & {x['label'] for x in td[b]['templates']})
        shared_cues=sorted({x['label'] for x in td[a]['content_cues']} & {x['label'] for x in td[b]['content_cues']})
        title_pair_rows.append({'series_a':a,'series_b':b,'shared_specific_templates':shared_templates,
             'shared_content_cues':shared_cues,'template_repeat':bool(shared_templates),
             'template_and_content_repeat':bool(shared_templates and shared_cues)})
    csv_save(OUTPUT/'tables/title_style_pairs.csv',title_pair_rows)
    metric('style.title.template_repeat','共享具体标题结构模板的系列占比',template_summary['series_rate']['numerator'],n,'169个有效代表剧名','与至少另一允许配对系列共享至少一个固定具体结构模板；24种模板规则并集')
    metric('style.title.template_and_content','标题结构模板与内容词项类别同时重复的系列占比',compound_summary['series_rate']['numerator'],n,'169个有效代表剧名','与同一个其他系列共享具体结构模板和至少一类内容词项')
    metric('style.title.top5','前五种具体标题模板覆盖率',len(top5),n,'169个有效代表剧名','按出现系列数排序取前5模板，系列并集去重；不等于高相似率')

    # OCR geometry and literal text-region appearance.
    valid_ocr=[sid for sid in ids if od[sid]['valid_title_layout']];layout_groups=defaultdict(set)
    for sid in valid_ocr:layout_groups[od[sid]['layout_signature']].add(sid)
    signature_rows=members_rows(layout_groups,valid_ocr); signature_pairs=set()
    for members in layout_groups.values():signature_pairs |= pairs_from_members(members)
    masks=np.array([title_mask(od[sid],64).reshape(-1) for sid in valid_ocr],dtype=np.float32)
    intersections=masks@masks.T;areas=masks.sum(axis=1);oi={sid:i for i,sid in enumerate(valid_ocr)}
    layout_pairs=[];close_pairs=set();color_pairs=set()
    for a,b in combinations(valid_ocr,2):
        key=tuple(sorted([a,b]))
        if key not in allowed:continue
        i,j=oi[a],oi[b];inter=intersections[i,j];union=areas[i]+areas[j]-inter
        iou=float(inter/union) if union else 0
        area_ratio=min(od[a]['area_fraction'],od[b]['area_fraction'])/max(od[a]['area_fraction'],od[b]['area_fraction'])
        color=float(np.dot(od[a]['region_color_histogram'],od[b]['region_color_histogram']))
        close=iou>=.60 and area_ratio>=2/3 and od[a]['direction']==od[b]['direction'] and abs(od[a]['box_count']-od[b]['box_count'])<=1
        if close:close_pairs.add(key)
        if close and color>=.80:color_pairs.add(key)
        layout_pairs.append({'series_a':key[0],'series_b':key[1],'mask_iou':iou,'area_ratio':area_ratio,'region_color_cosine':color,
                             'close_layout':close,'close_layout_and_region_color':close and color>=.80})
    signature_summary=pair_summary(signature_pairs,valid_ocr);close_summary=pair_summary(close_pairs,valid_ocr);color_summary=pair_summary(color_pairs,valid_ocr)
    public_ocr=[{k:v for k,v in r.items() if k!='region_color_histogram'} for r in ocr]
    dataset('cover_layout','封面文字布局与区域颜色',{'valid_series':len(valid_ocr),'missing_series':n-len(valid_ocr),'features':public_ocr,
       'signatures':signature_rows,'signature_repeat':signature_summary,'close_layout':close_summary,'close_layout_and_color':color_summary,
       'model':load(STYLE_RESULTS/'ocr_metadata.json')},PROTOCOL['ocr']['close_layout'],[PROTOCOL['ocr']['limits']]+LIMITS)
    csv_save(OUTPUT/'tables/cover_ocr_features.csv',public_ocr);csv_save(OUTPUT/'tables/cover_layout_pairs.csv',layout_pairs);csv_save(OUTPUT/'tables/cover_layout_signatures.csv',signature_rows)
    metric('style.cover.layout_signature','共享四项文字布局组合的有效系列占比',signature_summary['series_rate']['numerator'],len(valid_ocr),
           'OCR标题匹配达到标准且存在可比对象的系列','位置×文字区面积档×方向×OCR框数档完全相同；是组合重复，不是整图高相似')
    metric('style.cover.close_layout','文字布局空间接近的有效系列占比',close_summary['series_rate']['numerator'],len(valid_ocr),
           'OCR标题区域有效系列','与另一允许系列标题框并集IoU≥0.60、面积比≥2/3、方向相同、框数差≤1')
    metric('style.cover.close_layout_color','文字布局与文字区颜色同时接近的有效系列占比',color_summary['series_rate']['numerator'],len(valid_ocr),
           'OCR标题区域有效系列','布局空间接近，且OCR文字区HSV颜色直方图余弦≥0.80；不是笔画颜色')

    # Model-specific curves. The original score threshold does not transfer calibration.
    variants={
       'dinov2_center':(RESULTS/'cover_embeddings.npy','DINOv2 原中心裁切',ids),
       'dinov2_full':(STYLE_RESULTS/'dinov2_full_pad.npy','DINOv2 完整图补边',ids),
       'dinov2_masked':(STYLE_RESULTS/'dinov2_title_masked_pad.npy','DINOv2 标题区遮挡后补边',valid_ocr),
       'dinov2_center_ocr_subset':(RESULTS/'cover_embeddings.npy','DINOv2 原中心裁切（仅OCR有效子集）',valid_ocr),
       'dinov2_full_ocr_subset':(STYLE_RESULTS/'dinov2_full_pad.npy','DINOv2 完整图补边（仅OCR有效子集）',valid_ocr),
       'chinese_clip_resize':(STYLE_RESULTS/'chinese_clip_official_full_resize.npy','Chinese CLIP 官方完整图缩放',ids),
       'chinese_clip_pad':(STYLE_RESULTS/'chinese_clip_full_pad.npy','Chinese CLIP 完整图补边',ids),
       'bge_title':(RESULTS/'title_embeddings.npy','BGE-M3 剧名语义（关联疑点排除后）',ids),
       'bge_description':(RESULTS/'description_embeddings.npy','BGE-M3 简介语义（关联疑点排除后）',ids),
    }
    model_values={};model_rows=[];matrices={};model_pairs={}
    for key,(path,label,valid) in variants.items():
        if not path.exists():
            model_values[key]={'label':label,'status':'模型未完成','reason':'权重或推理结果不可用'};continue
        emb=np.load(path);checknorm=np.linalg.norm(emb,axis=1);assert emb.shape[0]==n and np.allclose(checknorm,1,atol=1e-4)
        sims=emb@emb.T;matrices[key]=sims
        selected_valid=set(valid)
        pairs=[(ids[i],ids[j],float(sims[i,j])) for i,j in index_pairs if ids[i] in selected_valid and ids[j] in selected_valid]
        model_pairs[key]=pairs
        curves=[]
        for threshold in PROTOCOL['cover_models']['threshold_grid']:
            selected={tuple(sorted([a,b])) for a,b,s in pairs if s>=threshold}
            summary=pair_summary(selected,valid)
            # Large membership/pair arrays are in CSV; compact JSON curve remains directly usable.
            curves.append({'threshold':threshold,**{k:v for k,v in summary.items() if k not in ['pairs','eligible_series_ids']}})
        maxima={sid:max((s for a,b,s in pairs if sid in [a,b]),default=None) for sid in valid}
        top=sorted(pairs,key=lambda x:(-x[2],x[0],x[1]))[:12]
        model_values[key]={'label':label,'status':'已计算','valid_series':len(valid),'valid_pairs':len(pairs),
           'all_pair_quantiles':quantiles(s for a,b,s in pairs),'nearest_score_quantiles':quantiles(maxima.values()),
           'thresholds':curves,'top_pairs':[{'series_a':a,'series_b':b,'score':s} for a,b,s in top]}
        for a,b,s in pairs:model_rows.append({'model_variant':key,'series_a':a,'series_b':b,'score':s})
    joint=[]
    for threshold in [.60,.70,.80]:
        chosen={tuple(sorted([a,b])) for a,b,s in model_pairs['dinov2_full'] if s>=threshold and tuple(sorted([a,b])) in color_pairs}
        summary=pair_summary(chosen,valid_ocr)
        joint.append({'dinov2_full_min':threshold,'layout_min_iou':.60,'region_color_min_cosine':.80,**summary})
        metric('style.cover.layout_color_image_'+str(int(threshold*100)),
          f'文字布局与区域颜色接近，且完整画面DINOv2≥{threshold:.2f}的有效系列占比',
          summary['series_rate']['numerator'],len(valid_ocr),'OCR标题区域有效系列',
          f'同一对系列满足文字布局IoU≥0.60、面积比≥2/3、方向相同、框数差≤1、区域颜色余弦≥0.80，且DINOv2完整图≥{threshold:.2f}；探索候选')
    # Same preprocessing comparison on common OCR-valid series only.
    commonvalid=set(valid_ocr);jaccards=[]
    for key in ['dinov2_full','dinov2_masked','chinese_clip_resize','chinese_clip_pad']:
        if key not in matrices:continue
        commonpairs=[(i,j) for i,j in index_pairs if ids[i] in commonvalid and ids[j] in commonvalid]
        near={};original={}
        for i,sid in enumerate(ids):
            if sid not in commonvalid:continue
            indices=[j for j,other in enumerate(ids) if other in commonvalid and tuple(sorted([sid,other])) in allowed]
            near[sid]=max(indices,key=lambda j:float(matrices[key][i,j]))
            original[sid]=max(indices,key=lambda j:float(matrices['dinov2_center'][i,j]))
        jaccards.append({'variant':key,'common_series':len(commonvalid),'same_top1_neighbor':ratio(sum(near[sid]==original[sid] for sid in near),len(near)),
           'score_change_quantiles':quantiles(float(matrices[key][i,j]-matrices['dinov2_center'][i,j]) for i,j in commonpairs),
           'interpretation':'跨模型分差仅显示刻度变化，无共同标定，不解释为准确度提升'})
    dataset('cover_models','图像与文本模型对照及完整阈值曲线',{'variants':model_values,'joint_layout_image':joint,
        'neighbor_comparison_with_dinov2_center':jaccards,'models':{'dinov2':load(STYLE_RESULTS/'dinov2_metadata.json'),
        'chinese_clip':load(STYLE_RESULTS/'chinese_clip_metadata.json') if (STYLE_RESULTS/'chinese_clip_metadata.json').exists() else None,
        'chinese_clip_checkpoint_manifest':load(MODEL_CACHE/'chinese_clip/manifest.json') if (MODEL_CACHE/'chinese_clip/manifest.json').exists() else None}},
        '同代表版本、同关联排除表；各模型各自输出全部阈值，不选择最大比例冒充统一真实相似率')
    csv_save(OUTPUT/'tables/model_pairs.csv',model_rows)

    # Exploratory zero-shot visual labels, with an explicit unknown margin.
    visual=[];visual_groups=[];visual_signature={};visual_summary=None
    if (STYLE_RESULTS/'clip_visual_labels.json').exists():
        visual=load(STYLE_RESULTS/'clip_visual_labels.json')
        fieldnames=list(visual[0]['fields'])
        for field in fieldnames:
            counts=Counter(r['fields'][field]['label'] or '未知' for r in visual)
            visual_groups.extend({'field':field,'label':label,**ratio(count,n)} for label,count in counts.items())
        vg=defaultdict(set);vvalid=[]
        for r in visual:
            fields=r['fields']; values=[fields[k]['label'] for k in ['render_style','people_count','shot']]
            if all(values):
                vg[' / '.join(values)].add(r['series_id']);vvalid.append(r['series_id'])
                visual_signature[r['series_id']]=' / '.join(values)
        vrows=members_rows(vg,vvalid);vp=set()
        for members in vg.values():vp |= pairs_from_members(members)
        visual_summary=pair_summary(vp,vvalid)
        dataset('visual_labels','模型估计的画风与人物构图',{'rows':visual,'field_distributions':visual_groups,'complete_signature_series':len(vvalid),
           'signatures':vrows,'signature_repeat':visual_summary},'固定中文候选描述的Chinese CLIP零样本匹配，最高与次高分差<0.02记未知；组合为画风×人物数×景别',
           ['标签是模型候选，不是人工核实的人物检测；重复分类不等于整图高度相似。']+LIMITS)
        csv_save(OUTPUT/'tables/visual_model_labels.csv',visual);csv_save(OUTPUT/'tables/visual_signature_counts.csv',vrows)
    else:dataset('visual_labels','模型估计的画风与人物构图',{'status':'未完成','reason':'Chinese CLIP不可用'},'不以其他指标冒充')

    # Cross-feature conjunction: same OTHER series must meet both rules.
    intersect=template_pairs & color_pairs
    intersect_narrow=compound_pairs & color_pairs
    summary_inter=pair_summary(intersect,valid_ocr)
    dataset('intersections','封面与标题风格的同对交集',{'template_and_layout_color':summary_inter,
            'template_content_and_layout_color':pair_summary(intersect_narrow,valid_ocr)},
            '同一对允许系列同时满足文字布局和区域颜色接近、具体标题模板重复；避免各自命中不同对象冒充同对交集')
    metric('style.cross.title_layout','同一对系列同时命中具体标题模板与文字布局颜色规则的系列占比',
        summary_inter['series_rate']['numerator'],len(valid_ocr),'OCR有效且标题有效的共同系列','同一对满足两条件；未知材料不计为零')

    # Within genre × form comparisons, without claiming an external benchmark.
    stratum_rows=[]
    for key,pairs in model_pairs.items():
        for relation in ['同题材同形态','其他可比配对']:
            values=[s for a,b,s in pairs if ((td[a]['genre']==td[b]['genre'] and td[a]['genre']!='未知' and td[a]['content_type']==td[b]['content_type']) == (relation=='同题材同形态'))]
            stratum_rows.append({'variant':key,'relation':relation,'pair_count':len(values),'quantiles':quantiles(values),
                 'at_080':ratio(sum(s>=.8 for s in values),len(values)), 'limits':'配对非独立，题材为自动规则主类；描述性对照，不作因果或行业外推'})
    dataset('strata','同题材同内容形态的描述性对照',stratum_rows,'各模型内分层报告分位数；未知题材不归入同题材组')
    csv_save(OUTPUT/'tables/stratum_model_summary.csv',stratum_rows)

    # Reviewable cases: the pair is the evidence unit, never a transitive cluster.
    cases=[]
    def add_cases(kind,pairs,scorefield=None,maximum=8):
        for pair in pairs[:maximum]:
            if isinstance(pair,dict):a,b=pair['series_a'],pair['series_b']; evidence={k:v for k,v in pair.items() if k not in ['series_a','series_b']}
            else:a,b=pair;evidence={}
            if tuple(sorted([a,b])) not in allowed:continue
            shared=sorted({x['label'] for x in td[a]['templates']} & {x['label'] for x in td[b]['templates']})
            cases.append({'case_id':f'{kind}_{len(cases)+1:03d}','kind':kind,'series_a':a,'series_b':b,'evidence':evidence,
                          'shared_title_templates':shared,'same_layout_signature':od[a].get('layout_signature')==od[b].get('layout_signature'),
                          'title_a':td[a]['title_style'],'title_b':td[b]['title_style']})
    add_cases('title_template',sorted(template_pairs))
    add_cases('title_template_content',sorted(compound_pairs))
    add_cases('layout_color',sorted([x for x in layout_pairs if x['close_layout_and_region_color']],key=lambda x:-x['mask_iou']))
    add_cases('title_layout_intersection',sorted(intersect))
    for key,value in model_values.items():
        if value['status']=='已计算':add_cases(key,value['top_pairs'],maximum=4)
    dataset('cases','逐对可核对案例',cases,'每对附原封面、OCR叠图、标题与原始来源；图像与文字证据通过统一系列表连接')
    csv_save(OUTPUT/'tables/cases.csv',cases)
    dataset('metrics','新增网页指标',metrics,'每项独立保留分子分母及规则，原整图相似指标由cover_models提供关联排除后的更正值')
    csv_save(OUTPUT/'tables/metrics.csv',metrics)
    report(title=title,model_values=model_values,template_summary=template_summary,compound_summary=compound_summary,
           valid_ocr=valid_ocr,signature_summary=signature_summary,close_summary=close_summary,color_summary=color_summary,
           signature_rows=signature_rows,template_rows=template_rows,joint=joint,null=null,identity=exclusions,n=n,
           visual_groups=visual_groups,visual_complete=len(vvalid) if visual else 0)
    shutil.copy2(ROOT/'style_protocol.json',OUTPUT/'补充实验规则.json')
    save(OUTPUT/'data/manifest.json',{'version':PROTOCOL['version'],'sample_series':n,'valid_cross_series_pairs':len(allowed),
          'sections':list(data),'main_preview':'preview/index.html','report':'补充实验结果解读.md',
          'protocol_sha256':lock['protocol_sha256'],'limits':LIMITS,
          'relationship_to_original':'补充新风格指标；cover_models中的旧模型曲线已排除两组新发现的关联疑点，引用Part2时优先此包。原交付包不改写。'})
    save(OUTPUT/'data/sources.json',{'input_fingerprints':load(RESULTS/'input_fingerprints.json'),
       'protocol_sha256':lock['protocol_sha256'],'representatives_sha256':lock['representatives_sha256'],
       'source_links':sorted({r['source_url'] for r in reps}),
       'model_manifest_files':['data/cover_models.json','data/cover_layout.json'],
       'analysis_code_sha256':{p.name:sha256(p) for p in ROOT.glob('style_*.py')},
       'source_file_hashes':{f'results/style/{p.name}':sha256(p) for p in STYLE_RESULTS.glob('*.json')}})
    (OUTPUT/'preview/data.js').write_text('window.STYLE_DATA = '+json.dumps(data,ensure_ascii=False,allow_nan=False)+';\n',encoding='utf-8')
    for filename in ['index.html','app.js','style.css']:
        shutil.copy2(ROOT/'style_preview'/filename,OUTPUT/'preview'/filename)
    print(json.dumps({'output':str(OUTPUT),'metrics':len(metrics),'valid_pairs':len(allowed),
          'title_repeat':template_summary['series_rate'],'layout_close_color':color_summary['series_rate']},ensure_ascii=False),flush=True)

def report(**r):
    def rate(x):return f"{x['numerator']}/{x['denominator']}（{x['percent']:.2f}%）" if x['denominator'] else '缺少有效分母'
    models=r['model_values'];curve=lambda key,t:next(x for x in models[key]['thresholds'] if x['threshold']==t)['series_rate']
    paragraphs=[
       '# 红果风格补充实验：结果与使用说明',
       '本轮实际运行了标题具体句式规则、169张封面OCR及空间布局比较、DINOv2完整图与文字区遮挡对照、Chinese CLIP图像与零样本构图候选分析。全部结果基于原169个确认平台系列的固定代表材料；同系列续季、跨月上榜不增加权重。',
       '**研究问题从整张图片或标题含义是否高度接近，扩展为命名结构、文字布局和视觉组合是否集中。新增覆盖率不能替换原高相似率。** 本轮设计已参考旧结果和现存标题，是探索分析；方法及判定规则在批量提取前保存了指纹，不宣称独立预注册验证。',
       f"**最直观的发现：具体标题结构重复覆盖{rate(r['template_summary']['series_rate'])}；文字布局与区域颜色同时接近覆盖{rate(r['color_summary']['series_rate'])}。** 在后者基础上，再要求完整图DINOv2≥0.70，覆盖{rate(next(x['series_rate'] for x in r['joint'] if x['dinov2_full_min']==.70))}。这更支持描述排版和部分命名结构的重复，尚不足以称多数作品整张封面高度相似。",
       '## 1．先处理同故事或版本关系疑点',
       '两组疑点为“都重生了，谁还装富二代啊 / 都重生了，这富二代我不装了”和“爆笑姐妹… / 反向拿捏…”。前者共同出现陆川、韩东、陈子昂；后者共同出现夏小柒、乔然和陆家妯娌。不同平台系列号不足以认定为无关故事。',
       '两组配对均从本轮全部主比较排除，保留系列和原材料，不擅自判定同一版本或合并。另按固定近名+简介低频片段规则筛查，结果详见identity.json；原排除表另有一组涉及样本外待核单元。169选2共14,196对，本轮有效14,194对。尚未发现的关系仍可能存在。',
       '排除后，BGE-M3在0.85下的剧名和简介命中均为0/169。原交付包2.37%和1.18%是此次身份疑点处理前的初算值，本轮不再作为已排除关联的跨故事主结果引用。',
       '## 2．标题句式：能测到哪些重复',
       f"与至少另一个允许比较的系列共享具体结构模板的有{rate(r['template_summary']['series_rate'])}；同时共享至少一类内容词项的有{rate(r['compound_summary']['series_rate'])}。这不是新的语义高相似率。",
       '例：固定模板包括“谁说…不能…”、“让你…没让你…”、“…只想…却/非要…”等。只有“后”“之”或一个逗号不算具体模板；反问、第一人称、身份词和标点另作描述。模板本身仍有宽窄差异，角色和语义关系未作人工核验。',
       '| 具体结构规则 | 出现系列数 | 有允许配对的重复系列数 |',
       '| --- | --- | --- |',
    ]
    paragraphs.extend(f"| {x['label']} | {x['count']} | {x['repeat_series_count']} |" for x in r['template_rows'][:10])
    paragraphs += [
       '每个标题可命中多个模板，总计不可直接相加。另输出最少2、3、5个系列采用的覆盖率，以及Top 5模板并集。',
       f"将内容标签在同题材同形态内打乱500次，联合覆盖系列数的中位数为{r['null']['permutation_quantiles']['median']}，实测为{r['null']['observed_series']}。这个对照只描述模板与内容词项是否结合，不能证明比其他平台或其他时代更同质化。详见title_style.json。",
       '## 3．封面文字布局：粗组合与空间接近分开',
       f"169张封面中，162张达到固定OCR标题匹配标准，7张记缺失。共享位置×面积档×方向×识别框数四项布局组合的有效系列占比为{rate(r['signature_summary']['series_rate'])}。",
       f"使用更细条件，文字框并集IoU≥0.60、面积比≥2/3、方向相同且框数差≤1，命中系列占比为{rate(r['close_summary']['series_rate'])}；再加文字区颜色直方图余弦≥0.80后，为{rate(r['color_summary']['series_rate'])}。",
       f"最常见的布局组合为“{r['signature_rows'][0]['label']}”，涉及{r['signature_rows'][0]['count']}个系列，占全部169个系列的{r['signature_rows'][0]['count']/169*100:.2f}%。这个共同组合不能直接证明这些封面两两高度相似。",
       'OCR叠图中绿色框为达到标题匹配条件的区域，灰色框为其他识别文字；匹配不足时用橙色。OCR框不是文字笔画，文字区颜色包含框内背景；框数不等于人工核实的排版行数。少数字体或竖排标题难以识别，不能把7个缺失当作没有标题或风格独特。',
       '## 4．完整图是否改变原模型结果',
       '| 模型及输入方式 | ≥0.70涉及系列 | ≥0.80涉及系列 | ≥0.85涉及系列 |',
       '| --- | --- | --- | --- |',
    ]
    for k in ['dinov2_center','dinov2_full','dinov2_center_ocr_subset','dinov2_full_ocr_subset','dinov2_masked','chinese_clip_resize','chinese_clip_pad']:
        if models[k]['status']=='已计算':paragraphs.append('| '+models[k]['label']+' | '+' | '.join(rate(curve(k,t)) for t in [.7,.8,.85])+' |')
        else:paragraphs.append('| '+models[k]['label']+' | 未完成 | 未完成 | 未完成 |')
    paragraphs += [
       '同一DINOv2的中心裁切与补边比较，可以帮助判断裁切对结果的影响；标题遮挡不是完美去字，灰色遮挡本身会影响图像特征，因此只作对照。遮挡实验仅统计162个OCR有效系列，其他方式为169个，不能直接把覆盖人数差当作效果差。',
       'Chinese CLIP和DINOv2的分数刻度不同，相同0.85不能认作相同严格程度；新模型更高的命中率也不等于更准确。预览和JSON完整提供0.50至0.95每0.05一档的结果，而非挑最高比例。没有本领域可靠真值标签，不能把任一档称为真实同质化率。',
       '## 5．画面与文字布局联合规则',
       '在文字布局空间及区域颜色同时接近的基础上，对DINOv2完整图分数再设三档，要求同一对系列满足所有条件：',
       '| DINOv2完整图最低分 | 命中有效系列占比 | 命中配对数 |',
       '| --- | --- | --- |',
    ]
    paragraphs.extend(f"| {x['dinov2_full_min']:.2f} | {rate(x['series_rate'])} | {x['pair_rate']['numerator']} |" for x in r['joint'])
    paragraphs += [
       '这些是明确规则下的联合候选，不是人类相似评价。只共享大类组合的较高覆盖率与联合规则下的较低覆盖率可以同时成立。所有案例按具体配对展示，不用A像B、B像C的连通链声称A、B、C全部相像。',
       '## 6．零样本人物与画风标签怎样使用',
       'Chinese CLIP根据冻结的中文候选描述，估计画风、人物数量、景别和构图；每类两个描述取平均，最高与次高余弦差小于0.02记未知。分差不是概率，模型候选未做人工准确性核验。',
       '本次未知数分别为：'+ '、'.join(f"{x['field']} {x['numerator']}/169" for x in r['visual_groups'] if x['label']=='未知') +f"。三个组合维度均可用的仅{r['visual_complete']}个系列，无法支撑可靠的整体构图重复比例；本轮将该项视为未获得充分可用结果，不降低分差门槛填满分类。",
       '画风×人物数×景别的组合分布可以作为风格构成的探索图；不能把“都被分到3D、双人、半身”直接称为高度相似，也不能据此认定AI制作。固定提示、原分数和未知原因均已交付。字体家族、描边及人物精确检测框本轮未可靠测得，未用其他指标冒充。',
       '## 7．网页引用建议',
       '正文可以分别写“具体标题结构模板覆盖”“文字布局接近候选覆盖”“图像模型分数达到某标准的覆盖”，同时给分子和分母。读者点击后应看到具体标题、封面、OCR叠图和来源。只有数据支持到哪一层，结论就写到哪一层。',
       '仍不能据此认定抄袭、同故事、AI导致同质化、行业整体严重程度或治理效果。缺少同题材同形态的外部参照，本轮只提供内部构成和分层对照。',
       '## 8．文件与复现',
       '直接双击preview/index.html即可离线查看，无需服务器。data/metrics.json是新增指标，data/cover_models.json包含关联排除后的原模型曲线及新对照；tables/保留配对和字段证据，assets/包含封面与OCR框叠图。数据JSON不含本机绝对路径。',
       '代码位于原项目analysis/style_*.py及style_preview/。执行顺序：style_features.py prepare → style_features.py ocr → style_models.py dinov2 → style_models.py clip → style_export.py → validate_style.py。第二模型权重先由style_fetch_models.py下载到任务缓存。',
       '基础与风格交付按配置分别输出，原始采集数据只读；当前基础代码也已排除这两组疑点。后续网页整合以此次验收输出为准，不沿用旧的文字高相似初算比例。',
    ]
    text='\n\n'.join(paragraphs)+'\n'
    text=re.sub(r'(?m)(\|[^\n]*\|)\n\n(?=\|)',r'\1\n',text)
    (OUTPUT/'补充实验结果解读.md').write_text(text,encoding='utf-8')
    import markdown
    body=markdown.markdown(text,extensions=['tables'])
    document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>红果风格补充实验结果解读</title><link rel="stylesheet" href="preview/style.css"></head><body><main class="wrap panel"><p><a href="preview/index.html">打开交互验收预览</a></p>'+body+'</main></body></html>'
    (OUTPUT/'补充实验结果解读.html').write_text(document,encoding='utf-8')

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');run()
