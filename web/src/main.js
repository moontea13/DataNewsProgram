import { governanceHTML, coverOverviewHTML, storyEvidenceHTML, storyFindingsHTML, originOverviewHTML, producerOverviewHTML, adaptationHTML, adaptationRelations, titleMarkup } from './editorial.js';
import * as d3 from './vendor/d3.js';
import { coverBoardsHTML, initCoverBoards } from './cover-boards.js';
import { initMotion } from './motion.js';
import { initPageTurns } from './page-turns.js';
import { exhibitHTML, initExhibits } from './exhibits.js';
import { clusterGrowthHTML, initClusterGrowth } from './cluster-growth.js';
import { esc, pct, month, source, chapter, scrolly, placeholder, barRows } from './components.js';
import { chapters, coverSteps, renewalSteps, feedbackSteps } from './story.js';
import { initScenes, drawHeatmap, kitBar } from './visuals.js';

const $ = selector => document.querySelector(selector);
const names = ['gallery','part45','story','sequels','producers','adaptations','phrases','aigc','audience','governance','title_style','cover_models','cover_layout','cases','metrics','provenance','cover_groups','editorial'];
const D = {};

async function start() {
  await Promise.all(names.map(async name => { if(window.__STORY_DATA__?.[name]){D[name]=window.__STORY_DATA__[name];return;} const response = await fetch(`./data/${name}.json`); if(!response.ok) throw new Error(`无法读取 ${name}`); D[name] = await response.json(); }));
  render();
  const book = initPageTurns();
  initCoverBoards();
  interactions();
  initExhibits(D);
  initClusterGrowth(D.part45);
  initScenes(D, { coverSteps, renewalSteps, feedbackSteps });
  drawHeatmap($('#genre-heatmap'), D.story.genre_reversal_matrix);
  renderGallery(); renderTitles(); renderClusters(); renderFeedback(); renderSeasonCase(); renderMonthly(); renderProducerMatrix();
  initMotion();
  // Resolve deep links after asynchronous content and charts have been inserted.
  if(location.hash) requestAnimationFrame(()=>book.openHash(location.hash));
  window.__storyReady = true;
}

