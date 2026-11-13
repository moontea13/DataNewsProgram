"""从当次运行结果生成说明、待判断问题和交付入口。"""
from pipeline import BASE, ANN, REVIEW, read_json, read_csv


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(x).replace('|','／').replace('\n',' ') for x in row)+' |' for row in rows])


def pct(value):
    return '留空' if value in [None,''] else f'{float(value):.2%}'


def main():
    if (ANN/'final_authorization.json').exists():
        import generate_final_docs
        generate_final_docs.main()
        return
    m=read_json(BASE/'logs/执行清单.json')
    preview=BASE/'results/preview'
    metrics=m['preview']['metrics']
    n=metrics['novelty']; reuse=metrics['reuse']
    c3=metrics['feedback']
    layers=read_csv(REVIEW/'未命中抽查分层数量.csv')
    series=read_csv(preview/'系列结构标注.csv')
    groups=read_csv(preview/'分组簇统计.csv')
    comments=read_csv(preview/'评论筛选与标签.csv')
    source=read_json(ANN/'input_index.json')
    native=[c for c in source['comments'] if c['native_comment_id']]
    native_pairs=[(c['source_url'],c['native_comment_id']) for c in native]
    assert len(native_pairs)==len(set(native_pairs)), '存在同来源原始评论编号重复，需先核对'
    text=f'''# 统计方法与结果说明

执行日期：2026-11-13。版本：{m['annotation_version']}。随机种子：20261113。

## 执行状态

已完成输入盘点、24系列与120评论试标、368作品结构初标、196系列候选共同核心、全局候选簇设计、评论全量预筛、校审材料和四项指标复算程序。全量评论语义初标尚未完成：120条已读全文，631条已读比较候选语句，其余2509条仍为预筛待复核；其中2317条属于有效观众候选。试标与人工校审均未确认，因此本次发布候选预览，正式统计未发布。

{table(['项目','数量'],[['上榜记录',400],['作品单元',368],['系列单元',196],['独立简介文本',331],['公开热评',3260],['候选结构簇',m['preview']['cluster_count']],['有候选簇的系列',161],['结构未定或材料不足的系列',35],['有候选簇的榜位',352],['无候选簇的榜位',48],['人工已审系列／簇／评论','0／0／0']])}

所有原始编号、月份、名次和原文保留。输入与冻结快照逐字段核对一致。源文件SHA-256、候选编码文件SHA-256和版本保存在 `logs/执行清单.json`。所有正式交付CSV采用UTF-8 BOM，列表字段为JSON字符串。新文件全部位于ymc45。

## 指标1：观察期三层换新

每月集合与此前所有月份累计集合做差。同作品再次入榜不新增作品；同系列新季不新增系列；同月共用新簇只新增一个结构。7月为基线。

{table(['月份','首次作品','首次系列','首次候选簇','当月可分簇系列','当月未分簇系列'],[[r['month'],r['new_work_count'],r['new_series_count'],r['new_cluster_count'],r['month_codable_series_count'],r['month_unassigned_series_count']] for r in n])}

作品与系列换新数量直接由原始编号计算；结构数量取决于候选簇。各层全部成员编号保存在指标1表的JSON列中。

## 指标2：新系列沿用此前结构

分子是本月首次入榜且进入此前已出现簇的新系列；分母是本月首次入榜且有簇归属的新系列。先同时完成整月判断，再更新累计集合。7月不解释为沿用率。

{table(['月份','沿用数','当月新结构系列数','可分簇新系列','未定新系列','沿用比例'],[[r['month'],r['reused_series_count'],r['new_structure_series_count'],r['codable_new_series_count'],r['unassigned_new_series_count'],pct(r['reuse_ratio'])] for r in reuse])}

明细表为每个新系列保存类别、此前同簇系列编号、双方简介原文与剧名。不存在此前对照的当月新簇，不按同月处理顺序制造先后。

## 指标3：相似反馈提及与覆盖

{table(['筛选资格','评论数'],sorted(m['preview']['comment_eligibility_counts'].items()))}

候选分母3049条，覆盖361个作品、189个系列。原推广候选181条，新增15条正文自述或推广候选；这196条的角色未确认，不进入候选观众分母。未选定版本11条及不可解释内容4条另列。含原始评论编号的记录为{len(native)}条；`comment_key`全表唯一，不按正文相同删评。

{table(['候选指标','分子','分母','预览比例'],[[r['metric'],round(r['numerator'],8),r['denominator'],pct(r['ratio'])] for r in c3])}

系列等权分子为各系列内部提及率之和，分母为有有效候选评论的系列数。27条跨系列相似候选涉及24个作品、23个系列。该提及数来自已处理候选，不能解释为整份热评完成语义标注后的最终数量。

## 指标4：对象与态度

保存222条评论的272条去重对象观点，含跨系列、同系列跨季、同剧内部、范围未说明和待判断五种范围。每条观点保存原句全文、对照对象、范围、关系、态度及来源。一般好评不进入观点主图。

同一评论有多个对象，指标3只计一次，指标4按对象计数。相同评论×对象×范围合并为一个最终态度。`object_share`的分母为该范围、该对象涉及的独立评论数；`valid_comment_share`的分母为有效观众候选评论总数。相似与差异保存在独立关系字段中，可分别筛选。待判断范围不计入跨系列相似分子。

## 人工校审清单

试标系列按首次入榜月份各抽6个，使用固定种子；120评论试标包覆盖普通评价、相似、差异、跨季、剧内和推广候选，是规则校准包，不作为随机意见样本。`code/check_sampling.py`可以复现全部抽样编号。

全审196个系列和70个候选簇；全审相似／差异及角色存疑评论417条；负例抽查如下。

{table(['作品首次入榜月份','未命中候选总数','20%向上取整抽查数'],[[r['work_first_month'],r['negative_population_count'],r['sample_count']] for r in layers])}

分层抽查共567条。出现漏标后整层扩查，脚本自动生成扩查名单。35个未定系列的问题见 `review/具体待判断问题.md`。未完成的全量语义初标需在试标校准后继续；其覆盖状态与人工覆盖分别记录，不混为同一种完成状态。

## 可视化数据接口

`榜单簇归属.csv`一行一个榜位，保留400个节点；`结构簇目录.csv`统一定义全局簇、规则、成员及颜色；`分组簇统计.csv`一行一个月份×分组×簇，含原分组总数、可分簇数与未分簇数。`可视化数据.json`合并节点、目录、分组与四项指标，不在渲染阶段重新分簇。

本次没有制作最终网页。HTML文件是原文与候选标签的校审阅读包。

## 复算与验证

从项目根目录运行 `python ymc45/code/run_all.py`。依赖Python标准库，不需要付费API。复算读取冻结输入快照、原始CSV与保存的候选标注；源数据有变化时逐字段核对会中止，防止把旧标注贴到新内容。

必要场景测试覆盖：跨月重复、同系列新增季、同月多个系列共享新簇、空簇、无分母、差异不进相似分子、剧内相似不进跨系列分子、多对象分子去重、已保存的语义案例与推广候选。

真实数据校验覆盖：主键、关联、月份排名、400节点完整、系列跨月继承、节点总数与簇规模对账、分组比例和为1、比例范围及引用原文存在。技术验收与人工审核状态分别保存在 `验收结果.json`，正式统计发布条件未满足。
'''
    (BASE/'统计方法与结果说明.md').write_text(text,encoding='utf-8')
    unresolved=[s for s in series if not s['cluster_id']]
    questions='# 具体待判断问题\n\n先校审试标，再固定编码规则；当前所有人工审核字段均为空。\n\n'
    questions+=table(['匿名编号','系列','原文与结构分歧'],[[s['anonymous_series'],s['series_title'],s['disagreement_note']] for s in unresolved])
    questions+='''

## 需要确认的共同规则

- 穿书后知晓未来悲剧，是否统一纳入“重生预知”；若拆成新标签，需同步更改作品与系列编码。
- C015的关系修复、C028的师门护持、C055的身份揭露，各成员是否共享同一个主要冲突和应对逻辑；尤其C055中洗冤正名与家人团聚是否应拆开。
- “另一个版本／同IP／真人版”能否根据既有系列映射确定比较范围；无法确定的继续保留待判断。
- R0241是“像斗破苍穹”且期待同样反击；R0206是“与其他剧不同”；R0329是剧内太太撞脸。请确认这三种边界。
- R1830、R1834、R1837比较“五位伙伴寻找”结构，其中存在接受相似的意见；不要把所有相似反馈归为负面。
- 原有181条及新增15条角色候选，哪些是主创推广，哪些是普通观众，哪些仍无法判断。角色未定的记录不直接进入正式观众分母。

修改路径：系列校审表的final_*列；簇校审表的最终规则和边界；评论校审表的final_eligibility、final_opinions及理由。保留原标签和原句，人工字段另列。
'''
    (REVIEW/'具体待判断问题.md').write_text(questions,encoding='utf-8')
    readme='''# ymc45：第4、5部分统计与结构簇标注

本次交付试标、候选标注、四项预览统计、可视化数据及复算代码。正式结果尚未发布：试标待校审，全量评论语义初标仍有未完成记录。

建议先打开：

1. [统计方法与结果说明](统计方法与结果说明.md)：执行状态、四项预览数值和分母。
2. [试标校审阅读包](review/试标校审阅读包.html)：24系列、120条评论的全文与初标。
3. [具体待判断问题](review/具体待判断问题.md)：35个系列及评论边界。
4. [全量结构与簇阅读包](review/全量结构与簇阅读包.html)：全部系列、簇规则和成员原文。

## 文件位置

| 路径 | 内容 |
|---|---|
| code/ | 主流程、抽样复现、必要测试、说明生成、一键运行 |
| annotations/ | 冻结输入索引、人工可审候选编码、匿名编号、试标编号 |
| review/ | 试标材料、三个可填写校审表、全审清单、20%抽查和扩查名单 |
| results/preview/ | 作品／系列结构、簇目录、400榜位归属、评论标签、四项指标、典型案例、可视化JSON |
| results/reviewed/ | 当前只有审核覆盖状态；满足发布条件后写入正式复算结果 |
| logs/ | 输入和标注哈希、版本、执行及测试日志 |

CSV使用UTF-8 BOM，可直接用Excel打开。含多成员或多证据的单元格使用JSON数组。

## 复算

在项目根目录执行：

```powershell
python ymc45/code/run_all.py
```

仅重算数据：`python ymc45/code/pipeline.py`。重算不会覆盖已填写的三个校审表。修改候选标注导致编号或规则变化时，需同步重新校审受影响记录。

## 填写校审

先按[编码手册](编码手册.md)完成试标并填写 `review/试标确认.json`。三个校审表中，人工确认需同时填写 `human_review_status=人工已审`、`reviewer`、`reviewed_at`与`final_reason`。负例抽查还需填写 `missed_feedback_found=是/否`。意见修改写入final_*列，原文及初标列保留。

当前所有人工已审数量均为0。预览表的统计身份写在analysis_status列，不能删除该列后把候选结果称作正式结果。
'''
    (BASE/'README.md').write_text(readme,encoding='utf-8')
    # 校审补充材料：各分组覆盖独立保存，包括完全无法分簇的分组。
    nodes=read_csv(preview/'榜单簇归属.csv')
    coverage=[]
    for month in sorted({r['month'] for r in nodes}):
        for group in ['head','middle','tail']:
            rs=[r for r in nodes if r['month']==month and r['rank_group']==group]
            coverage.append(dict(month=month,rank_group=group,original_ranking_count=len(rs),
                                 codable_count=sum(bool(r['cluster_id']) for r in rs),unassigned_count=sum(not r['cluster_id'] for r in rs)))
    from pipeline import write_csv
    write_csv(preview/'分组覆盖.csv',coverage)
    print('说明、校审问题和目录入口已生成。')


if __name__=='__main__':
    main()
