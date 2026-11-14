import { esc } from './components.js';

export function coverBoardsHTML(D, start=0, count=5) {
  const gallery=new Map(D.gallery.map(row=>[row.series_id,row]));
  const board=(group,index)=>`<section class="cover-board ${index===start?'is-active':''}" id="cover-panel-${group.id}" role="tabpanel" data-board-panel="${index-start}" data-reveal style="--board-tint:${group.color};--stack-position:${index-start};--stack-lean:${[-1.2,.8,-.6,1.1,-.5][index-start]}deg" aria-labelledby="cover-tab-${group.id}" ${index===start?'':'inert aria-hidden="true"'}><div class="board-heading"><span class="board-number">${String(index+1).padStart(2,'0')}</span><h3 id="board-${group.id}">${esc(group.title)}</h3><p>${esc(group.description)}</p><div class="board-cues">${group.cues.map(cue=>`<span>${esc(cue)}</span>`).join('')}</div></div><div class="board-covers">${group.members.map((id,i)=>{const row=gallery.get(id),feature=D.cover_layout.features.find(r=>r.series_id===id);return `<div class="board-cover" style="--reveal-order:${i};--cover-lean:${[-3,1.5,-1,3][i]}deg"><button class="physical-cover" data-series="${id}" aria-label="查看${esc(row.title)}"><img src="./${row.cover}" alt="《${esc(row.title)}》封面" loading="lazy"><span class="cover-spine" aria-hidden="true"></span><svg class="title-region-overlay" viewBox="0 0 ${feature?.width||640} ${feature?.height||915}" aria-hidden="true">${(feature?.title_boxes||[]).map(box=>`<polygon points="${box.polygon.map(p=>p.join(',')).join(' ')}"/>`).join('')}</svg></button><span class="board-cover-title">${esc(row.title)}</span></div>`;}).join('')}</div></section>`;
  return `<div class="cover-boards section-wrap"><div class="cover-boards-opening"><p class="cover-boards-intro">标题的位置、画面的配色、人物的构图。五组封面，五种熟悉的第一眼。</p><button class="annotation-toggle" id="annotation-toggle" aria-pressed="true">隐藏标题区域标记</button></div><p class="reading-note">选一张卡片，展开这一组封面。点击作品，读一读它的故事。</p><div class="cover-board-tabs" role="tablist" aria-label="五组封面案例">${D.cover_groups.groups.slice(start,start+count).map((g,i)=>`<button id="cover-tab-${g.id}" role="tab" data-board-tab="${i}" aria-controls="cover-panel-${g.id}" aria-selected="${i===0}" tabindex="${i===0?0:-1}" style="--tab-tint:${g.color}"><span>${String(start+i+1).padStart(2,'0')}</span><strong>${['暗色双人','暖金古装','西装男女','多人仙侠','暗色仙侠'][start+i]}</strong></button>`).join('')}</div><div class="cover-board-stack">${D.cover_groups.groups.slice(start,start+count).map((g,i)=>board(g,start+i)).join('')}</div></div>`;
}


export function initCoverBoards() {
  document.querySelectorAll('.cover-boards').forEach(root => {
    const tabs = [...root.querySelectorAll('[data-board-tab]')];
    const panels = [...root.querySelectorAll('[data-board-panel]')];
    function select(index, focus = false) {
      tabs.forEach((tab, i) => {
        tab.setAttribute('aria-selected', String(i === index));
        tab.tabIndex = i === index ? 0 : -1;
      });
      panels.forEach((panel, i) => {
        panel.classList.toggle('is-active', i === index);
        panel.inert = i !== index;
        panel.setAttribute('aria-hidden', String(i !== index));
        panel.style.setProperty('--stack-position', (i - index + panels.length) % panels.length);
      });
      const active = panels[index];
      active.classList.remove('is-revealed');
      requestAnimationFrame(() => requestAnimationFrame(() => active.classList.add('is-revealed')));
      if (focus) tabs[index].focus({ preventScroll: true });
    }
    root.addEventListener('click', event => {
      const tab = event.target.closest('[data-board-tab]');
      if (tab) select(Number(tab.dataset.boardTab));
    });
    root.querySelector('.cover-board-tabs').addEventListener('keydown', event => {
      const tab = event.target.closest('[data-board-tab]');
      if (!tab) return;
      const current = Number(tab.dataset.boardTab);
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 :
        event.key === 'ArrowRight' ? (current + 1) % tabs.length :
        event.key === 'ArrowLeft' ? (current - 1 + tabs.length) % tabs.length : -1;
      if (index >= 0) { event.preventDefault(); select(index, true); }
    });
  });
}