function render() {
  const counts=D.part45.counts;
  const heroItems=[14,35,76,90,109,122,147,43,62,155,23,81].map(i=>D.gallery[i]);
  const top3=D.story.top3_union;
  $('#app').innerHTML=`
    <nav class="chapter-nav floating-chapters" aria-label="章节导航">${chapters.slice(1,-1).map(([id,no],index)=>`<a href="#${id}" aria-label="第${no}章：${({appearance:'封面',stories:'故事',origins:'来源',renewal:'榜单',audience:'评论'})[id]}" style="--nav-color:${['#b86570','#6d8f75','#b79b55','#708795','#9a7e90'][index]}"><span class="nav-marker" aria-hidden="true"></span><span class="nav-label">${({appearance:'封面',stories:'故事',origins:'来源',renewal:'榜单',audience:'评论'})[id]}</span></a>`).join('')}</nav><a class="floating-methods" href="#methods" aria-label="阅读数据与方法"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1m0-15c3-2 6-2 9-1v15c-3-1-6-1-9 1zm0 0v15"/></svg><span>数据与方法</span></a>
    <main id="top">
      <section class="hero" aria-labelledby="story-title"><div class="edition"><span>AI 短剧观察</span><i></i><span>2026 年 7—10 月 · 红果月榜</span></div><p class="hero-pretitle">400 个榜位，究竟有多少不同的故事？</p><h1 id="story-title">换一部，<br>还是<span class="title-red">这一个？<svg viewBox="0 0 500 20" preserveAspectRatio="none" aria-hidden="true"><path d="M3 13Q240 -6 496 12M22 18Q280 6 465 16"/></svg></span></h1><p class="hero-deck">封面在变，剧名在变，榜单也在变。<br>沿着一部短剧的外表，走进它的故事。</p>
      <div class="hero-wall" aria-label="样本作品封面画廊">${heroItems.map((item,i)=>`<button class="hero-poster" data-series="${item.series_id}" style="--tilt:${[-6,3,-3,5,-4,4,2,-5,4,-2,6,-3][i]}deg;--shift:${[26,5,32,0,24,12,32,8,25,0,30,10][i]}px" aria-label="查看${esc(item.title)}"><img src="./${item.cover}" alt="《${esc(item.title)}》封面" ${i<6?'fetchpriority="high"':'loading="lazy"'}><span>${esc(item.genre)}</span></button>`).join('')}</div><div class="hero-bottom"><span>武汉大学 · 新闻安全分析课程作品</span><a href="#opening" class="scroll-down">向下阅读，拆开故事 <span>↓</span></a><span>约 12 分钟阅读</span></div></section>

      <section class="opening section-wrap" id="opening"><div class="opening-index">序<br><span>进入片场</span></div><div class="prose"><p class="drop-cap">打开短剧榜单，选择看起来很多。修仙、重生、穿越、豪门，新的剧名与封面不断出现。但当你点开下一部，会不会又遇到熟悉的人设、熟悉的逆袭，和熟悉的故事走向？</p><p>我们从2026年7—10月的红果月榜出发，把封面、剧名、简介、出品署名和观众热评放在一起，追问：<strong>选择的数量，等于故事的数量吗？</strong></p></div><div class="sample-strip">${[[counts.rankings,'条上榜记录','每月 100 个榜位'],[counts.works,'部分季作品','保留每一季的区别'],[169,'个确认系列','另有27个缺号单元待核'],[counts.validComments.toLocaleString('zh-CN'),'条有效热评','公开页可见热评样本']].map(([value,label,note])=>`<div><strong>${value}</strong><span>${label}</span><small>${note}</small></div>`).join('')}</div>
      <details class="audience-background"><summary>短剧受众规模：不同报告怎样估计？</summary><div class="audience-context">${D.audience.slice(0,2).map(row=>`<div><strong>${esc(row.value)}<small>${esc(row.unit)}</small></strong><span>${esc(row.period.replace('2026-H1','2026年上半年'))} · ${esc(row.measure)}</span><p>${esc(row.value_type)} · ${source(row.source_url,'来源')}</p></div>`).join('')}</div></details></section>
      ${governanceHTML(D)}

      <section class="chapter chapter-appearance" aria-labelledby="appearance-heading">${chapter('appearance','一','先看封面。','把作品摆在一起，比较会更具体。')}
        ${coverBoardsHTML(D)}
        ${coverOverviewHTML(D)}
        <details class="section-wrap supporting-data cover-archive"><summary>逛一逛全部169张封面<span>按题材筛选、找剧名 ＋</span></summary>        <div class="gallery-section"><div class="figure-topline"><span class="eyebrow">封面阅览室</span><span class="small">169 个系列的固定代表封面 · 点击查看作品</span></div><div class="gallery-controls"><div class="filter-pills" id="genre-filter"><button data-genre="全部" class="active" aria-pressed="true">全部题材</button>${['家庭婚恋','玄幻仙侠','都市生活','古代宫廷'].map(g=>`<button data-genre="${g}" aria-pressed="false">${g}</button>`).join('')}</div><label class="search-field"><span aria-hidden="true">⌕</span><input id="gallery-search" type="search" placeholder="找一部剧，或一种故事" aria-label="搜索封面、剧名或简介"></label></div><div class="cover-gallery" id="cover-gallery"></div><div class="gallery-footer"><span id="gallery-count" class="small" aria-live="polite"></span><button class="text-button" id="expand-gallery">展开更多封面 ↓</button></div></div></details>


        <div class="title-lab section-wrap"><div class="split-heading"><div><span class="eyebrow">剧名里的固定句式</span><h3>“谁说……不能……”<br>填空的，可能是不同的人生。</h3></div><div class="inline-stat"><strong>${D.title_style.template_coverage.series_rate.percent.toFixed(2)}<small>%</small></strong><p><strong class="stat-sentence">27个系列，沿用了可识别的命名句式。</strong>在169个代表剧名中，至少与另一系列共享一种具体模板。</p></div></div><div class="template-tabs" id="template-tabs"></div><div id="title-examples" class="title-examples" aria-live="polite"></div><div class="title-explainer"><span><mark>固定句式</mark> <span class="title-variable">填入的内容</span></span><p>颜色标出固定句式，留白部分由不同的人物与情节填入。</p></div></div>
      </section>

      <section class="chapter chapter-stories" aria-labelledby="stories-heading">${chapter('stories','二','再读故事。','把困境、转机与行动，放回简介原文。')}
        <div class="prose chapter-bridge"><p>从封面走进故事。把三部作品的简介摆在一起，看看人物怎样遇到困境、获得转机，又怎样行动。</p></div>
        ${storyEvidenceHTML(D)}
        ${storyFindingsHTML(D)}
        <details class="section-wrap story-archive editorial-detail"><summary><span>继续探索74种故事结构</span><span>结构档案 ＋</span></summary><div class="cluster-section"><div class="split-heading"><div><h3>146个可编码系列，<br>74种共同核心。</h3></div><p>点击分组，可以核对成员、原文和相邻结构的区别。</p></div><div class="cluster-tools"><label class="search-field"><span aria-hidden="true">⌕</span><input id="cluster-search" type="search" placeholder="搜索结构、剧名或关键词" aria-label="搜索故事结构"></label><label>成员数量<select id="cluster-filter"><option value="all">全部结构</option><option value="multi">多个系列共用</option><option value="single">单个系列</option></select></label><span id="cluster-count" aria-live="polite"></span></div><div class="cluster-grid" id="cluster-grid"></div><button class="outline-button" id="expand-clusters">查看全部结构 ↓</button></div></details>
        <details class="section-wrap editorial-detail story-supplement"><summary><span>换一种观察：简介里的词项与月份</span><span>补充统计 ＋</span></summary><div class="detail-body"><div class="heatmap-panel"><h3>各题材里，哪些翻盘表述更常见？</h3><p>色块表示该题材中相应词项的覆盖比例，一部简介可命中多个词项。</p><div id="genre-heatmap"></div></div><p class="supplement-takeaway">“系统、穿越、修炼或传承变强”三类词项，覆盖${top3.numerator} / ${top3.denominator}个有明确翻盘词项的系列（${top3.percent.toFixed(1)}%）。</p><div class="monthly-panel"><h3>各月入榜系列的题材与词项构成</h3><label class="monthly-select">查看题材<select id="monthly-genre">${D.story.genres.map(row=>`<option>${esc(row.label)}</option>`).join('')}</select></label><div class="monthly-comparison" id="monthly-comparison"></div></div><div class="phrase-bars">${barRows(D.phrases.description_phrases.slice(0,8).map(row=>({label:row.phrase,value:row.count})),169,value=>`${value} 个系列`)}</div></div></details>
      </section>

      <section class="chapter chapter-origins" aria-labelledby="origins-heading">${chapter('origins','三','顺着作品，往回找。','续季、出品署名和原著，接在一条线上。')}
        ${originOverviewHTML(D)}
        <div class="section-wrap origin-trace-heading"><span class="eyebrow">再把镜头拉近一部作品</span><h3>续季、署名、原著，<br>每条关系都留下不同的痕迹。</h3><p>沿着同一系列，翻开续季、出品署名和原著三层资料。</p></div>
        ${exhibitHTML('origins')}
        <details class="section-wrap supporting-data origin-archive"><summary>按月份核对一个系列的完整榜位<span>榜位明细 ＋</span></summary><div class="sequel-case"><label class="full-select">查看系列<select id="season-select">${[...D.sequels.series_ranking].slice(0,8).map(row=>`<option value="${row.series_id}">${esc(row.title)}</option>`).join('')}</select></label><div id="season-case"></div></div></details>
        <section class="section-wrap production-panel">${producerOverviewHTML(D)}<details class="editorial-detail"><summary><span>各家署名集中在哪些题材？</span><span>题材分布 ＋</span></summary><div class="detail-body"><div class="producer-matrix" id="producer-matrix"></div><div class="producer-comparison"><h4>同题材、同内容形态的跨系列封面对比</h4><div>${D.producers.comparison.cover.summary.slice(0,2).map(row=>`<span><small>${esc(row.relation)} · ${row.quantiles.n}对</small><strong>${row.quantiles.median.toFixed(3)}</strong><small>DINOv2封面相似度中位数</small></span>`).join('')}</div></div></div></details></section>
        <section class="section-wrap adaptation-panel">${adaptationHTML(D)}</section>
      </section>

      <section class="chapter renewal-chapter" aria-labelledby="renewal-heading">${chapter('renewal','四','热榜在更新，<br>故事却趋于同质','作品、系列、结构簇三个层次探究')}
        ${scrolly('renewal',renewalSteps,`<div class="chart-eyebrow">每月的新作品数量</div><div class="renewal-chart" id="renewal-chart" role="img" aria-label="按作品、系列与结构簇切换的月度新增数量"></div><div class="chart-stage-label" id="renewal-stage">分季作品</div>`,`7月份的数据作为为观察期基线`)}
        ${clusterGrowthHTML()}
        <div class="section-wrap reuse-panel"><div><span class="eyebrow">新系列可能有相似的故事结构</span><h3>10月，30个新系列<br>走进了熟悉的叙事逻辑。</h3><strong class="big-ratio">${(D.part45.reuse.at(-1).reuse_ratio*100).toFixed(1)}<small>%</small></strong></div><div class="reuse-bars">${D.part45.reuse.filter(row=>!row.baseline).map(row=>`<div class="reuse-row"><div><span>${month(row.month)}</span><strong>${pct(row.reuse_ratio)}</strong></div><div class="reuse-track"><i style="width:${row.reuse_ratio*100}%"></i></div><small>沿用此前结构 ${row.reused_series_count} / ${row.codable_new_series_count} 个可分簇新系列</small></div>`).join('')}</div></div>
        ${exhibitHTML('timeline')}

      </section>

      <section class="chapter" aria-labelledby="audience-heading">${chapter('audience','五','评论区提到了“相似”，<br>','相似是结构上的归纳，观众感受体现在评论里。')}
        ${scrolly('feedback',feedbackSteps,`<div class="comment-dot-field" id="comment-dot-field" role="img" aria-label="3049条评论中27条明确提及跨系列相似"></div><div class="feedback-figure-stat"><strong id="feedback-figure-number">3,049</strong><span id="feedback-figure-label">条有效观众热评</span></div>`,'')}
        <div class="section-wrap feedback-panel"><div class="split-heading"><div><h3>重复的对象 × 评价的态度</h3></div></div><div class="feedback-tools"><div class="segmented" id="feedback-relation"><button data-relation="指出相似" class="active" aria-pressed="true">指出相似</button><button data-relation="强调不同" aria-pressed="false">强调不同</button></div><label>比较范围<select id="feedback-scope"><option>不同系列</option><option>同剧内部</option><option>未说明</option></select></label></div><div class="attitude-legend" id="attitude-legend"></div><div id="attitude-chart" aria-live="polite"></div><div class="case-heading"><span class="eyebrow">让原句说话</span><button class="text-button" id="more-comments">再读几条 ↻</button></div><div class="comment-cards" id="comment-cards" aria-live="polite"></div></div>
      </section>

      <section class="ending" id="ending"><div class="ending-mark" aria-hidden="true">终</div><h2>我们想看的，<br>是下一部，<span>还是不一样的一部？</span></h2><div class="prose"><p>封面、剧名、题材、结构，分别给出了不同层次的答案。排版会重复，常见的翻盘机制会再现，新入榜的系列也可能落在熟悉的叙事逻辑里。</p><p>人物、细节与观看感受，也为熟悉的故事留下了变化。观众会识别套路，也会为熟悉配方里的改变留下好评。</p></div><div class="ending-stats">${[['400','条记录','观察的起点'],['85','个结构簇','180个可分簇系列'],['61.2%','10月结构沿用','30 / 49个可分簇新系列']].map(([value,label,note])=>`<div><strong>${value}</strong><span>${label}</span><small>${note}</small></div>`).join('')}</div></section>

      <section class="methods section-wrap" id="methods"><div class="split-heading"><div><span class="eyebrow">报道说明</span><h2>我们怎样展开这次观察</h2></div></div><p class="collection-intro">我们逐条整理四个月的月榜，将同系列续季关联起来，再补充封面、剧名、简介、出品署名、原著线索和公开页热评。从外观到故事，再到生产与观看，拆开这400个榜位。</p><details><summary>样本与计数</summary><p>2026年7—10月红果月榜，每月100条，共400条上榜记录；对应368部分季作品、196个系列单元，其中169个有平台号的确认系列，另27个缺号单元待核。前三章结构分析采用146个有完整编码材料的系列、74种共同核心；第四章按完整榜单的180个可编码系列、85个全局结构簇统计月度变化。7月作为观察期基线，后续月份的“首次出现”与此前观察月份累计集合比较。</p></details><details><summary>封面、剧名与简介</summary><p>封面、剧名与词项分析使用169个固定代表系列。封面展示组固定采用DINOv2中心裁剪特征、相似度0.70；组内每一对均达到该阈值，再逐图核对构图、标题排版和色彩。5组封面案例覆盖17个系列。外观描述结合图像指标与人工观察，简介词项按规则编码，结构标签采用AI辅助、人工校审。</p></details><details><summary>出品、改编与评论</summary><p>出品方以榜单署名品牌计数，联合署名分别保留。原著资料按作品声明、系列报道、候选线索与来源待补分别整理。3,260条公开页热评筛选出3,049条有效观众评论，按评论编号去重；27条明确提及跨系列相似，涉及24部作品，作品覆盖率分母为361部。热评采自公开页面，单条评论可涉及多个比较对象。</p></details><details><summary>来源</summary><div class="source-list">${['33750460','34022517','34223675','34442821'].map((id,i)=>`<a href="https://www.thepaper.cn/newsDetail_forward_${id}" target="_blank" rel="noopener noreferrer">DataEye · ${i+7}月榜单报告 ↗</a>`).join('')}<a href="https://www.nrta.gov.cn/art/2026/11/6/art_114_74410.html" target="_blank" rel="noopener noreferrer">专项治理原文 ↗</a></div></details></section>
    </main><footer class="site-footer"><a href="#top">回到故事开头 ↑</a></footer><dialog id="detail-dialog" aria-labelledby="detail-title"><button class="dialog-close" id="dialog-close" aria-label="关闭详情">×</button><div id="detail-content"></div></dialog>
  `;
  renderAdaptations();
}

