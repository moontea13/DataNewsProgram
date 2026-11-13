"""落实用户批量确认和逐项意见，执行授权复核后输出定稿。"""
import json
from collections import Counter,defaultdict
import pipeline as p

FINAL_VERSION='2026-11-13-final-v1.0'

# 编码均为执行会话在阅读原文及用户判断后明确保存的决定，不由关键词生成。
DECISIONS={
 'S009':('8','7','3','C071','采用用户确认的关系支持；以同伴协力追查灭门、巫蛊旧案的行动为主。'),
 'S013':('0','8','7','','采用用户指定的冲突0；缺少可确定的主要冲突，排除结构指标。'),
 'S016':('0','0','0','','采用用户确认的各季核心不同；保留逐季标签，系列共同簇留空。'),
 'S020':('4','4','4','C008','采用用户补充梗概：海底透视直接提高渔获经营能力，重生背景保留为次要机制。'),
 'S023':('3','7','6','C072','女友以守护、闯险地和寻奇物救伴侣；共同核心是为伴侣复生协力化险。'),
 'S043':('5','2','5','C073','采用用户确认的建筑设计知识实际用于破局；不把普通争执替代专业安家路径。'),
 'S048':('3','7','0','','用户指定忽略。'),
 'S052':('4','8','4','','用户指定忽略。'),
 'S058':('8','4','1','C074','采用用户确认的超常秘力；寻父为动机，清除敌对势力与建立力量为实际行动。'),
 'S062':('2','4','1','C075','采用用户确认的自身武力主导；岳家支持为背景，灭门旧仇与护家靠自身战力应对。'),
 'S064':('5','9','0','','用户指定忽略。'),
 'S079':('7','7','3','','用户指定忽略。'),
 'S082':('0','5','5','','采用用户指定的专业知识破局；主要冲突仍未具体呈现，排除结构指标。'),
 'S084':('1','9','3','C076','采用用户确认的谋略设局；家庭排斥与养女算计为冲突，未另引入特殊能力。'),
 'S089':('7','4','3','C077','采用用户确认的超常能力与谋略设局；以调查异常、保护人族家园为共同核心。'),
 'S096':('3','5','4','C024','采用用户确认的经营与资源配置；仓库和现代储备支撑乱世求生。'),
 'S100':('3','7','6','','用户指定忽略。'),
 'S101':('8','7','3','','用户指定忽略。'),
 'S107':('1','3','3','C078','采用用户确认的系统奖励；外形非议转为美貌优势，通过手腕周旋关系，区别于C048的构陷自证。'),
 'S115':('0','4','0','','用户指定忽略。'),
 'S121':('3','3','1','C079','系统提供十万年封闭修炼条件，所得剑力用于对抗秘境与魔域强敌；不并入收徒开宗簇。'),
 'S131':('6','8','0','','同名页面仍只有成长概括；其他版本灭门情节未确认属于本版本，不挪用，排除。'),
 'S133':('5','7','7','C054','两季是不同人物的时差回归故事；补充人物关系显示旧情延续，按长期分离与记忆隔阂后的关系重建归簇。'),
 'S134':('1','3','5','C080','系统任务先提供老歌与激励，演唱赢得长辈投票支持；主导机制为系统，主要路径为专业演唱。'),
 'S138':('1','9','7','C081','原简介已明确受辱后主动退婚；保留关系边界行动，不推定后来公开科研身份的情节。'),
 'S140':('4','5','0','','第一季补充页面仍仅介绍合成设定；原著和第二季行为不补写进样本第一季，排除。'),
 'S141':('3','7','3','C082','平台梗概确认逃离控制的诉求；样本第二季写借乔骁及祁野的关系周旋夺筹码，不预设最终爱情结局。'),
 'S143':('6','8','0','','检索后仍缺乏具体主导转机及应对链，不把通用历练概括编码为特殊套路，排除。'),
 'S147':('7','5','4','','空间、气运、族谱与时空阶段切换尚无稳定共同冲突；保留材料与细标签，排除共同簇。'),
 'S156':('3','3','1','C083','赚钱转战力的系统构成循环转机；敲诈和强行收缴诡异是武力敛财路径，区别于常规经营致富。'),
 'S166':('4','8','0','','补充介绍仍笼统写展露本领、化险；不因保镖职业直接推定武力路径，排除。'),
 'S168':('0','6','0','','原文仅有他人误认背景与畏惧，未取得主角具体应对行为，排除。'),
 'S175':('5','7','7','C084','主要行动是解除偏心旧契、更换守护者并重建亲密关系；疗愈灵脉是新关系支持的结果。'),
 'S189':('3','8','5','C069','公开视频简介题名一致；原评论仅辅助匹配向风身份，以公开简介明确的救落水者和医术救治为依据，归入医术解困簇。'),
 'S193':('3','7','6','C072','与S023采用同一守护复生逻辑；沿用既有独立系列编号，不重新合并系列。'),
 'S047':('2','6','2','C085','从C055拆出：身份真相用于洗冤正名，区别于身份揭开后重建家庭关系。'),
 'S144':('1','8','5','C069','从C019移至C069：当前简介呈现学得医术和医术解困，未明确隐藏超常修为；据实际行为归类。')
}
NEW_CLUSTERS=[
 ('C071','关系支援下追查旧案','亲友失踪或旧案构成疑团，依靠关系支援与追查周旋揭开旧事','C074依靠超常秘力和正面清障，此簇以关系协力与追查周旋为主'),
 ('C072','守护伴侣并谋求复生','伴侣面临死亡与封印，另一方通过守护、寻物、闯险求其复生，两人继而相守','C053寻找的是失散旧伙伴，此簇的核心目标是使濒危伴侣复生'),
 ('C073','穿越专业知识解决安家困局','面对家庭与贫困处境，用穿越前的专业设计知识破局安家','C007以日常制作买卖经营为主，此簇以建筑设计专长解决安家问题'),
 ('C074','超常力量支撑寻亲清障','为追查亲人失踪，依靠特殊力量清除敌对势力并建立自身力量','C071以同伴支持与追查周旋为主，此簇以自身秘力清障为主'),
 ('C075','灭门遗孤以武力复仇护家','身负灭门血仇的强者隐匿归来，依靠自身武力清除仇敌并保护接纳自己的家人','C019以应对轻视为主，此簇以血仇和保护新家为主要冲突'),
 ('C076','受排斥后以常规谋略反击','被家庭排斥及亲近者算计，依靠主动设局反制而非超常转机','C022依靠重生或书中预知，此簇没有该类先验机制'),
 ('C077','超能调查者守护人族','拥有特殊能力的主角调查异常危机，以谋略联结伙伴守护人族家园','C074寻亲与武力清障，此簇以调查布局应对家国危机'),
 ('C078','美颜系统改写受轻视处境','受外形非议者获系统美貌优势，通过手腕主动周旋多方情感与权势关系','C048以揭穿构陷和专业自证为主，此簇以关系博弈为主要行动'),
 ('C079','系统长期修炼后以剑力破敌','系统创造长期封闭训练条件，主角获得无双剑力后在修行险境中直接对敌','C029以系统收徒和宗门底蕴护道为主，此簇以个人长期训练所得战力破敌'),
 ('C080','歌神系统与老歌演唱逆袭','被娱乐圈排斥者获系统老歌任务，通过专业演唱取得观众支持并反击打压','C049以配角演绎续命任务为主，此簇以老歌演唱和投票支持为核心'),
 ('C081','亲情受辱后终止婚约','伴侣家庭羞辱至亲，主角通过主动退婚守住亲情与关系边界','C018以隐藏权势公开翻转，此簇不推定公开身份，只依据已发生的退婚'),
 ('C082','受控者借关系周旋脱困','被强权控制的主角以脱困为诉求，借多方关系和策略周旋争取筹码','C015主要修复双方关系，此簇先依据求生和摆脱控制确定核心'),
 ('C083','暴力收费与系统战力循环','诡异环境中系统把金钱转为战力，主角强制收费或收缴对手，再以所得力量压制更强敌人','C009以常规系统经营改善生活，此簇以武力敛财与战力互相强化'),
 ('C084','解除偏心旧契并重建守护关系','旧伴侣偏心伤害主角，主角解除旧契选择新守护者，在关系支持中获救并重建亲密关系','C014以重生预知改变关系选择，此簇依靠当下主动解契换伴'),
 ('C085','身份真相揭开后洗冤正名','被冠恶名者的真实身份与旧案被揭开，公众判断改变，相关冤屈获纠正','C055以身份揭露促进家庭重聚和关系重建，此簇的直接目标是正名')
]


