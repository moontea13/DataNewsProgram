import * as d3 from "d3";
import scrollama from "scrollama";
import { deepMerge, num, where, applyTheme } from "./util.js";
import { FONTS, applyFont } from "./fonts.js";
import { initEditor } from "./editor.js";
import { createNumber } from "./charts/number.js";
import { createArea } from "./charts/area.js";
import { createBar } from "./charts/bar.js";
import { createLine } from "./charts/line.js";
import { createBeeswarm } from "./charts/beeswarm.js";
import { createMap } from "./charts/map.js";
import { createScatter } from "./charts/scatter.js";
import { createSlope } from "./charts/slope.js";
import { createWaffle } from "./charts/waffle.js";
import { createHistogram } from "./charts/histogram.js";

const base = import.meta.env.BASE_URL || "/";
const FACTORIES = { number: createNumber, area: createArea, bar: createBar, line: createLine, beeswarm: createBeeswarm, map: createMap, scatter: createScatter, slope: createSlope, waffle: createWaffle, histogram: createHistogram };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function main() {
  const story = await d3.json(`${base}story.json`);
  document.title = story.title;
  // theme: story.theme = { preset: "dark"|"paper"|"bold", accent, density: "reading"|"presentation", palette? }; ?theme= & ?density= URL params override (used for style previews)
  const q = new URLSearchParams(location.search);
  const saved = (() => { try { return localStorage.getItem("scrolly-theme"); } catch { return null; } })();
  const themeCfg = { ...(story.theme || {}), ...(saved ? { preset: saved } : {}), ...(q.get("theme") ? { preset: q.get("theme") } : {}), ...(q.get("density") ? { density: q.get("density") } : {}), ...(q.get("accent") ? { accent: "#" + q.get("accent").replace("#", "") } : {}) };
  applyTheme(themeCfg);
  const savedFont = (() => { try { return localStorage.getItem("scrolly-font"); } catch { return null; } })();
  applyFont(q.get("font") || savedFont || (story.theme && story.theme.font) || "system");
  // datasets
  const datasets = {};
  await Promise.all(Object.entries(story.data || {}).map(async ([k, f]) => { datasets[k] = await d3.csv(`${base}data/${f}`); }));
  const needsGeo = story.scenes.some((sc) => Object.values(sc.charts || {}).some((c) => c.type === "map"));
  const geo = needsGeo ? await d3.json(`${base}data/${story.geo || "world.geojson"}`) : null;
  // value resolver for number chart: literal, or {data, where, column}, or {data, where, column, agg:"sum"|"max"|"min"|"mean"}
  // {data, where, column, agg} | {op:"sub"|"add"|"mul"|"div"|"sum", args:[refs]} | number
  const resolve = (ref) => { if (ref == null || typeof ref === "number") return ref; if (ref.op) { const a = ref.args.map(resolve); if (ref.op === "sum" || ref.op === "add") return d3.sum(a); if (ref.op === "sub") return a[0] - d3.sum(a.slice(1)); if (ref.op === "mul") return a.reduce((x, y) => x * y, 1); if (ref.op === "div") return a[0] / a[1]; }
    const rows = where(datasets[ref.data], ref.where); const vals = ref.columns ? rows.flatMap((r) => ref.columns.map((c) => num(r[c]))).filter((v) => v != null) : rows.map((r) => num(r[ref.column])).filter((v) => v != null); if (!vals.length) return null; const agg = ref.agg || (ref.columns ? "sum" : "first"); return agg === "sum" ? d3.sum(vals) : agg === "max" ? d3.max(vals) : agg === "min" ? d3.min(vals) : agg === "mean" ? d3.mean(vals) : vals[0]; };

  // ---- build DOM ----
  const app = document.getElementById("app");
  app.insertAdjacentHTML("beforeend", `<header class="hero" id="hero"><div class="hero-dot" aria-hidden="true"></div>${story.kicker ? `<p class="kicker">${esc(story.kicker)}</p>` : ""}<h1>${esc(story.title)}</h1>${story.subtitle ? `<p class="subtitle">${esc(story.subtitle)}</p>` : ""}${story.sourceNote ? `<p class="source-note">${esc(story.sourceNote)}</p>` : ""}<div class="scroll-hint" aria-hidden="true"><span>Scroll</span><i></i></div></header>`);
  const scenes = [];
  story.scenes.forEach((sc, si) => {
    const id = sc.id || `s${si}`;
    const stepsHtml = sc.steps.map((st, i) => { const inner = `${st.heading ? `<h2>${st.heading}</h2>` : ""}${st.text ? `<p>${st.text}</p>` : ""}${st.html || ""}`; return `<div class="step${st.tall ? " step-tall" : ""}" data-step="${i}"><div class="step-inner">${inner}</div></div>`; }).join("");
    app.insertAdjacentHTML("beforeend", `<section class="scrolly" id="scrolly-${id}" data-scrolly="${id}"><figure class="graphic"><div class="chart" id="chart-${id}"></div></figure><div class="steps">${stepsHtml}</div></section>`);
    const container = document.getElementById(`chart-${id}`);
    const charts = {};
    Object.entries(sc.charts).forEach(([name, spec]) => { const layer = document.createElement("div"); layer.className = "chart-layer hidden"; layer.dataset.chart = name; container.appendChild(layer); const make = FACTORIES[spec.type]; if (!make) throw new Error(`Unknown chart type "${spec.type}" in scene ${id}`); charts[name] = { spec, layer, api: make(layer, spec, datasets, { geo, resolve }) }; });
    scenes.push({ id, sc, charts, container, lastShown: null });
  });
  if (story.footerHtml) app.insertAdjacentHTML("beforeend", `<footer class="footer"><h3>${esc(story.footerTitle || "Method & sources")}</h3><div class="footer-body">${story.footerHtml}</div><p class="fine">Built with D3.js and Scrollama. <a href="#hero">Back to top ↑</a></p></footer>`);

  // ---- state resolution: step.state = deepMerge(chart.spec.defaults, previous carried state?) — we merge defaults + step only (idempotent) ----
  function stateFor(scene, stepIndex) {
    const step = scene.sc.steps[stepIndex]; const showName = step.show || Object.keys(scene.charts)[0]; const chart = scene.charts[showName];
    const st = deepMerge(chart.spec.defaults || {}, step.state || {}); st.__index = stepIndex; return { showName, chart, state: st, step };
  }
  function renderStep(scene, stepIndex, immediate) {
    const { showName, chart, state } = stateFor(scene, stepIndex);
    Object.entries(scene.charts).forEach(([n, c]) => c.layer.classList.toggle("hidden", n !== showName));
    chart.api.render(state, immediate); scene.lastShown = showName; scene.lastState = state; scene.lastIndex = stepIndex;
  }
  scenes.forEach((s) => renderStep(s, 0, true));

  // ---- deterministic step control (QA, deep links, background tabs where IntersectionObserver won't fire) ----
  // URL: ?step=<sceneId>:<index>  ·  JS: window.scrolly.goto("a", 3), window.scrolly.list()
  const goto = (sceneId, index, scroll = true) => {
    const scene = scenes.find((s) => s.id === String(sceneId)); if (!scene) return false;
    const steps = document.querySelectorAll(`#scrolly-${scene.id} .step`); const i = Math.max(0, Math.min(steps.length - 1, +index || 0));
    steps.forEach((s) => s.classList.remove("is-active")); steps[i].classList.add("is-active"); renderStep(scene, i, false);
    if (scroll) { const r = steps[i].getBoundingClientRect(); window.scrollTo({ top: r.top + window.scrollY - window.innerHeight * (window.innerWidth < 900 ? 0.56 : 0.55) + 30, behavior: "instant" }); }
    return true;
  };
  window.scrolly = { goto, list: () => scenes.map((s) => ({ scene: s.id, steps: s.sc.steps.length, charts: Object.keys(s.charts) })), scenes };
  if (q.get("step")) { const [sid, idx] = q.get("step").split(":"); setTimeout(() => goto(sid, idx), 300); }

  // ---- inline text editing: on in `npm run dev` (⌘S rewrites public/story.json) or when "editor": true in story.json (downloads story.json). Off on published sites by default. ----
  if (import.meta.env.DEV ? story.editor !== false : story.editor === true) initEditor(story, { start: q.get("edit") === "1" });

  // ---- optional reader-facing theme switcher: "themeSwitcher": true in story.json ----
  if (story.themeSwitcher) {
    const names = { dark: "Dark", paper: "Paper", bold: "Bold" };
    const sw = document.createElement("div"); sw.className = "theme-switcher"; sw.setAttribute("role", "group"); sw.setAttribute("aria-label", "Colour theme");
    sw.innerHTML = Object.entries(names).map(([k, v]) => `<button type="button" data-t="${k}" aria-pressed="${document.documentElement.dataset.theme === k}">${v}</button>`).join("")
      + `<select aria-label="Font">${FONTS.map((f) => `<option value="${f.id}" ${document.documentElement.dataset.font === f.id ? "selected" : ""}>${f.label}</option>`).join("")}</select>`;
    document.body.appendChild(sw);
    sw.querySelector("select").addEventListener("change", (e) => { const id = applyFont(e.target.value); try { localStorage.setItem("scrolly-font", id); } catch {} });
    sw.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-t]"); if (!b) return;
      const preset = b.dataset.t; try { localStorage.setItem("scrolly-theme", preset); } catch {}
      applyTheme({ ...(story.theme || {}), preset });
      sw.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x.dataset.t === preset));
      scenes.forEach((s) => { const { chart, state } = stateFor(s, s.lastIndex || 0); chart.api.render(state, true); });
    });
  }

  const scrollers = [];
  scenes.forEach((scene) => {
    const steps = document.querySelectorAll(`#scrolly-${scene.id} .step`);
    const scroller = scrollama();
    scroller.setup({ step: steps, offset: window.innerWidth < 900 ? 0.56 : 0.55, progress: true })
      .onStepEnter(({ element, index }) => { steps.forEach((s) => s.classList.remove("is-active")); element.classList.add("is-active"); renderStep(scene, index, false); })
      .onStepExit(({ index, direction }) => { if (index === 0 && direction === "up") renderStep(scene, 0, false); })
      .onStepProgress(({ index, progress }) => { const st = scene.sc.steps[index]; if (st && st.state && (st.state.scrub) && scene.lastIndex === index) { const { chart } = stateFor(scene, index); chart.api.progress(progress); } });
    scrollers.push(scroller);
  });
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { scenes.forEach((s) => { const { chart, state } = stateFor(s, s.lastIndex || 0); chart.api.render(state, true); }); scrollers.forEach((s) => s.resize()); }, 150); });
}
main().catch((e) => { console.error(e); document.body.insertAdjacentHTML("afterbegin", `<pre style="color:#f88;padding:1rem;white-space:pre-wrap">Story failed to load: ${e.message}</pre>`); });