const state = {genre:'全部',galleryExpanded:false,template:0,clustersExpanded:false,relation:'指出相似',scope:'不同系列',commentPage:0};
let lastFocus;
function openDialog(body) { lastFocus=document.activeElement;$('#detail-content').innerHTML=body;const dialog=$('#detail-dialog');if(!dialog.open)dialog.showModal();dialog.scrollTop=0;document.body.classList.add('dialog-open'); }
function showSeries(id) {
  const row=D.gallery.find(row=>row.series_id===id), detail=D.part45.series.find(row=>row.series_id===id);
  if(!row&&!detail)return;
  openDialog(`<span class="eyebrow">作品档案 · ${esc(row?.genre || '系列结构')}</span><div class="series-dialog">${row?`<img src="./${row.cover}" alt="${esc(row.title)}封面">`:''}<div><h2 id="detail-title">${esc(row?.title || detail.series_title)}</h2>${row?`<p class="small">${esc(row.genre)} · ${esc(row.producer_brands.join(' / ') || '署名未注明')}</p><p>${esc(row.description)}</p>${source(row.source_url)}`:`<p>${esc(detail.evidence_excerpt)}</p>${source(detail.source_url)}`}</div></div>${detail?.cluster_id?`<div class="dialog-callout"><span class="eyebrow">简介呈现的核心结构</span><h3>${esc(detail.cluster_name)}</h3><p>${esc(detail.core_narrative)}</p><div class="tags">${[detail.core_conflict,detail.turning_mechanism,detail.response_path].map(t=>`<span>${esc(t)}</span>`).join('<i>→</i>')}</div></div>`:''}`);
}
function renderGallery() {
  const query=$('#gallery-search').value.trim();
  const rows=D.gallery.filter(row=>(state.genre==='全部'||row.genre===state.genre)&&`${row.title} ${row.genre} ${row.description}`.includes(query));
  const visible=state.galleryExpanded?rows:rows.slice(0,18);
  $('#cover-gallery').innerHTML=visible.length?visible.map(row=>`<button class="cover-card" data-series="${row.series_id}"><div class="cover-image"><img src="./${row.cover}" alt="《${esc(row.title)}》封面" loading="lazy"><span>查看作品 ↗</span></div><strong>${esc(row.title)}</strong><small>${esc(row.genre)} · ${esc(row.content_type.replace('3D漫','三维漫剧'))}</small></button>`).join(''):'<p class="empty-state">暂时没有找到这部剧，换一个关键词试试。</p>';
  $('#gallery-count').textContent=`当前显示 ${visible.length} / ${rows.length} 个系列`;
  $('#expand-gallery').hidden=rows.length<=18;
  $('#expand-gallery').textContent=state.galleryExpanded?'收起封面 ↑':`展开全部 ${rows.length} 张封面 ↓`;
}
function renderTitles() {
  const templates=D.title_style.templates.filter(row=>row.count>=2).sort((a,b)=>Number(b.label.includes('谁说'))-Number(a.label.includes('谁说'))).slice(0,5);
  $('#template-tabs').innerHTML=templates.map((row,i)=>`<button class="${i===state.template?'active':''}" data-template="${i}" aria-pressed="${i===state.template}">${esc(row.label)}<small>${row.count}个系列</small></button>`).join('');
  const template=templates[state.template];
  const patterns={'谁说…不能…':'谁说【条件／身份】不能【目标】','重生…，…':'重生【处境】， 【新的选择】','…归来：/，…':'【身份】归来， 【后续行动】','…后，我/她/他…':'【事件】后， 【人物的行动】','…，全班/全家/师兄/大佬…':'【事件】， 【群体的反应】'};
  $('#title-examples').innerHTML=`<p class="template-formula">${esc(patterns[template.label]||template.label)}</p><div class="title-example-grid">${template.series_ids.slice(0,4).map(id=>{const row=D.gallery.find(row=>row.series_id===id);return row?`<button data-series="${id}"><span class="title-book physical-cover"><img src="./${row.cover}" alt="${esc(row.title)}的封面" loading="lazy"><span class="cover-spine" aria-hidden="true"></span></span><strong>${titleMarkup(row.title_style||row.title,template.label)}</strong><span class="title-case-link">读作品简介 ↗</span></button>`:'';}).join('')}</div>`;
}
function editorialClusters() {
  const titles=new Map(D.gallery.map(r=>[r.series_id,r.title]));
  return D.editorial.clusters.map(c=>({cluster_id:c.id,cluster_name:c.name,common_chain:c.chain,nearest_cluster_difference:c.boundary,member_series_ids:c.members,member_count:c.count,member_titles:c.members.map(id=>titles.get(id)||id)}));
}

