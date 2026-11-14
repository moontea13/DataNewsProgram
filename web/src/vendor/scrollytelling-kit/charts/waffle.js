import * as d3 from "../../d3.js";
import { fmt, DUR, size, INK, chrome, CATEGORICAL } from "../util.js";
/** Waffle / unit chart — "x of y", "1 in N", or a composition, as 100 (or `cells`) squares.
 *  spec: {format, cells:100, color, unitLabel}
 *  state: {value: ref, total: ref (default 100 → value is a percent), label, sublabel}                       → one filled group
 *       | {parts:[{value: ref, label, color}], total: ref (default sum of parts), sublabel}                    → composition */
export function createWaffle(container, spec, datasets, { resolve }) {
  const el = d3.select(container), svg = el.append("svg"); const ch = chrome(el, svg);
  const g = svg.append("g"), gNum = svg.append("g"); const f = fmt(spec.format);
  return {
    render(state, immediate) {
      const { width, height } = size(container); svg.attr("viewBox", `0 0 ${width} ${height}`); const t = immediate ? 0 : DUR();
      ch.set(state.title ?? spec.title, state.subtitle ?? spec.subtitle);
      const cells = spec.cells || 100, cols = Math.round(Math.sqrt(cells));
      let parts, total;
      if (state.parts) { parts = state.parts.map((p, i) => ({ label: p.label || "", v: resolve(p.value) || 0, color: p.color || CATEGORICAL[i % CATEGORICAL.length] })); total = resolve(state.total) ?? d3.sum(parts, (p) => p.v); }
      else { const v = resolve(state.value) || 0; total = resolve(state.total) ?? 100; parts = [{ label: state.label || "", v, color: spec.color || CATEGORICAL[0] }]; }
      // Allocate the unfilled background as a real remainder category, too.
      // Otherwise a zero numerator receives one filled cell in the upstream
      // single-group case. This local fix preserves a valid zero as zero.
      const remaining = Math.max(0, total - d3.sum(parts, p => p.v));
      const raw = [...parts.map((p) => (p.v / Math.max(1e-9, total)) * cells), remaining / Math.max(1e-9, total) * cells]; let alloc = raw.map(Math.floor); let rem = cells - d3.sum(alloc);
      raw.map((r, i) => [r - Math.floor(r), i]).sort((a, b) => b[0] - a[0]).slice(0, Math.max(0, rem)).forEach(([, i]) => alloc[i]++);
      const owner = []; parts.forEach((p, i) => { for (let k = 0; k < alloc[i]; k++) owner.push(i); }); while (owner.length < cells) owner.push(-1);
      const side = Math.min((height - 200) / cols, (width - 80) / cols, 34), gap = Math.max(2, side * 0.14);
      const gw = cols * side, x0 = (width - gw) / 2, y0 = 100;
      const data = d3.range(cells).map((i) => ({ i, r: Math.floor(i / cols), c: i % cols, o: owner[i] }));
      const sq = g.selectAll("rect").data(data, (d) => d.i);
      sq.enter().append("rect").attr("rx", 2).attr("fill", INK.grid).merge(sq)
        .attr("x", (d) => x0 + d.c * side).attr("y", (d) => y0 + d.r * side).attr("width", side - gap).attr("height", side - gap)
        .transition().duration(t).delay((d) => (immediate ? 0 : d.i * 4)).attr("fill", (d) => (d.o >= 0 ? parts[d.o].color : INK.grid)).attr("opacity", (d) => (d.o >= 0 ? 1 : 0.7));
      sq.exit().remove();
      // numbers / legend under the grid
      const items = parts.map((p, i) => ({ ...p, i, share: p.v / Math.max(1e-9, total) }));
      const ly = y0 + cols * side + 30; const slot = Math.min(260, width / (items.length + 0.5));
      const li = gNum.selectAll("g.n").data(items, (d) => d.i); const en = li.enter().append("g").attr("class", "n");
      en.append("rect").attr("width", 12).attr("height", 12).attr("rx", 2); en.append("text").attr("class", "hero-num").attr("font-size", 26); en.append("text").attr("class", "label");
      const m = en.merge(li); const startX = width / 2 - (items.length * slot) / 2 + 20;
      m.select("rect").attr("x", (d, i) => startX + i * slot).attr("y", ly - 12).attr("fill", (d) => d.color);
      m.select("text.hero-num").attr("x", (d, i) => startX + i * slot + 20).attr("y", ly).text((d) => (state.total || state.parts ? `${f(d.v)}` : f(d.v)) + (state.parts || state.total ? ` · ${d3.format(".0%")(d.share)}` : "%"));
      m.select("text.label").attr("x", (d, i) => startX + i * slot + 20).attr("y", ly + 20).text((d) => d.label);
      li.exit().remove();
      gNum.selectAll("text.sub").data([state.sublabel || ""]).join("text").attr("class", "chart-sub sub").attr("x", width / 2).attr("y", ly + 52).attr("text-anchor", "middle").text((d) => d);
      ch.legend([]);
    }, resize() {}, progress() {},
  };
}
