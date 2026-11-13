export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const pct = (value, digits = 1) => value == null ? '—' : `${(value * 100).toFixed(digits)}%`;
export const month = value => `${Number(value.slice(-2))}月`;
export const source = (url, label = '查看原始材料') => /^https?:\/\//.test(url || '') ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>` : '';
export function chapter(id, no, title, lead) {
  return `<header class="chapter-heading" id="${id}"><div class="chapter-kicker"><span>第${no}章</span><i></i><span>AI短剧观察</span></div><h2 id="${id}-heading">${title}</h2><p>${lead}</p></header>`;
}
export function scrolly(id, steps, graphic, caption) {
  return `<div class="scrolly" id="scrolly-${id}" data-scrolly="${id}"><figure class="graphic"><div class="scene-frame">${graphic}<div class="scene-dots" aria-label="图表步骤">${steps.map((step,i)=>`<button data-scene="${id}" data-index="${i}" aria-label="${esc(step.label)}" aria-pressed="${i===0}" class="${i===0?'active':''}"><span>${String(i+1).padStart(2,'0')}</span></button>`).join('')}</div></div><figcaption>${caption}</figcaption></figure><div class="steps">${steps.map((step,i)=>`<article class="step" data-step="${i}"><div class="step-inner"><span class="step-index">${String(i+1).padStart(2,'0')} / ${String(steps.length).padStart(2,'0')}</span><h3>${step.heading}</h3><p>${step.text}</p><span class="step-cue">${step.label} <span aria-hidden="true">↓</span></span></div></article>`).join('')}</div></div>`;
}
export function placeholder(title, description, label = '待补材料') {
  return `<div class="placeholder"><span class="status-label">${label}</span><div class="placeholder-drawing" aria-hidden="true"><i></i><i></i><i></i><i></i></div><h4>${title}</h4><p>${description}</p></div>`;
}
export function barRows(rows, max, format = value => `${value}`) {
  return rows.map((row,i)=>`<div class="bar-row"><span>${esc(row.label)}</span><div class="bar-track"><i style="width:${Math.max(0,Math.min(100,row.value/max*100))}%;--bar-color:${row.color || (i===0?'var(--accent)':'var(--sage)')}"></i></div><b>${format(row.value)}</b></div>`).join('');
}
