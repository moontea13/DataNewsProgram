(() => {
  'use strict';
  const D = window.PREVIEW_DATA;
  const $ = (s) => document.querySelector(s);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct = (n, digits=1) => n == null ? '—' : `${(n*100).toFixed(digits)}%`;
  const shortMonth = (m) => `${Number(m.slice(-2))}月`;
  const series = new Map(D.series.map(s => [s.series_id,s]));
  const clusters = new Map(D.clusters.map(c => [c.cluster_id,c]));
  const works = new Map(D.nodes.map(n => [n.work_id,n.title]));
  const state = {relation:'指出相似',scope:'不同系列',casePage:0,showAll:false};
  const attitudeColors = {'反感重复':'#bd654e','接受或喜爱重复':'#7d9c75','肯定差异':'#7d9c75','褒贬混合':'#cfad70','未表态':'#cbd1c2'};
  let lastFocus = null;
  const dialog = $('#detail-dialog');

  function openDetail(kicker,body) {
    if (!dialog.open) lastFocus=document.activeElement;
    $('#detail-kicker').textContent=kicker;
    $('#detail-content').innerHTML=body;
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop=0;
    document.body.style.overflow='hidden';
  }
  function closeDetail(){dialog.close();}
  dialog.addEventListener('close',()=>{document.body.style.overflow='';lastFocus?.focus();});
  $('#close-dialog').addEventListener('click',closeDetail);
  dialog.addEventListener('click',e=>{if(e.target===dialog)closeDetail();});
  const tags = s => `<div class="detail-tags">${[s.core_conflict,s.turning_mechanism,s.response_path].map(t=>`<span>${esc(t)}</span>`).join('')}</div>`;
  function sourceLink(url){return url?.startsWith('https://')?`<a class="detail-source" href="${esc(url)}" target="_blank" rel="noopener noreferrer">查看材料来源 ↗</a>`:'';}
  function showSeries(id){
    const s=series.get(id);
    const c=clusters.get(s.cluster_id);
    openDetail(`${s.anonymous_series} · ${c?c.cluster_id:'结构已排除'}`,`<h2 id="detail-title">${esc(s.series_title)}</h2>${tags(s)}<div class="detail-chain">${esc(c?c.common_chain:s.exclusion_reason)}</div><div class="detail-label">归入理由</div><p class="detail-evidence">${esc(s.assignment_reason.replaceAll('候选',''))}</p><div class="detail-label">系列代表材料</div><p class="detail-evidence">${esc(s.evidence_excerpt||'原简介为空，补充材料见下方。')}</p><p class="detail-note">材料属性：${esc(s.evidence_origin)}</p>${sourceLink(s.source_url)}${s.supplementary_evidence.length?`<div class="detail-label">补充依据</div>${s.supplementary_evidence.map(e=>`<p class="detail-evidence">${esc(e.summary||e.text||'')}</p>${sourceLink(e.url)}`).join('')}`:''}${c?`<div class="detail-label">所在全局簇</div><button class="outline-button" data-cluster="${c.cluster_id}">${esc(c.cluster_name)} ↗</button>`:''}`);
  }
  function showCluster(id){
    const c=clusters.get(id);
    openDetail(`${c.cluster_id} · ${c.member_count}个独立系列`,`<h2 id="detail-title">${esc(c.cluster_name)}</h2><div class="detail-chain">${esc(c.common_chain)}</div><div class="detail-label">归入规则</div><p class="detail-evidence">${esc(c.inclusion_rule)}</p><div class="detail-label">与近邻簇的区别</div><p class="detail-evidence">${esc(c.nearest_cluster_difference)}</p><div class="detail-label">全部成员 · 点击查看原文</div><ul class="member-list">${c.member_series_ids.map(sid=>{const s=series.get(sid);return `<li><button class="read-case" data-series="${esc(sid)}">${esc(s.series_title)} ↗</button><span class="member-id">${esc(s.anonymous_series)} · ${esc(s.core_conflict)} → ${esc(s.turning_mechanism)} → ${esc(s.response_path)}</span></li>`;}).join('')}</ul>`);
  }
  function showNovelty(month,key){
    const row=D.novelty.find(r=>r.month===month);
    const cfg={work:{label:'首次入榜作品',ids:row.new_work_ids,title:id=>works.get(id)||id},series:{label:'首次入榜系列',ids:row.new_series_ids,title:id=>series.get(id).series_title},cluster:{label:'首次出现结构簇',ids:row.new_cluster_ids,title:id=>clusters.get(id).cluster_name}}[key];
    openDetail(`${shortMonth(month)} · ${cfg.label} · ${cfg.ids.length}项`,`<h2 id="detail-title">${shortMonth(month)}的${cfg.label}</h2><p class="detail-note">${row.baseline?'7月作为观察期基线。':'与此前全部月份累计集合比较，不表示作品或结构在全网首次出现。'}</p><ul class="member-list">${cfg.ids.map(id=>`<li>${key==='work'?esc(cfg.title(id)):`<button class="read-case" data-${key}="${esc(id)}">${esc(cfg.title(id))} ↗</button>`}<span class="member-id">${esc(id)}</span></li>`).join('')}</ul>`);
  }
  function showCase(id){
    const c=filteredCases().find(c=>c.id===id);
    openDetail(`${c.scope} · ${c.relation}`,`<h2 id="detail-title">${esc(c.title)}</h2><div class="detail-label">评论原句</div><p class="detail-evidence">${esc(c.text)}</p><div class="detail-label">对象、态度与对照对象</div><ul class="member-list">${c.opinions.map(o=>`<li>${esc(o.object)} · ${esc(o.attitude)}<span class="member-id">对照对象：${esc(o.comparison_target)}</span></li>`).join('')}</ul>${sourceLink(c.source_url)}<p class="detail-note">点赞仅用于案例排序，比例按评论条数计算。</p>`);
  }
  document.addEventListener('click',e=>{
    const button=e.target.closest('[data-cluster],[data-series],[data-case],[data-novelty]');
    if(!button)return;
    if(button.dataset.cluster)showCluster(button.dataset.cluster);
    else if(button.dataset.series)showSeries(button.dataset.series);
    else if(button.dataset.case)showCase(button.dataset.case);
    else if(button.dataset.novelty)showNovelty(button.dataset.month,button.dataset.novelty);
  });

  function renderOverview(){
    const items=[[D.counts.works,'作品单元','保留季号'],[D.counts.series,'系列单元','跨月统一对应'],[D.counts.clusters,'全局结构簇','覆盖180个系列'],[D.counts.validComments.toLocaleString('en-US'),'有效观众热评','全期统一分析']];
    $('#overview').innerHTML=items.map(([v,t,n])=>`<div class="stat-item"><strong>${v}</strong><span>${t}<small>${n}</small></span></div>`).join('');
    const oct=D.reuse.at(-1);
    $('#hero-reuse').innerHTML=`${(oct.reuse_ratio*100).toFixed(1)}<span>%</span>`;
    $('#hero-reuse-note').textContent=`10月可分簇的新系列中，${oct.reused_series_count} / ${oct.codable_new_series_count} 沿用此前结构。`;
    $('#data-version').textContent=`${D.meta.date} · 定稿数据`;
  }
  function renderRenewal(){
    const kinds=[['work','new_work_count','作品','var(--ink)'],['series','new_series_count','系列','var(--sage)'],['cluster','new_cluster_count','结构簇','var(--coral)']];
    $('#renewal-chart').innerHTML=`<div class="chart-axis">${[0,25,50,75,100].map(v=>`<div class="axis-line" style="--p:${v/120*100}%"><span>${v}</span></div>`).join('')}${D.novelty.map(r=>`<div class="bar-group">${kinds.map(([key,field,label,color])=>`<button class="new-bar" style="--h:${r[field]/120*100}%;--c:${color}" data-novelty="${key}" data-month="${r.month}" data-value="${r[field]}" title="${shortMonth(r.month)}：${r[field]}个首次${label}" aria-label="${shortMonth(r.month)}，${r[field]}个首次出现${label}，点击查看成员"></button>`).join('')}</div>`).join('')}</div><div class="month-axis">${D.novelty.map(r=>`<span>${shortMonth(r.month)}${r.baseline?'<small>观察期基线</small>':''}</span>`).join('')}</div>`;
    $('#reuse-chart').innerHTML=D.reuse.filter(r=>!r.baseline).map(r=>`<div class="reuse-row"><div class="reuse-row-head"><span>${shortMonth(r.month)}</span><strong>${pct(r.reuse_ratio)}</strong></div><div class="reuse-track" role="img" aria-label="${r.reused_series_count}个沿用，${r.new_structure_series_count}个进入当月新结构"><span style="width:${r.reuse_ratio*100}%" title="沿用此前：${r.reused_series_count}个"></span></div><div class="reuse-detail"><span>沿用 ${r.reused_series_count} / 可分簇 ${r.codable_new_series_count}</span><span>另 ${r.unassigned_new_series_count} 个未分簇</span></div></div>`).join('');
  }
  function renderFeedback(){
    const [mention,coverage,equal]=D.commentMetrics;
    $('#mention-rate').innerHTML=`${(mention.ratio*100).toFixed(2)}<span>%</span>`;
    $('#mention-formula').textContent=`${mention.numerator} 条跨系列相似反馈 / ${mention.denominator} 条有效热评`;
    $('#mention-fill').style.width=pct(mention.ratio,6);
    $('#mention-fill').parentElement.setAttribute('aria-label',`真实比例${pct(mention.ratio,2)}，其余未明确提及跨系列相似`);
    $('#feedback-substats').innerHTML=`<div><strong>${pct(coverage.ratio,2)}</strong><p>作品覆盖率<br>${coverage.numerator} / ${coverage.denominator} 个有有效热评的作品</p></div><div><strong>${pct(equal.ratio,2)}</strong><p>系列等权提及率<br>对${equal.denominator}个系列内部提及率取平均</p></div>`;
    renderAttitudes();
  }
  function renderAttitudes(){
    const rows=D.attitudes.filter(r=>r.comparison_scope===state.scope&&r.similarity_relation===state.relation&&r.comment_count>0);
    const objects=[...new Set(rows.map(r=>r.object))].sort((a,b)=>rows.filter(r=>r.object===b).reduce((s,r)=>s+r.comment_count,0)-rows.filter(r=>r.object===a).reduce((s,r)=>s+r.comment_count,0));
    const attitudes=Object.keys(attitudeColors).filter(a=>rows.some(r=>r.attitude===a));
    const largest=Math.max(1,...objects.map(o=>rows.filter(r=>r.object===o).reduce((s,r)=>s+r.comment_count,0)));
    $('#attitude-legend').innerHTML=attitudes.map(a=>`<span><i class="swatch" style="--c:${attitudeColors[a]}"></i>${esc(a)}</span>`).join('');
    $('#attitude-chart').innerHTML=objects.length?objects.map(o=>{const rs=rows.filter(r=>r.object===o),total=rs.reduce((s,r)=>s+r.comment_count,0);return `<div class="attitude-row"><span class="attitude-label">${esc(o)}</span><div class="attitude-track" role="img" aria-label="${esc(o)}：${rs.map(r=>`${r.attitude}${r.comment_count}条`).join('，')}">${attitudes.map(a=>{const r=rs.find(r=>r.attitude===a);return r?`<span class="attitude-part" style="--c:${attitudeColors[a]};width:${r.comment_count/largest*100}%" title="${esc(a)}：${r.comment_count}条；占本行${pct(r.comment_count/total)}"></span>`:'';}).join('')}</div><span class="attitude-count">${total}</span></div>`;}).join(''):'<div class="empty-state">这个范围与关系组合中，没有可计入的对象观点。</div>';
    renderCases();
  }
  function filteredCases(){return D.cases.filter(c=>c.scope===state.scope&&c.relation===state.relation);}
  function renderCases(){
    const all=filteredCases();
    const start=all.length?state.casePage%Math.ceil(all.length/3)*3:0;
    $('#case-title').textContent=`${state.scope==='不同系列'?'跨系列':state.scope}${state.relation==='指出相似'?'相似':'差异'}反馈`;
    $('#next-cases').disabled=all.length<=3;
    $('#comment-cases').innerHTML=all.length?all.slice(start,start+3).map(c=>{const ats=[...new Set(c.opinions.map(o=>o.attitude))];return `<article class="comment-card"><div class="comment-meta"><span>${esc(c.scope)} · ${esc(c.relation)}</span><span class="attitude-tag">${ats.length===1?esc(ats[0]):'多对象评价'}</span></div><blockquote>“${esc(c.text)}”</blockquote><div class="case-bottom"><span class="case-work" title="${esc(c.title)}">${esc(c.title)}</span><button class="read-case" data-case="${esc(c.id)}" aria-label="阅读${esc(c.title)}的完整评论">原句 ↗</button></div></article>`;}).join(''):'<div class="empty-state">没有可展示的原句。</div>';
  }
  $('#next-cases').addEventListener('click',()=>{state.casePage++;renderCases();});
  $('#relation-control').addEventListener('click',e=>{const b=e.target.closest('[data-relation]');if(!b)return;state.relation=b.dataset.relation;state.casePage=0;$('#relation-control').querySelectorAll('button').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});renderAttitudes();});
  $('#scope-select').addEventListener('change',e=>{state.scope=e.target.value;state.casePage=0;renderAttitudes();});
  function renderLibrary(){
    const q=$('#cluster-search').value.trim().toLowerCase(),size=$('#cluster-size').value;
    const found=D.clusters.filter(c=>(size==='all'||(size==='multi'?c.member_count>1:c.member_count===1))&&[c.cluster_id,c.cluster_name,c.common_chain,...c.member_titles].join(' ').toLowerCase().includes(q)).sort((a,b)=>b.member_count-a.member_count||a.cluster_id.localeCompare(b.cluster_id));
    const visible=q||size!=='all'||state.showAll?found:found.slice(0,8);
    $('#cluster-count').textContent=`${found.length}个结构簇 · ${found.reduce((s,c)=>s+c.member_count,0)}个系列`;
    $('#cluster-grid').innerHTML=visible.length?visible.map(c=>`<button class="cluster-card" data-cluster="${c.cluster_id}"><div class="cluster-card-top"><span class="cluster-id"><i class="swatch" style="--c:${c.color}"></i>${c.cluster_id}</span><span class="cluster-count-mark">${c.member_count}个系列 ↗</span></div><h3>${esc(c.cluster_name)}</h3><p>${esc(c.member_titles.slice(0,2).join(' / '))}${c.member_count>2?' 等':''}</p></button>`).join(''):'<div class="empty-state">没有找到匹配的结构簇，可尝试剧名或簇编号。</div>';
    $('#show-all-clusters').hidden=!!q||size!=='all'||found.length<=8;
    $('#show-all-clusters').innerHTML=state.showAll?'收起结构簇 ↑':`展开全部${found.length}个结构簇 ↓`;
  }
  $('#cluster-search').addEventListener('input',renderLibrary);
  $('#cluster-size').addEventListener('change',renderLibrary);
  $('#show-all-clusters').addEventListener('click',()=>{state.showAll=!state.showAll;renderLibrary();});
  $('#excluded-series').innerHTML=D.excludedSeries.map(s=>`<div class="excluded-item"><strong>${esc(s.title)}</strong>${esc(s.reason)}</div>`).join('');
  renderOverview();renderRenewal();renderFeedback();renderLibrary();
})();