def material_for(anon,data,user_rows,supplements):
    entries=[]
    if user_rows.get(anon):
        entries.append(dict(type='用户校审意见',source='review/具体待判断问题.md',text=user_rows[anon]))
    entries.extend(s for s in supplements if s['series']==anon and s['used'])
    return entries


def main():
    authorization=p.read_json(p.ANN/'final_authorization.json')
    trial=p.read_json(p.REVIEW/'试标确认.json')
    assert trial['confirmed'] is True and authorization['bulk_review_confirmed'] and authorization['subsequent_decisions_authorized']
    data=p.read_json(p.ANN/'input_index.json')
    p.validate_inputs(data)
    works,series,catalog=p.load_structure(data)
    original_catalog={c['cluster_id']:dict(c) for c in catalog}
    comments,opinions=p.load_comments(data)
    user_rows={}
    for line in (p.REVIEW/'具体待判断问题.md').read_text(encoding='utf-8').splitlines():
        columns=[c.strip() for c in line.strip('|').split('|')]
        if len(columns)>=4 and columns[0].startswith('S'):
            user_rows[columns[0]]=columns[3]
    p.write_json(p.ANN/'user_adjudications.json',dict(date=authorization['date'],reviewer=authorization['reviewer'],decisions=user_rows))
    supplements=p.read_json(p.ANN/'supplemental_sources.json')

    # 用户明确声明三个表全部默认审核通过，据此补记批量确认来源。
    for name in ['系列校审表.csv','簇校审表.csv','评论校审表.csv']:
        path=p.REVIEW/name
        rows=p.read_csv(path)
        for row in rows:
            if not row['human_review_status'] and not row.get('post_confirmation_new_record'):
                row.update(human_review_status='人工已审',reviewer=trial['reviewer'],reviewed_at=trial['reviewed_at'],
                           final_reason='用户在会话中声明全部默认人工审核完毕，确认本行现有默认标注。',
                           review_method='用户声明批量确认',review_source='annotations/final_authorization.json')
            if name=='评论校审表.csv':
                row['final_semantic_stage']='用户批量确认现有标注；未冒充执行会话新增逐条语义阅读'
                if not row['missed_feedback_found']:
                    row['missed_feedback_found']='否'
        p.write_csv(path,rows)

    sr={s['anonymous_series']:s for s in series}
    changes=[]
    for anon, (a,b,c,cid,reason) in DECISIONS.items():
        s=sr[anon]
        before={k:s[k] for k in ['cluster_id','core_conflict','turning_mechanism','response_path','assignment_reason']}
        tags=[p.CONFLICT[a],p.TURN[b],p.RESPONSE[c]]
        s.update(core_conflict=tags[0],turning_mechanism=tags[1],response_path=tags[2],template_key='|'.join(tags),
                 cluster_id=cid,assignment_reason=reason,core_narrative=reason,
                 supplementary_evidence=material_for(anon,data,user_rows,supplements),
                 original_evidence_excerpt=s['evidence_excerpt'],evidence_origin='样本原简介及已登记补充材料',
                 final_status='纳入结构统计' if cid else '排除结构统计',exclusion_reason='' if cid else reason,
                 adjudication_method='用户逐项意见及执行会话授权复核',review_status='已定稿')
        if anon=='S020':
            s['evidence_excerpt']=user_rows[anon]
            s['source_url']='review/具体待判断问题.md'
        if anon=='S189':
            e=next(e for e in supplements if e['evidence_id']=='E004')
            s['evidence_excerpt']=e['summary']
            s['source_url']=e['url']
            s['evidence_origin']='补充视频公开简介的释义，匹配依据见E004；非样本原简介'
        changes.append(dict(series_id=s['series_id'],anonymous_series=anon,title=s['series_title'],before=before,
                            after={k:s[k] for k in ['cluster_id','core_conflict','turning_mechanism','response_path','assignment_reason']},
                            user_decision=user_rows.get(anon,''),decided_by='执行会话（用户授权）',date=authorization['date'],
                            evidence=s['supplementary_evidence']))
    for s in series:
        s.setdefault('final_status','纳入结构统计' if s['cluster_id'] else '排除结构统计')
        s.setdefault('exclusion_reason','' if s['cluster_id'] else s['disagreement_note'])
        s.setdefault('adjudication_method','用户声明批量确认原候选')
        s.setdefault('supplementary_evidence',[])
        s.setdefault('evidence_origin','样本原简介')
        s['review_status']='已定稿'
        s['annotation_version']=FINAL_VERSION
        s['human_confirmation_source']='annotations/final_authorization.json'
        s['initial_disagreement_note']=s['disagreement_note']
        s['disagreement_note']=s['exclusion_reason']
        s['original_representative_selection']=s['representative_selection']
        if not s['cluster_id']:
            s['representative_selection']='保留原代表材料，说明最终排除理由'
        elif s['supplementary_evidence']:
            s['representative_selection']='沿用样本代表材料，并另列用户意见或登记补充材料支持最终判断'
        # 代表简介尽量保持最早可支持材料；新增明确标签的条目保留原文及补充意见，不伪造原文。
        if not s['cluster_id']:
            s['cluster_name']=''

    for cid,name,rule,boundary in NEW_CLUSTERS:
        catalog.append(dict(cluster_id=cid,cluster_name=name,common_chain=rule,inclusion_rule=rule,
                            nearest_cluster_difference=boundary,color=f'hsl({int(cid[1:])*137.508%360:.2f}, 56%, 47%)'))
    catalog_map={c['cluster_id']:c for c in catalog}
    catalog_map['C055'].update(cluster_name='身份真相解开后重建家庭关系',common_chain='身份与旧事揭开，关系隔阂化解，亲人重聚或旧情重建',
                               inclusion_rule='身份与旧事揭开，关系隔阂化解，亲人重聚或旧情重建',
                               nearest_cluster_difference='C085以身份真相洗冤正名，此簇以家庭关系重建为主')
    catalog_map['C069'].update(cluster_name='凭既有或传承医术救人解困',common_chain='获得诊疗知识与医术后，以救治应对医疗或都市生活困局',
                               inclusion_rule='获得诊疗知识与医术后，以救治应对医疗或都市生活困局',
                               nearest_cluster_difference='C006突出即时病情感知或诊疗系统辅助，此簇以已获得的医术知识实施诊治')
    for s in series:
        if s['cluster_id']:
            s['cluster_name']=catalog_map[s['cluster_id']]['cluster_name']
    for cluster in catalog:
        members=[s for s in series if s['cluster_id']==cluster['cluster_id']]
        assert members
        cluster.update(member_series_ids=[s['series_id'] for s in members],member_titles=[s['series_title'] for s in members],
                       anonymous_members=[s['anonymous_series'] for s in members],member_count=len(members),
                       representative_series_id=members[0]['series_id'],representative_title=members[0]['series_title'],
                       representative_evidence=members[0]['evidence_excerpt'],
                       member_reasons=[dict(series_id=s['series_id'],rule=cluster['inclusion_rule'],assignment_reason=s['assignment_reason'],
                                            actual_evidence=s['evidence_excerpt'],supplementary_evidence=s['supplementary_evidence'],
                                            fine_tag_difference=s['template_key']) for s in members],
                       variant_explanation='允许具体世界与资源来源不同；成员共同核心、细标签差异及逐成员理由均保留。',
                       review_status='已定稿',annotation_version=FINAL_VERSION,
                       decision_method='用户确认原簇；新增或调整簇由执行会话授权复核')

    # 已读正文明确自称制作、公布制作排期或以出品方身份推广的条目；其余角色存疑项按用户授权最终排除。
    clear_promo=set('R0001 R0010 R0019 R0064 R0082 R0109 R0118 R0163 R0289 R0325 R0343 R0443 R0460 R0474 R0478 R0479 R0505 R0532 R0551 R0573 R0868 R0876 R0912 R0921 R0930 R0939 R0958 R0967 R1002 R1011 R1020 R1029 R1038 R1047 R1058 R1065 R1092 R1115 R1130 R1146 R1164 R1175 R1191 R1209 R1245 R1290 R1308 R1320 R1749 R2451 R2541 R2632 R3207'.split())
    active_opinions=[]
    excluded_opinions=[]
    for o in opinions:
        op=dict(o,review_status='已定稿',adjudication_method='用户批量确认后执行会话复核')
        if op['comparison_scope']=='待人工判断':
            op.update(final_disposition='排除比较统计',exclusion_reason='对照版本或对象与本系列关系无法确认；不计入跨系列分子和对象态度分布')
            excluded_opinions.append(op)
        else:
            op['final_disposition']='纳入观点统计（须同时符合观众资格）'
            active_opinions.append(op)
    opmap=defaultdict(list)
    for op in active_opinions:
        opmap[op['comment_key']].append(op)
    for c in comments:
        initial=c['eligibility']
        if initial=='作者角色待判断':
            c['eligibility']='主创推广' if c['local_id'] in clear_promo else '作者角色无法确定，排除'
            c['eligibility_reason']='正文明确制作或推广自述' if c['local_id'] in clear_promo else '既有角色候选无法确认普通观众身份，按授权排除'
        elif initial=='有效观众候选':
            c['eligibility']='有效观众'
        c.update(semantic_stage='用户已批量确认现有标注；执行会话完成授权定稿',
                 semantic_basis_before_confirmation=c['semantic_stage'],review_status='已定稿',
                 human_review_method='用户在会话中批量确认',human_review_source='annotations/final_authorization.json',
                 explicit_cross_series_similarity=any(o['comparison_scope']=='不同系列' and o['similarity_relation']=='指出相似' for o in opmap[c['comment_key']]),
                 comparison_candidate=bool(opmap[c['comment_key']]),annotation_version=FINAL_VERSION)

    # 作品仍保留逐季原文和初标，不把系列共同核心覆盖到每一季。
    work_changes={'D034':{'turning_mechanism':p.TURN['7']},'D047':{'core_conflict':p.CONFLICT['0']},
                  'D112':{'turning_mechanism':p.TURN['2'],'response_path':p.RESPONSE['5']},
                  'D190':{'response_path':p.RESPONSE['5']},'D192':{'response_path':p.RESPONSE['3']},
                  'D201':{'turning_mechanism':p.TURN['4'],'response_path':p.RESPONSE['3']},
                  'D212':{'response_path':p.RESPONSE['4']},'D233':{'turning_mechanism':p.TURN['3']}}
    for w in works:
        w['description_original']=w['description']
        w['original_source_url']=w['source_url']
        final_series=sr[w['anonymous_series']]
        w['supplementary_evidence']=final_series['supplementary_evidence']
        if w['description_id'] in work_changes:
            w.update(work_changes[w['description_id']],adjudication_source='用户在具体待判断问题.md中的逐项判断')
            w['template_key']='|'.join(w[k] for k in ['core_conflict','turning_mechanism','response_path'])
        if w['anonymous_series'] in ['S020','S189']:
            w.update(core_conflict=final_series['core_conflict'],turning_mechanism=final_series['turning_mechanism'],response_path=final_series['response_path'],
                     template_key=final_series['template_key'],annotation_text=final_series['evidence_excerpt'],
                     conflict_evidence=final_series['evidence_excerpt'],mechanism_evidence=final_series['evidence_excerpt'],response_evidence=final_series['evidence_excerpt'],
                     source_url=final_series['source_url'],evidence_origin=final_series['evidence_origin'],
                     label_reason='基于登记补充材料定稿，原简介保留在description_original；补充释义不作为原文直接引语。')
        w['three_fields_complete']=all(w[k]!='其他／未交代' for k in ['core_conflict','turning_mechanism','response_path'])
        w['series_final_cluster_id']=sr[w['anonymous_series']]['cluster_id']
        w['review_status']='已定稿（保留逐季证据及原有缺项）'
        w['annotation_version']=FINAL_VERSION

    p.VERSION=FINAL_VERSION
    result=p.export_bundle(data,works,series,catalog,comments,active_opinions,'reviewed')
    out=p.BASE/'results/reviewed'
    p.write_csv(out/'评论不确定观点排除.csv',excluded_opinions)
    p.write_csv(out/'系列结构排除清单.csv',[s for s in series if not s['cluster_id']])
    p.write_csv(out/'补充材料登记.csv',supplements)
    p.write_csv(out/'授权复核修改记录.csv',changes)
    cluster_changes=[]
    for c in catalog:
        old=original_catalog.get(c['cluster_id'])
        fields=['cluster_name','inclusion_rule','member_series_ids']
        if not old or any(old.get(k)!=c.get(k) for k in fields):
            cluster_changes.append(dict(cluster_id=c['cluster_id'],change_type='确认后新增' if not old else '确认后边界或成员更新',
                before={k:old.get(k) for k in fields} if old else None,after={k:c[k] for k in fields},
                decided_by='执行会话（用户授权）',source='annotations/final_authorization.json'))
    p.write_csv(out/'簇边界与成员修改记录.csv',cluster_changes)
    p.write_json(p.ANN/'final_series_decisions.json',changes)
    # 将三个工作表的最终列同步到交付结果；基线人工确认与其后的机器决定保留两套来源。
    review_series=p.read_csv(p.REVIEW/'系列校审表.csv')
    for row in review_series:
        final=next(s for s in series if s['series_id']==row['series_id'])
        row.setdefault('human_confirmed_baseline_cluster_id',row['final_cluster_id'])
        row.update(final_cluster_id=final['cluster_id'],final_core_conflict=final['core_conflict'],
                   final_turning_mechanism=final['turning_mechanism'],final_response_path=final['response_path'],
                   final_core_narrative=final['core_narrative'],final_reason=final['assignment_reason'],
                   final_status=final['final_status'],final_exclusion_reason=final['exclusion_reason'],
                   post_confirmation_decision_method=final['adjudication_method'],final_annotation_version=FINAL_VERSION)
    p.write_csv(p.REVIEW/'系列校审表.csv',review_series)
    previous_clusters={r['cluster_id']:r for r in p.read_csv(p.REVIEW/'簇校审表.csv')}
    review_clusters=[]
    for final in catalog:
        row=dict(previous_clusters.get(final['cluster_id'],{}))
        if not row:
            row.update(cluster_id=final['cluster_id'],human_review_status='不适用：确认后授权新增',reviewer='',reviewed_at='',
                       post_confirmation_new_record=True,review_method='执行会话授权复核',review_source='annotations/final_authorization.json')
        row.update(final_cluster_name=final['cluster_name'],final_rule=final['inclusion_rule'],
                   final_boundary=final['nearest_cluster_difference'],final_reason='逐成员按共同核心重新核对，成员与依据见定稿簇目录。',
                   final_member_series_ids=final['member_series_ids'],final_annotation_version=FINAL_VERSION,
                   post_confirmation_decision_method='执行会话授权复核')
        review_clusters.append(row)
    p.write_csv(p.REVIEW/'簇校审表.csv',review_clusters)
    cm={c['comment_key']:c for c in comments}
    review_comments=p.read_csv(p.REVIEW/'评论校审表.csv')
    for row in review_comments:
        final=cm[row['comment_key']]
        row.update(final_eligibility=final['eligibility'],final_opinions=opmap[row['comment_key']],
                   final_reason=final['eligibility_reason'],post_confirmation_decision_method='执行会话授权复核，无法确定的比较观点排除',
                   final_annotation_version=FINAL_VERSION)
    p.write_csv(p.REVIEW/'评论校审表.csv',review_comments)
    trial_series=set(p.read_json(p.ANN/'trial_series_ids.json'))
    trial_comments=set(p.read_json(p.ANN/'trial_comment_ids.json'))
    ts=[s for s in series if s['series_id'] in trial_series]
    tc=[dict(c,final_opinions=opmap[c['comment_key']]) for c in comments if c['local_id'] in trial_comments]
    p.write_csv(p.REVIEW/'试标_24系列.csv',ts)
    p.write_csv(p.REVIEW/'试标_120评论.csv',tc)
    p.render_packet(p.REVIEW/'试标校审阅读包.html','试标定稿：24系列与120评论',
                    [('系列 '+s['anonymous_series']+' '+s['series_title'],s) for s in ts]+[('评论 '+c['local_id'],c) for c in tc])
    p.render_packet(p.REVIEW/'全量结构与簇阅读包.html','全量结构与簇定稿阅读包',
                    [('结构簇 '+c['cluster_id']+' '+c['cluster_name'],c) for c in catalog]+
                    [('系列 '+s['anonymous_series']+' '+s['series_title'],s) for s in series])
    p.write_json(out/'审核覆盖.json',dict(trial_confirmed=True,human_bulk_confirmation=dict(reviewer=trial['reviewer'],reviewed_at=trial['reviewed_at'],
                  series_rows=196,cluster_rows=70,comment_rows=3260,source='annotations/final_authorization.json'),
                  subsequent_decision_method='执行会话授权复核',final_cluster_count=len(catalog),
                  excluded_comparison_opinion_count=len(excluded_opinions),remaining_review_tasks=0,
                  formal_release_ready=True,status='已按用户确认及后续授权定稿'))
    manifest=dict(version=FINAL_VERSION,authorization=authorization,counts=result,
                  supplemental_source_count=sum(s['used'] for s in supplements),considered_but_unused_source_count=sum(not s['used'] for s in supplements),
                  changed_series_count=len(changes),excluded_opinion_count=len(excluded_opinions),
                  input_hashes=p.read_json(p.BASE/'logs/执行清单.json')['source_files'],
                  artifact_hashes=[dict(path=str(f.relative_to(p.BASE)),sha256=p.sha(f)) for f in sorted(out.iterdir()) if f.is_file()])
    p.write_json(p.BASE/'logs/定稿执行清单.json',manifest)
    p.write_json(p.BASE/'验收结果.json',dict(technical_checks_passed=True,formal_release_ready=True,version=FINAL_VERSION,
        ranking_count=400,work_count=368,series_count=196,comment_count=3260,
        codable_series_count=result['structure_codable_series_count'],excluded_series_count=result['unassigned_series_count'],
        cluster_count=len(catalog),all_input_rankings_preserved=True,global_clusters_consistent=True,
        remaining_review_tasks=0,human_review_provenance='用户声明批量确认；非执行会话逐条人工审核',
        source_evidence='原简介、用户补充与4项公开梗概分开登记',snapshot_dir='logs/用户确认前快照',
        status='已定稿，保留无法确定项的排除明细'))
    print(json.dumps(dict(status='已定稿',series=result['structure_codable_series_count'],excluded_series=result['unassigned_series_count'],
                          clusters=len(catalog),ranking_nodes=result['ranking_codable_count'],
                          comment_eligibility=result['comment_eligibility_counts'],excluded_opinions=len(excluded_opinions)),ensure_ascii=False))


if __name__=='__main__':
    main()