function renderClusters() {
  const query=$('#cluster-search').value.trim().toLowerCase(),filter=$('#cluster-filter').value;
  const rows=editorialClusters().filter(row=>(filter==='all'||(filter==='multi'?row.member_count>1:row.member_count===1))&&`${row.cluster_name} ${row.common_chain} ${row.member_titles.join(' ')}`.toLowerCase().includes(query)).sort((a,b)=>b.member_count-a.member_count);
  const visible=state.clustersExpanded||query||filter!=='all'?rows:rows.slice(0,6);
  $('#cluster-grid').innerHTML=visible.length?visible.map((row,i)=>`<button class="cluster-card" data-cluster="${row.cluster_id}"><span class="cluster-cover-stack" aria-hidden="true">${row.member_series_ids.map(id=>D.gallery.find(item=>item.series_id===id)).filter(Boolean).slice(0,3).map((item,i)=>`<img src="./${item.cover}" alt="" loading="lazy" style="--stack:${i}">`).join('')}</span><span class="cluster-top"><span class="cluster-number">${row.cluster_id.replace('C','结构 ')}</span><span>${row.member_count} 个系列 ↗</span></span><h4>${esc(row.cluster_name)}</h4><p>${esc(row.common_chain)}</p><div class="cluster-members">${esc(row.member_titles.slice(0,2).join(' / '))}${row.member_count>2?' 等':''}</div></button>`).join(''):'<p class="empty-state">没有找到匹配的结构，试试作品名称。</p>';
  $('#cluster-count').textContent=`${rows.length} 个结构 · ${rows.reduce((n,row)=>n+row.member_count,0)} 个系列`;
  $('#expand-clusters').hidden=Boolean(query)||filter!=='all'||rows.length<=6;
  $('#expand-clusters').textContent=state.clustersExpanded?'收起结构 ↑':`查看全部 ${rows.length} 个结构 ↓`;
}
function showCluster(id, editorial) {
  const row=(editorial?editorialClusters():D.part45.clusters).find(row=>row.cluster_id===id);
  openDialog(`<span class="eyebrow">结构档案 · ${row.member_count} 个系列</span><h2 id="detail-title">${esc(row.cluster_name)}</h2><div class="dialog-callout">${esc(row.common_chain)}</div><h4>和相邻结构的区别</h4><p>${esc(row.nearest_cluster_difference)}</p><h4>成员与原文依据</h4><div class="dialog-member-list">${row.member_series_ids.map(id=>{const item=(editorial?D.editorial.semantic:D.part45.series).find(row=>row.series_id===id);return `<details><summary>${esc(item.series_title)}</summary><p>${esc(item.evidence_excerpt || item.core_narrative)}</p><p class="small">${esc(item.evidence_origin)}</p>${source(item.source_url)}</details>`;}).join('')}</div>`);
}
function renderSeasonCase() {
  const id=$('#season-select').value;
  $('#season-case').innerHTML=D.part45.novelty.map(({month:m})=>{const nodes=D.part45.nodes.filter(row=>row.series_id===id&&row.month===m);return `<div class="season-month"><span>${month(m)}</span><div>${nodes.length?nodes.map(row=>`<button data-node="${esc(row.ranking_id)}" title="${esc(row.title)} · 第${row.rank}名" aria-label="查看${esc(row.title)}，第${row.rank}名">${row.rank}</button>`).join(''):'<small>本月未入榜</small>'}</div><small>${nodes.length} 席</small></div>`;}).join('');
}
function renderMonthly() {
  const genre=$('#monthly-genre').value;
  $('#monthly-comparison').innerHTML=D.story.monthly.map(row=>{
    const selected=row.genres.find(item=>item.label===genre),reversal=row.global_top3_reversal_union;
    return `<div><span class="eyebrow">${month(row.month)}</span><div class="monthly-measure"><strong>${selected?.percent?.toFixed(1) ?? '—'}<small>%</small></strong><span>${esc(genre)}<small>${selected?.count ?? 0} / ${row.series_with_description} 个有简介系列</small></span></div><div class="monthly-track"><i style="width:${selected?.percent || 0}%;background:var(--sage)"></i></div><div class="monthly-measure reversal"><strong>${reversal.percent?.toFixed(1) ?? '—'}<small>%</small></strong><span>三类翻盘表述覆盖<small>${reversal.numerator} / ${reversal.denominator} 个有明确词项系列</small></span></div><div class="monthly-track"><i style="width:${reversal.percent || 0}%;background:var(--accent)"></i></div></div>`;
  }).join('');
}
function renderProducerMatrix() {
  const producers=D.producers.ranking.slice(0,6),genres=D.story.genres.filter(row=>row.label!=='未知').slice(0,7);
  $('#producer-matrix').innerHTML=`<table><caption>前6家出品署名的题材分布 · 单位：系列</caption><thead><tr><th scope="col">出品署名</th>${genres.map(row=>`<th scope="col">${esc(row.label)}</th>`).join('')}</tr></thead><tbody>${producers.map(row=>`<tr><th scope="row">${esc(row.brand)}</th>${genres.map(genre=>{const item=D.producers.genre_matrix.find(item=>item.brand===row.brand&&item.genre===genre.label);const count=item?.count || 0;return `<td style="--cell-alpha:${count?Math.min(.85,.12+count*.15):0}" title="${esc(row.brand)} · ${esc(genre.label)}：${count}个系列">${count || '·'}</td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
}
function renderAdaptations() { $('#adaptation-network').innerHTML=adaptationRelations(D); }

const attitudeColors={'反感重复':'#bb4633','接受或喜爱重复':'#628278','肯定差异':'#628278','褒贬混合':'#b28c4d','未表态':'#b3aea3'};
function renderFeedback() {
  const rows=D.part45.attitudes.filter(row=>row.comparison_scope===state.scope&&row.similarity_relation===state.relation&&row.comment_count>0);
  const objects=[...new Set(rows.map(row=>row.object))];
  const attitudes=Object.keys(attitudeColors).filter(a=>rows.some(row=>row.attitude===a));
  const max=Math.max(1,...objects.map(object=>d3.sum(rows.filter(row=>row.object===object),row=>row.comment_count)));
  $('#attitude-legend').innerHTML=attitudes.map(a=>`<span><i style="background:${attitudeColors[a]}"></i>${a}</span>`).join('');
  $('#attitude-chart').innerHTML=objects.length?objects.map(object=>{const items=rows.filter(row=>row.object===object);return `<div class="attitude-row"><span>${esc(object)}</span><div>${items.map(row=>`<i style="width:${row.comment_count/max*100}%;background:${attitudeColors[row.attitude]}" title="${esc(row.attitude)}：${row.comment_count}条">${row.comment_count>2?row.comment_count:''}</i>`).join('')}</div><b>${d3.sum(items,row=>row.comment_count)}</b></div>`;}).join(''):'<p class="empty-state">这一比较范围中没有对应评价记录。</p>';
  const cases=D.part45.cases.filter(row=>row.scope===state.scope&&row.relation===state.relation);
  const page=state.commentPage%Math.max(1,Math.ceil(cases.length/3));
  $('#comment-cards').innerHTML=cases.length?cases.slice(page*3,page*3+3).map(row=>`<article class="comment-card"><div class="comment-top"><span>${esc([...new Set(row.opinions.map(row=>row.attitude))].join(' / '))}</span><span>“</span></div><blockquote>${esc(row.text)}</blockquote><div class="comment-bottom"><span>《${esc(row.title)}》</span><button data-comment="${esc(row.id)}">阅读全文 ↗</button></div></article>`).join(''):'<p class="empty-state">暂无可展示的对应原句。</p>';
  $('#more-comments').disabled=cases.length<=3;
}
function activateButtons(container,button) {container.querySelectorAll('button').forEach(item=>{item.classList.toggle('active',item===button);item.setAttribute('aria-pressed',String(item===button));});}
function interactions() {
  $('#annotation-toggle').addEventListener('click',event=>{const shown=event.currentTarget.getAttribute('aria-pressed')!=='true';document.querySelector('.chapter-appearance').classList.toggle('hide-regions',!shown);event.currentTarget.setAttribute('aria-pressed',String(shown));event.currentTarget.textContent=shown?'隐藏标题区域标记':'显示标题区域标记';});
  document.querySelectorAll('details.supporting-data,details.editorial-detail').forEach(detail=>detail.addEventListener('toggle',()=>{if(detail.open)requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));}));
  $('#dialog-close').addEventListener('click',()=>$('#detail-dialog').close());
  $('#detail-dialog').addEventListener('close',()=>{document.body.classList.remove('dialog-open');lastFocus?.focus();});
  $('#detail-dialog').addEventListener('click',event=>{if(event.target===$('#detail-dialog')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
  document.addEventListener('click',event=>{
    const series=event.target.closest('[data-series]');if(series){showSeries(series.dataset.series);return;}
    const cluster=event.target.closest('[data-cluster]');if(cluster){showCluster(cluster.dataset.cluster,Boolean(cluster.closest('.chapter-stories')));return;}
    const node=event.target.closest('[data-node]');if(node){const row=D.part45.nodes.find(row=>row.ranking_id===node.dataset.node);openDialog(`<span class="eyebrow">${month(row.month)} · 第${row.rank}名</span><h2 id="detail-title">${esc(row.title)}</h2><p>${esc(row.work_description)}</p><div class="dialog-callout">${esc(row.cluster_name || '结构未确定')}</div>${source(row.description_source_url)}`);return;}
    const comment=event.target.closest('[data-comment]');if(comment){const row=D.part45.cases.find(row=>row.id===comment.dataset.comment);openDialog(`<span class="eyebrow">${esc(row.scope)} · ${esc(row.relation)}</span><h2 id="detail-title">《${esc(row.title)}》的观众说</h2><blockquote class="dialog-quote">${esc(row.text)}</blockquote><div class="tags">${row.opinions.map(o=>`<span>${esc(o.object)} · ${esc(o.attitude)}</span>`).join('')}</div><p class="small">比较对象：${esc([...new Set(row.opinions.map(o=>o.comparison_target))].join(' / '))}</p>${source(row.source_url,'核对评论来源')}`);}
  });
  $('#genre-filter').addEventListener('click',event=>{const button=event.target.closest('[data-genre]');if(!button)return;state.genre=button.dataset.genre;activateButtons(event.currentTarget,button);state.galleryExpanded=false;renderGallery();});
  $('#gallery-search').addEventListener('input',renderGallery);
  $('#expand-gallery').addEventListener('click',()=>{state.galleryExpanded=!state.galleryExpanded;renderGallery();});
  $('#template-tabs').addEventListener('click',event=>{const button=event.target.closest('[data-template]');if(button){state.template=+button.dataset.template;renderTitles();}});
  $('#cluster-search').addEventListener('input',renderClusters);$('#cluster-filter').addEventListener('change',renderClusters);
  $('#expand-clusters').addEventListener('click',()=>{state.clustersExpanded=!state.clustersExpanded;renderClusters();});
  $('#season-select').addEventListener('change',renderSeasonCase);
  $('#monthly-genre').addEventListener('change',renderMonthly);
  $('#feedback-relation').addEventListener('click',event=>{const button=event.target.closest('[data-relation]');if(!button)return;state.relation=button.dataset.relation;state.commentPage=0;activateButtons(event.currentTarget,button);renderFeedback();});
  $('#feedback-scope').addEventListener('change',event=>{state.scope=event.target.value;state.commentPage=0;renderFeedback();});
  $('#more-comments').addEventListener('click',()=>{state.commentPage++;renderFeedback();});

}
start().catch(error=>{console.error(error);$('#app').innerHTML=`<div class="load-error"><h1>故事暂时没有展开</h1><p>${esc(error.message)}</p><p>请使用本地预览服务打开网页：在web目录运行 npm run dev。</p><button onclick="location.reload()">重新载入</button></div>`;});
