import * as d3 from './vendor/d3.js';
import { month } from './components.js';

export function clusterGrowthData(data) {
  const firstSeen = new Map();
  data.novelty.forEach((row, index) => row.new_series_ids.forEach(id => firstSeen.set(id, index)));
  const stories = data.series.filter(row => row.cluster_id).map(row => ({ ...row, firstMonth: firstSeen.get(row.series_id) }));
  const groups = data.clusters.map(cluster => {
    const members = stories.filter(row => row.cluster_id === cluster.cluster_id).sort((a, b) => a.firstMonth - b.firstMonth || a.series_id.localeCompare(b.series_id));
    const color = d3.hsl(cluster.color);
    color.s = .43;
    color.l = .46;
    return { ...cluster, members, firstMonth: Math.min(...members.map(row => row.firstMonth)), color: color.formatHex() };
  }).sort((a, b) => a.firstMonth - b.firstMonth || a.cluster_id.localeCompare(b.cluster_id));
  return { groups, stories, months: data.novelty.map(row => row.month) };
}

export function clusterGrowthHTML() {
  return `<section class="cluster-growth section-wrap" id="cluster-growth" aria-labelledby="cluster-growth-heading">
    <div class="cluster-growth-header"><h3 id="cluster-growth-heading">结构簇聚集图</h3><div class="cluster-growth-months" role="group" aria-label="查看月份">${[7, 8, 9, 10].map((value, index) => `<button type="button" data-growth-month="${index}" aria-pressed="${index === 0}">${value}月</button>`).join('')}</div></div>
    <div class="cluster-growth-summary" aria-live="polite"></div>
    <div class="cluster-growth-filters" role="group" aria-label="突出显示新增结构或已有结构"></div>
    <div class="cluster-growth-stage"></div>
  </section>`;
}

