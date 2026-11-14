// Keep the document's window scrolling so the existing sticky charts and Scrollama
// continue to work. Only crossing a chapter boundary becomes a page turn.
export function initPageTurns() {
  const main = document.querySelector('main');
  const hero = main.querySelector('.hero');
  hero.id = 'cover';
  const group = (className, nodes) => {
    const page = document.createElement('div');
    page.className = className;
    nodes[0].before(page);
    page.append(...nodes);
    return page;
  };
  const methods = main.querySelector('#methods');
  const coverMethod = main.querySelector('.cover-findings .method-fold');
  if (coverMethod) methods.append(coverMethod);
  const opening = group('book-opening', [main.querySelector('#opening'), main.querySelector('.governance-opening'), methods]);
  const ending = group('book-ending', [main.querySelector('#ending')]);
  const pages = [hero, opening, ...main.querySelectorAll(':scope > .chapter'), ending];
  const labels = ['扉页', '序 · 进入片场', '一 · 封面', '二 · 故事', '三 · 来源', '四 · 榜单', '五 · 评论', '终 · 下一部故事'];
  const ids = ['cover', 'opening', 'appearance', 'stories', 'origins', 'renewal', 'audience', 'ending'];
  pages.forEach((page, index) => {
    page.classList.add('book-page');
    page.dataset.page = ids[index];
    if (!index) return;
    const footer = document.createElement('div');
    footer.className = 'page-turn-footer';
    footer.innerHTML = `<button data-turn="${index - 1}" class="page-previous"><span aria-hidden="true">←</span> 上一页</button><span class="page-folio"><span>${labels[index]}</span><small>${String(index + 1).padStart(2, '0')} / ${String(pages.length).padStart(2, '0')}</small></span><button data-turn="${index === pages.length - 1 ? 0 : index + 1}" class="page-next">${index === pages.length - 1 ? '回到扉页' : `翻到${labels[index + 1].split(' · ')[1]}`} <span aria-hidden="true">↗</span></button>`;
    page.append(footer);
  });
  // The colophon belongs to the last page, rather than a ninth, unmarked page.
  ending.append(document.querySelector('.site-footer'));
  const nav = document.querySelector('.chapter-nav');
  const navItem = (id, label, color) => `<a href="#${id}" style="--nav-color:${color}" aria-label="${label}"><span class="nav-marker" aria-hidden="true"></span><span class="nav-label">${label}</span></a>`;
  nav.insertAdjacentHTML('afterbegin', navItem('opening', '序', '#9e9484'));
  nav.insertAdjacentHTML('beforeend', navItem('ending', '终', '#9e9484'));

  document.documentElement.classList.add('book-reader');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let current = 0, turning = false, gestureUntil = 0, edgeDelta = 0, edgeTime = 0;
  const bounds = page => {
    const top = page.getBoundingClientRect().top + window.scrollY;
    return { top, bottom: Math.max(top, top + page.offsetHeight - window.innerHeight) };
  };
  const setCurrent = index => {
    current = index;
    document.documentElement.dataset.bookPage = ids[index];
    nav.querySelectorAll('a').forEach(link => {
      const active = link.hash === `#${ids[index]}`;
      link.classList.toggle('current', active);
      if (active) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  const scrollTo = top => window.scrollTo({ top, behavior: 'instant' });
  async function turn(index, { target = null, animate = true, updateHash = true } = {}) {
    if (turning || index < 0 || index >= pages.length) return;
    const previous = current;
    const direction = index < previous ? 'backward' : 'forward';
    turning = true;
    edgeDelta = 0;
    document.documentElement.dataset.pageTurn = direction;
    const update = () => {
      setCurrent(index);
      const range = bounds(pages[index]);
      const targetTop = target ? target.getBoundingClientRect().top + window.scrollY - 90 : range.top;
      scrollTo(Math.max(range.top, Math.min(range.bottom, targetTop)));
      if (updateHash) history.replaceState(null, '', `#${ids[index]}`);
      // Prevent keyboard focus from staying on the previous page's footer.
      const focus = pages[index].querySelector('h1, h2, .opening-index');
      if (focus && animate) { focus.tabIndex = -1; focus.focus({ preventScroll: true }); }
    };
    try {
      if (!animate || reduced.matches || index === previous) update();
      else if (document.startViewTransition) {
        const transition = document.startViewTransition(update);
        await transition.finished;
      } else {
        update();
        const sheet = document.createElement('div');
        sheet.className = `page-turn-sheet ${direction}`;
        sheet.setAttribute('aria-hidden', 'true');
        document.body.append(sheet);
        try {
          await sheet.animate([
            { opacity: 1 },
            { opacity: 0 }
          ], { duration: 380, easing: 'ease-out' }).finished;
        } finally { sheet.remove(); }
      }
    } finally {
      turning = false;
      gestureUntil = performance.now() + 180;
      delete document.documentElement.dataset.pageTurn;
    }
  }
  function openHash(hash, animate = false) {
    let id;
    try { id = decodeURIComponent(hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    const index = id === 'top' ? 0 : pages.findIndex(page => page === target || page.contains(target));
    if (index >= 0) return turn(index, { target: ids.includes(id) || id === 'top' ? null : target, animate, updateHash: animate });
  }
  function nestedScroll(target, delta) {
    for (let node = target instanceof Element ? target : null; node && node !== document.body; node = node.parentElement) {
      if (node.matches('dialog, select, textarea, input, [contenteditable="true"]')) return true;
      if (/auto|scroll/.test(getComputedStyle(node).overflowY) && node.scrollHeight > node.clientHeight + 2 &&
          (delta > 0 ? node.scrollTop + node.clientHeight < node.scrollHeight - 1 : node.scrollTop > 0)) return true;
    }
    return false;
  }
  function scrollPage(delta, event) {
    if (!delta || document.querySelector('dialog[open]') || nestedScroll(event.target, delta)) return;
    const now = performance.now();
    if (turning || now < gestureUntil) {
      event.preventDefault();
      gestureUntil = now + 180;
      return;
    }
    const { top, bottom } = bounds(pages[current]);
    const next = window.scrollY + delta;
    if (next >= top && next <= bottom && bottom > top) { edgeDelta = 0; return; }
    event.preventDefault();
    const forward = delta > 0;
    const edge = forward ? bottom : top;
    if (Math.abs(window.scrollY - edge) > 2) { scrollTo(edge); edgeDelta = 0; return; }
    if (now - edgeTime > 220 || Math.sign(edgeDelta) !== Math.sign(delta)) edgeDelta = 0;
    edgeTime = now;
    edgeDelta += delta;
    if (Math.abs(edgeDelta) >= 36) void turn(current + (forward ? 1 : -1));
  }
  window.addEventListener('wheel', event => {
    if (event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
    const delta = event.deltaY * (event.deltaMode === 1 ? 18 : event.deltaMode === 2 ? innerHeight : 1);
    scrollPage(delta, event);
  }, { passive: false });
  let touch = null, touchUntil = 0;
  window.addEventListener('touchstart', event => {
    touch = event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
    touchUntil = touch ? performance.now() + 1200 : 0;
  }, { passive: true });
  window.addEventListener('touchmove', event => {
    if (!touch || event.touches.length !== 1) return;
    const point = event.touches[0], delta = touch.y - point.clientY;
    touchUntil = performance.now() + 1200;
    if (Math.abs(delta) > Math.abs(touch.x - point.clientX)) scrollPage(delta, event);
    touch = { x: point.clientX, y: point.clientY };
  }, { passive: false });
  window.addEventListener('touchend', () => { touch = null; }, { passive: true });
  window.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey ||
        event.target.closest('input, select, textarea, button, summary, [contenteditable="true"], dialog') || document.querySelector('dialog[open]')) return;
    const delta = ({ ArrowDown: 60, ArrowUp: -60, PageDown: innerHeight * .85, PageUp: -innerHeight * .85, ' ': innerHeight * (event.shiftKey ? -.85 : .85) })[event.key];
    if (delta) {
      scrollPage(delta, event);
      if (!event.defaultPrevented) {
        event.preventDefault();
        const { top, bottom } = bounds(pages[current]);
        scrollTo(Math.max(top, Math.min(bottom, window.scrollY + delta)));
      }
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      scrollTo(bounds(pages[current])[event.key === 'Home' ? 'top' : 'bottom']);
    }
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-turn]');
    if (button) { void turn(Number(button.dataset.turn)); return; }
    const link = event.target.closest('a[href^="#"]');
    if (link && !event.metaKey && !event.ctrlKey && !event.shiftKey) {
      event.preventDefault();
      void openHash(link.hash, true);
    }
  });
  window.addEventListener('hashchange', () => void openHash(location.hash, true));
  let scrollFrame = 0;
  window.addEventListener('scroll', () => {
    if (scrollFrame || turning) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = 0;
      if (turning) return;
      // Native touch inertia can continue after touchend, without touchmove events.
      const range = bounds(pages[current]);
      if (performance.now() < touchUntil && (scrollY < range.top - 2 || scrollY > range.bottom + 2)) {
        const forward = scrollY > range.bottom;
        scrollTo(forward ? range.bottom : range.top);
        if (performance.now() >= gestureUntil) void turn(current + (forward ? 1 : -1));
        return;
      }
      const top = window.scrollY + 2;
      const index = pages.findLastIndex(page => bounds(page).top <= top);
      if (index >= 0 && index !== current) setCurrent(index);
    });
  }, { passive: true });
  setCurrent(0);
  return { openHash };
}
