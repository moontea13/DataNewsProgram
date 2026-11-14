import { esc, source, month } from './components.js';

const percent = rate => rate.percent.toFixed(1);
const fraction = rate => `${rate.numerator} / ${rate.denominator}`;
const metric = (rate, label, description, extra='') => `<article class="finding ${extra}"><strong>${percent(rate)}<span>%</span></strong><h4>${label}</h4><p>${description}</p><span class="finding-count">${fraction(rate)} 个系列</span></article>`;

export function governanceHTML(D) {
  const row=D.governance[0];
  return `<section class="governance-opening section-wrap" aria-labelledby="governance-heading"><div class="governance-date"><span>报道缘起</span><strong>2026.11</strong><p>专项治理启动</p></div><div><h2 id="governance-heading">当“换一部”成为问题</h2><p>2026年11月6日，国家广播电视总局发布的专项治理消息，将“同剧改名反复播出”和“推荐同质化”列为关注的问题。作品不断上新，内容是否也在变得更多样？这是我们展开这次观察的起点。</p><blockquote>“${esc(row.quotes[0].text)}”<br>“${esc(row.quotes[1].text)}”</blockquote><p>我们回到治理开始前的7—10月，拆开红果月榜里的封面、故事与来源，寻找“熟悉感”留下的具体痕迹。</p><div class="reading-note">这是一份治理前的榜单观察，不用于判断治理成效或认定作品违规。${source(row.source_url,'阅读治理原文')}</div></div></section>`;
}

export function coverOverviewHTML(D) {
  const layout=D.cover_layout.close_layout.series_rate,color=D.cover_layout.close_layout_and_color.series_rate;
  const imageCandidate=D.cover_models.variants.dinov2_center.thresholds.find(r=>r.threshold===.50).series_rate;
  return `<section class="section-wrap cover-findings" aria-labelledby="cover-finding-heading"><div class="split-heading"><div><span class="eyebrow">把案例放回全部样本</span><h3 id="cover-finding-heading">熟悉的，是包装的方式。</h3></div><p>标题占据哪里、文字区域呈现什么颜色，与封面图像是否达到设定的相似度阈值，是三个不同的问题。</p></div><div class="findings-grid">${metric(layout,'标题布局接近','至少与另一系列的标题位置、面积和形状接近。')}${metric(color,'布局与区域配色都接近','在布局接近的基础上，文字所在区域的颜色也接近。','featured')}${metric(imageCandidate,'图像相似候选 · 阈值0.50','至少与另一系列的封面达到DINOv2中心裁切余弦相似度 ≥ 0.50。')}</div><p class="reading-note">每个系列只取一张代表封面，同系列续季不互相比。169个系列中，162个能识别有效标题区域，7个未纳入布局统计；区域颜色包含背景，并不等于字体颜色。封面反映采集时材料。</p><details class="method-fold"><summary>这些比例怎样计算？</summary><p>统计至少与一个其他系列满足条件的系列占比，分母为相应有效样本；同系列和已登记的关联疑点配对排除。布局规则：区域交并比 ≥ 0.60；区域颜色余弦相似度 ≥ 0.80。图像相似候选按本页展示阈值0.50计算，148/169个系列命中，共2,794/14,193对有效跨系列配对（19.69%）；系列占比与配对占比不同。0.50是较宽松的探索阈值，不作为通用高相似标准；原预设0.85下为0/169，保留作标准变化的对照。不能与版式比例混用。前面的封面组为从中心裁切相似度 ≥ 0.70 的候选中选出的展示案例，不代表总体比例。</p></details></section>`;
}