export function initClusterGrowth(data) {
  const root = document.getElementById('cluster-growth');
  const model = clusterGrowthData(data);
  const stage = root.querySelector('.cluster-growth-stage');
  const svg = d3.select(stage).append('svg').attr('role', 'group');
  let selectedMonth = 0, filter = 'all';
  let positions = new Map(), chartWidth, chartHeight;
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

  function layout() {
    chartWidth = stage.clientWidth;
    const radius = chartWidth < 600 ? 6 : 8;
    const padding = chartWidth < 600 ? 8 : 13;
    const groups = model.groups.map(group => {
      const points = group.members.map(row => ({ id: row.series_id, r: radius }));
      d3.packSiblings(points);
      return { ...group, r: d3.packEnclose(points).r + padding };
    });
    const rows = [];
    let row = [], used = 0;
    for (const group of groups) {
      if (row.length && used + group.r * 2 + padding > chartWidth - padding * 2) {
        rows.push(row);
        row = [];
        used = 0;
      }
      row.push(group);
      used += group.r * 2 + padding;
    }
    rows.push(row);
    positions = new Map();
    let top = 22;
    for (const items of rows) {
      const height = Math.max(...items.map(group => group.r * 2));
      const width = d3.sum(items, group => group.r * 2) + padding * (items.length - 1);
      let left = (chartWidth - width) / 2;
      for (const group of items) {
        positions.set(group.cluster_id, { x: left + group.r, y: top + height / 2, radius });
        left += group.r * 2 + padding;
      }
      top += height + padding;
    }
    chartHeight = top + 15;
    svg.attr('viewBox', `0 0 ${chartWidth} ${chartHeight}`).attr('width', chartWidth).attr('height', chartHeight);
  }

  function matches(row, group) {
    return filter === 'all' || (row.firstMonth === selectedMonth && (filter === 'new' ? group.firstMonth === selectedMonth : group.firstMonth < selectedMonth));
  }

  function render(animate = true) {
    const visibleGroups = model.groups.filter(group => group.firstMonth <= selectedMonth);
    const visibleStories = model.stories.filter(row => row.firstMonth <= selectedMonth);
    const newClusters = visibleGroups.filter(group => group.firstMonth === selectedMonth).length;
    const reused = visibleGroups.filter(group => group.firstMonth < selectedMonth).reduce((sum, group) => sum + group.members.filter(row => row.firstMonth === selectedMonth).length, 0);
    const duration = animate && !reduced() ? 850 : 0;
    root.querySelector('.cluster-growth-summary').innerHTML = `<span><strong>${visibleStories.length}</strong> 个系列</span><span><strong>${visibleGroups.length}</strong> 个结构簇</span>`;
    root.querySelectorAll('[data-growth-month]').forEach(button => button.setAttribute('aria-pressed', String(+button.dataset.growthMonth === selectedMonth)));
    const filters = [['all', '全部', ''], ['new', '新增结构簇', newClusters], ['reuse', '进入已有簇', reused]];
    root.querySelector('.cluster-growth-filters').innerHTML = filters.map(([key, label, count]) => `<button type="button" data-growth-filter="${key}" aria-pressed="${filter === key}" ${key === 'reuse' && selectedMonth === 0 ? 'disabled' : ''}>${label}${count === '' ? '' : `<b>${count}</b>`}</button>`).join('');
    svg.attr('aria-label', `${month(model.months[selectedMonth])}，累计${visibleStories.length}个独立系列、${visibleGroups.length}个结构簇。每个点是一个系列，同色点属于同一结构簇。`);

    const islands = svg.selectAll('g.growth-island').data(visibleGroups, group => group.cluster_id);
    islands.exit().interrupt().remove();
    const enter = islands.enter().append('g').attr('class', 'growth-island').attr('transform', group => {
      const position = positions.get(group.cluster_id);
      return `translate(${position.x},${position.y})`;
    });
    enter.append('circle').attr('class', 'growth-halo').attr('r', 0);
    enter.merge(islands).each(function(group) {
      const island = d3.select(this);
      const position = positions.get(group.cluster_id);
      island.attr('data-cluster-id', group.cluster_id).classed('is-new-cluster', group.firstMonth === selectedMonth);
      island.interrupt().transition().duration(duration).attr('transform', `translate(${position.x},${position.y})`);
      const members = group.members.filter(row => row.firstMonth <= selectedMonth).map(row => ({ ...row, r: position.radius }));
      d3.packSiblings(members);
      const enclosure = d3.packEnclose(members);
      members.forEach(row => { row.x -= enclosure.x; row.y -= enclosure.y; });
      const highlighted = members.some(row => matches(row, group));
      island.select('.growth-halo').attr('fill', group.color).attr('stroke', group.color).interrupt().transition().duration(duration).attr('r', enclosure.r + 6).attr('opacity', highlighted ? 1 : .18);
      const dots = island.selectAll('circle.growth-dot').data(members, row => row.series_id);
      dots.exit().interrupt().remove();
      const added = dots.enter().append('circle').attr('class', 'growth-dot').attr('r', 0).attr('cx', row => row.x * 1.9).attr('cy', row => row.y * 1.9 - 16).attr('tabindex', 0).attr('role', 'button');
      added.append('title');
      const merged = added.merge(dots).attr('fill', group.color).attr('data-cluster', group.cluster_id).attr('data-series-id', row => row.series_id).attr('data-first-month', row => row.firstMonth).attr('aria-label', row => `${row.series_title}，${group.cluster_name}，查看结构簇`).classed('is-current', row => row.firstMonth === selectedMonth);
      merged.select('title').text(row => `《${row.series_title}》\n${group.cluster_name}\n${group.common_chain}`);
      merged.interrupt().transition().duration(duration).delay(row => duration && row.firstMonth === selectedMonth ? group.firstMonth === selectedMonth ? 150 : 380 : 0).ease(d3.easeCubicOut).attr('cx', row => row.x).attr('cy', row => row.y).attr('r', position.radius).attr('opacity', row => matches(row, group) ? row.firstMonth === selectedMonth ? 1 : .48 : .1);
    });
  }

  root.addEventListener('click', event => {
    const monthButton = event.target.closest('[data-growth-month]');
    const filterButton = event.target.closest('[data-growth-filter]');
    if (monthButton) {
      selectedMonth = +monthButton.dataset.growthMonth;
      filter = 'all';
      render();
    } else if (filterButton) {
      filter = filterButton.dataset.growthFilter;
      render(false);
    }
  });
  root.addEventListener('keydown', event => {
    if (event.target.matches('.growth-dot') && ['Enter', ' '].includes(event.key)) {
      event.preventDefault();
      event.target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }
  });
  layout();
  render(false);
  const resize = new ResizeObserver(() => {
    if (stage.clientWidth !== chartWidth) { layout(); render(false); }
  });
  resize.observe(stage);
  window.addEventListener('pagehide', () => resize.disconnect(), { once: true });
}