// 只标记保存原文中的精确词段，不用标签改写或补造简介。
const storyCases=[
  {id:'HG_7657534299947666494',c:'被裁员又遭分手',t:'意外觉醒“海洋透视”异能',r:'利用异能捕捞极品海鲜'},
  {id:'HG_7660522049697221657',c:'创业失败',t:'获超凡五感与巨力',r:'靠捕捉石蛙、挖掘山货谋生'},
  {id:'HG_7662030523253918744',c:'贫困的农村亲生家庭',t:'意外觉醒了“介虚空间”',r:'带领全村走上科学种植的致富道路'},
];
function markedExcerpt(text, item) {
  const marks=[['c','困境'],['t','转机'],['r','应对']].map(([key,label])=>({start:text.indexOf(item[key]),text:item[key],key,label})).sort((a,b)=>a.start-b.start);
  let cursor=0,html='';
  for(const m of marks){if(m.start<cursor)throw new Error('故事原文证据未定位');html+=esc(text.slice(cursor,m.start))+`<mark class="evidence-${m.key}" title="${m.label}">${esc(m.text)}</mark>`;cursor=m.start+m.text.length;}
  return html+esc(text.slice(cursor));
}

export function storyEvidenceHTML(D) {
  const rows=new Map(D.editorial.semantic.map(r=>[r.series_id,r]));
  const gallery=new Map(D.gallery.map(r=>[r.series_id,r]));
  const cluster=D.editorial.clusters.find(r=>r.id==='C008');
  return `<section class="section-wrap story-evidence" aria-labelledby="evidence-heading"><div class="split-heading"><div><span class="eyebrow">把简介摆在一起</span><h3 id="evidence-heading">人物不同，<br>转机与行动却有熟悉的路径。</h3></div><p>下面三部作品来自同一结构组。颜色标出简介中的原文：先遇到困境，再获得优势，最后用它改善生活。</p></div><div class="evidence-legend"><span class="evidence-c">困境</span><i>→</i><span class="evidence-t">转机</span><i>→</i><span class="evidence-r">应对</span></div><div class="evidence-cards">${storyCases.map(item=>{const row=rows.get(item.id),g=gallery.get(item.id);return `<article class="evidence-card"><header><button data-series="${item.id}" aria-label="查看${esc(row.series_title)}"><img src="./${g.cover}" alt="《${esc(row.series_title)}》封面" loading="lazy"></button><div><h4>${esc(row.series_title)}</h4><p>${esc(g.genre)}</p></div></header><blockquote>${markedExcerpt(row.evidence_excerpt,item)}</blockquote><div class="evidence-fields"><span class="evidence-c">${esc(row.core_conflict)}</span><span class="evidence-t">${esc(row.turning_mechanism)}</span><span class="evidence-r">${esc(row.response_path)}</span></div>${source(row.source_url,'阅读简介来源')}</article>`;}).join('')}</div><div class="shared-chain"><span>共同路径</span><p>${esc(cluster.chain)}</p></div><p class="reading-note">三部作品分别用海洋透视、超凡五感与巨力、灵泉空间推进故事；人物处境与具体经营方式仍然不同。这里展示的是简介中的共同结构，不是正片完全相同。</p></section>`;
}

export function storyFindingsHTML(D) {
  const s=D.editorial.structure;
  return `<section class="section-wrap story-findings"><div class="split-heading"><div><span class="eyebrow">从三部作品，到全部可编码系列</span><h3>常见的转机，<br>也反复出现在其他故事里。</h3></div><p>排除关联疑点和材料不足后，146个系列可用于结构分析，归入74种共同核心。</p></div><div class="story-summary"><div class="story-repeat">${metric(s.repeated_cluster_coverage,'与其他系列共享结构组','109个系列被归入至少有两个成员的共同核心分组。')}</div><div><h4>最常见的三种主导转机</h4><div class="mechanism-bars">${s.top3_mechanisms.map(label=>{const r=s.distributions.turning_mechanism.find(r=>r.label===label);return `<div><span>${esc(label)}</span><div><i style="width:${r.percent}%"></i></div><strong>${r.numerator} / ${r.denominator}</strong></div>`;}).join('')}</div><p class="mechanism-union">合计覆盖 <strong>${percent(s.top3_union)}%</strong> 的可编码系列（${fraction(s.top3_union)}）。</p></div></div><p class="reading-note">共同核心是对简介与已登记补充材料的抽象归类。每个系列的主导转机单选，三类覆盖按系列并集统计；自动归类不代表已测得人工标注准确率。7个关联疑点系列、16个信息不足系列不进入这组主统计。</p></section>`;
}

export function originOverviewHTML(D) {
  return `<section class="section-wrap sequel-overview" aria-labelledby="sequel-heading"><div class="split-heading"><div><span class="eyebrow">先看续作怎样占据榜单</span><h3 id="sequel-heading">100个榜位，<br>并不等于100个不同系列。</h3></div><p>同一系列当月出现k次，留下一个首次占位，其余k−1席计为“额外榜位”。这部分单独统计，不混进跨系列相似度。</p></div><div class="sequel-waffles">${D.sequels.monthly.map(row=>`<article><header><h4>${month(row.month)}</h4><strong>${row.confirmed_extra_slots}<span> / 100席</span></strong></header><div class="slot-grid" role="img" aria-label="${month(row.month)}100个榜位中，确认同系列额外占位${row.confirmed_extra_slots}席，关系待核${row.pending_ranking_rows}席">${Array.from({length:100},(_,i)=>`<i class="${i<row.confirmed_extra_slots?'extra':i>=100-row.pending_ranking_rows?'pending':'first'}"></i>`).join('')}</div><p>确认系列 ${row.known_series} 个<br>关系待核榜位 ${row.pending_ranking_rows} 席</p></article>`).join('')}</div><div class="slot-legend"><span><i class="extra"></i>确认同系列的额外榜位</span><span><i class="first"></i>确认系列的首次占位</span><span><i class="pending"></i>系列关系待核</span></div><div class="origin-takeaway"><strong>8月，57席是同系列的额外占位。</strong><p>这说明该月榜位被同系列续作反复占据；不能据此把续季当成不同作品之间的内容同质化。</p></div></section>`;
}

export function producerOverviewHTML(D) {
  const rate=D.editorial.producer_concentration.find(r=>r.top_k===10);
  return `<div class="producer-overview"><span class="eyebrow">谁在榜单上署名</span><h3>出品品牌，连接着哪些系列？</h3><p>覆盖系列最多的10个署名品牌，合计涉及 <strong>${fraction(rate)} 个系列（${percent(rate)}%）</strong>。联合署名按系列并集统计，不重复累加。</p><div class="producer-editorial-bars">${D.producers.ranking.slice(0,6).map(row=>`<div><span>${esc(row.brand)}</span><div><i style="width:${row.confirmed_series_count/D.producers.ranking[0].confirmed_series_count*100}%"></i></div><strong>${row.confirmed_series_count}个系列</strong></div>`).join('')}</div><p class="reading-note">这里统计榜单上的署名品牌；品牌与企业主体是不同层级。同家出品的可比封面配对仅7对，当前证据不足以判断同家一定更相似。</p></div>`;
}

export function adaptationHTML(D) {
  const distribution=D.adaptations.confirmed_series_distribution;
  const captions=['具体作品直接声明','系列级官方／媒体证据','主创身份待核自述','仅有候选线索','明确原创','来源未知'];
  return `<div class="split-heading"><div><span class="eyebrow">原著与作者</span><h3>有的能追到原著，<br>有的还只是线索。</h3></div><p>我们为169个确认系列逐一登记来源。找到同名书目，与找到直接改编声明，是不同强度的证据。</p></div><div class="adaptation-stack" role="img" aria-label="${distribution.map((r,i)=>`${captions[i]}${r.count}个`).join('，')}">${distribution.filter(r=>r.count).map(r=>`<span class="evidence-level-${distribution.indexOf(r)}" style="flex:${r.count}" title="${esc(r.label)}：${r.count}个系列"></span>`).join('')}</div><div class="adaptation-key">${distribution.map((r,i)=>`<div><i class="evidence-level-${i}"></i><span>${captions[i]}</span><strong>${r.count}<small> / 169</small></strong></div>`).join('')}</div><p class="reading-note">93个系列的来源未知，表示现有材料不足，不能归为原创；系列级改编证据也不能自动外推到每一季。</p><div class="evidence-relations"><h4>一条来源关系，需要怎样的证据？</h4><div class="relation-legend"><span><i class="solid"></i>已找到直接／系列级证据</span><span><i class="dashed"></i>候选关联或身份待核</span></div><div id="adaptation-network"></div></div>`;
}

export function adaptationRelations(D) {
  const nodes=new Map(D.adaptations.nodes.map(r=>[r.id,r]));
  const ids=['HG_7687169040510372888','HG_7624475539960499262','HG_7619198149772446782'];
  const rows=ids.map(id=>{
    const status=D.adaptations.statuses.find(r=>r.series_id===id),e=D.editorial.adaptation_evidence.find(r=>r.series_id===id),book=nodes.get(`book:${status.book_ids[0]}`);
    const confirmed=['具体作品有直接改编声明','系列有官方或媒体改编证据'].includes(status.category);
    return `<article class="relation-evidence ${confirmed?'confirmed':'candidate'}"><div class="relation-path"><span><small>${confirmed?'关联书目':'待核书目线索'}</small>${esc(book?.label||e.book_title)}<small>${esc(e.author)}</small></span><i aria-hidden="true">${confirmed?'→':'⇢'}</i><span><small>${esc(status.category)}</small>${esc(status.title)}</span></div><blockquote>“${esc(e.claim_excerpt)}”</blockquote>${id==='HG_7624475539960499262'?'<p>报道中使用书名《那妖魔是姜大人！》，关联书目页当前题名为《从变身少女开始斩妖除魔》。</p>':''}<p>${confirmed?(e.scope==='具体季'?'该声明对应具体作品，不外推每季。':'该证据支持系列级关系，不外推每季。'):'该线索涉及主创身份待核，目前不作为确认改编。'}</p>${source(e.source_url,'核对关系证据')}${source(e.book_source_url,'查看书目')}</article>`;
  });
  const candidate=D.adaptations.statuses.find(r=>r.confirmed_group&&r.category==='仅候选线索'&&r.book_ids.length);
  if(candidate){const book=nodes.get(`book:${candidate.book_ids[0]}`),edge=D.adaptations.edges.find(r=>r.source===book?.id&&r.target===candidate.series_id);rows.push(`<article class="relation-evidence candidate"><div class="relation-path"><span><small>候选书目</small>${esc(book?.label)}</span><i aria-hidden="true">⇢</i><span><small>第三方候选关联</small>${esc(candidate.title)}</span></div><p>第三方页面留下关联线索，尚无直接改编声明；书目本身存在，也不能证明改编关系成立。</p>${source(edge?.source_url||edge?.source_urls?.[0],'查看候选线索')}</article>`);}
  return rows.join('');
}

export function titleMarkup(title, template) {
  const rules={
    '谁说…不能…':/谁说|不能/g,
    '重生…，…':/重生|[，,]/g,
    '…归来：/，…':/归来|[：:，,]/g,
    '…后，我/她/他…':/后|我|她|他/g,
    '…，全班/全家/师兄/大佬…':/[，,]|全班|全家|师兄们|大佬/g,
  };
  const regex=rules[template];if(!regex)return esc(title);
  let html='',cursor=0;for(const m of title.matchAll(regex)){html+=`<span class="title-variable">${esc(title.slice(cursor,m.index))}</span><mark>${esc(m[0])}</mark>`;cursor=m.index+m[0].length;}
  return html+`<span class="title-variable">${esc(title.slice(cursor))}</span>`;
}
