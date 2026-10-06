"use strict";

// ---------- 월별 지출 그래프 ----------
// 최근 12개월을 누적 막대로 보여준다. 결제수단(카드별/현금·기타) 또는 카테고리로 나눠 볼 수 있다.
const CHART_MONTHS = 12;
const CHART_MODE_KEY = `${PROFILE.keyPrefix}.chartMode.v1`;
// 카테고리 색은 순위가 아니라 카테고리에 고정 (달을 옮겨도 색이 바뀌지 않게)
const CHART_CATS = PROFILE.chartCats;
const CHART_OTHER = "그 외";
const SVG_NS = "http://www.w3.org/2000/svg";

const chartState = {
  mode: (() => { try { return localStorage.getItem(CHART_MODE_KEY) || "method"; } catch { return "method"; } })(),
  table: false,
};

function chartSeries() {
  if (chartState.mode === "category") {
    return [...CHART_CATS, CHART_OTHER].map((name, i) => ({ key: name, name, color: `var(--s${i + 1})` }));
  }
  return [...PROFILE.cards, "현금·기타"].map((name, i) => ({ key: i < PROFILE.cards.length ? name : "cash", name, color: `var(--s${i + 1})` }));
}

function seriesKeyOf(t) {
  if (chartState.mode === "category") return CHART_CATS.includes(t.category) ? t.category : CHART_OTHER;
  return isCard(t) ? t.method : "cash";
}

// 보고 있는 달과 이번 달 중 늦은 달까지 12개월 (지난달을 눌러도 그래프가 밀리지 않게)
function chartMonths() {
  const now = new Date();
  const end = new Date(state.year, state.month, 1) > now ? new Date(state.year, state.month, 1) : new Date(now.getFullYear(), now.getMonth(), 1);
  const months = [];
  for (let i = CHART_MONTHS - 1; i >= 0; i--) {
    const d = new Date(end.getFullYear(), end.getMonth() - i, 1);
    months.push({ y: d.getFullYear(), m: d.getMonth(), ym: ymOf(d.getFullYear(), d.getMonth()), values: {}, cats: {}, total: 0, count: 0 });
  }
  const byYm = new Map(months.map((mo) => [mo.ym, mo]));
  for (const t of state.tx) {
    const mo = byYm.get(t.date.slice(0, 7));
    if (!mo) continue;
    const k = seriesKeyOf(t);
    mo.values[k] = (mo.values[k] || 0) + t.amount;
    mo.cats[t.category] = (mo.cats[t.category] || 0) + t.amount;
    mo.total += t.amount;
    mo.count++;
  }
  return months;
}

// 눈금: 0 / 10만 / 20만 처럼 깔끔한 값
function niceScale(maxValue) {
  if (maxValue <= 0) return { step: 10000, max: 40000 };
  const raw = maxValue / 4;
  const p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * p).find((s) => s >= raw);
  return { step, max: Math.ceil(maxValue / step) * step };
}
function axisWon(n) {
  if (Math.abs(n) >= 10000) return `${+(n / 10000).toFixed(1)}만`;
  return n.toLocaleString("ko-KR");
}

function svgEl(tag, attrs, parent) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}

// 위쪽만 4px 둥근 막대 (바닥은 각지게)
function columnPath(x, yTop, w, yBottom, r) {
  const h = yBottom - yTop;
  r = Math.min(r, h, w / 2);
  if (r <= 0) return `M${x},${yBottom}V${yTop}H${x + w}V${yBottom}Z`;
  return `M${x},${yBottom}V${yTop + r}Q${x},${yTop} ${x + r},${yTop}H${x + w - r}Q${x + w},${yTop} ${x + w},${yTop + r}V${yBottom}Z`;
}

function renderChart() {
  const wrap = $("#chart");
  if (!wrap) return;
  const months = chartMonths();
  const series = chartSeries();
  const selectedYm = ymOf(state.year, state.month);
  const used = series.filter((s) => months.some((mo) => mo.values[s.key]));

  $$(".seg-btn").forEach((b) => b.classList.toggle("active", b.dataset.mode === chartState.mode));
  renderChartNote(months);
  renderChartLegend(used.length ? used : series);
  renderChartTable(months, used.length ? used : series);

  wrap.replaceChildren();
  if (!months.some((mo) => mo.count)) {
    const empty = document.createElement("p");
    empty.className = "chart-empty";
    empty.textContent = "최근 12개월 기록이 아직 없어요";
    wrap.appendChild(empty);
    return;
  }

  const W = Math.max(280, wrap.clientWidth);
  const H = W < 500 ? 190 : 220;
  const M = { top: 22, right: 4, bottom: 24, left: 40 };
  const plotW = W - M.left - M.right;
  const plotH = H - M.top - M.bottom;
  const GAP = 2;

  // 마이너스(취소가 더 많은 달)는 막대로 그리지 않고 툴팁·표에만 보여준다
  const stackTop = (mo) => series.reduce((s, ser) => s + Math.max(0, mo.values[ser.key] || 0), 0);
  const { step, max } = niceScale(Math.max(...months.map(stackTop)));
  const y = (v) => M.top + plotH - (v / max) * plotH;
  const band = plotW / months.length;
  const colW = Math.min(24, band * 0.6);

  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "group", "aria-label": "월별 지출 막대 그래프" }, wrap);

  // 눈금선과 y축 값
  for (let v = 0; v <= max + 1e-6; v += step) {
    svgEl("line", { x1: M.left, x2: W - M.right, y1: y(v), y2: y(v), class: v === 0 ? "chart-base" : "chart-grid" }, svg);
    const t = svgEl("text", { x: M.left - 6, y: y(v), class: "chart-tick", "text-anchor": "end", "dominant-baseline": "middle" }, svg);
    t.textContent = axisWon(v);
  }

  months.forEach((mo, i) => {
    const cx = M.left + band * i + band / 2;
    const x = cx - colW / 2;
    const g = svgEl("g", { class: `chart-col${mo.ym === selectedYm ? " selected" : ""}` }, svg);

    // 아래부터 쌓고, 조각 사이에 2px 틈
    const segs = series.map((ser) => ({ ser, v: Math.max(0, mo.values[ser.key] || 0) })).filter((s) => s.v > 0);
    let acc = 0;
    segs.forEach((s, j) => {
      const yBottom = y(acc) - (j > 0 ? GAP : 0);
      acc += s.v;
      const yTop = y(acc);
      if (yBottom - yTop < 0.5) return;
      svgEl("path", { d: columnPath(x, yTop, colW, yBottom, j === segs.length - 1 ? 4 : 0), fill: s.ser.color }, g);
    });

    // 월 이름 (1월에는 연도도)
    const label = svgEl("text", { x: cx, y: H - 8, class: "chart-month", "text-anchor": "middle" }, svg);
    label.textContent = mo.m === 0 && W >= 500 ? `${String(mo.y).slice(2)}년 1월` : `${mo.m + 1}월`;
    if (mo.ym === selectedYm) label.classList.add("selected");

    // 보고 있는 달만 합계를 막대 위에 표시
    if (mo.ym === selectedYm && mo.count) {
      const v = svgEl("text", { x: cx, y: y(stackTop(mo)) - 6, class: "chart-value", "text-anchor": "middle" }, svg);
      v.textContent = axisWon(mo.total);
    }

    // 막대보다 넓은 투명 영역이 마우스·터치·키보드 대상
    const hit = svgEl("rect", {
      x: M.left + band * i, y: M.top, width: band, height: plotH, class: "chart-hit", tabindex: 0,
      role: "button", "aria-label": `${mo.y}년 ${mo.m + 1}월 ${won(mo.total)}`,
    }, svg);
    const show = () => { svg.classList.add("hovering"); g.classList.add("active"); showChartTip(wrap, mo, series, cx); };
    const hide = () => { svg.classList.remove("hovering"); g.classList.remove("active"); hideChartTip(); };
    hit.addEventListener("pointerenter", show);
    hit.addEventListener("pointerleave", hide);
    hit.addEventListener("focus", show);
    hit.addEventListener("blur", hide);
    const go = () => {
      hideChartTip();
      state.year = mo.y; state.month = mo.m;
      state.selected = `${mo.ym}-01`;
      render();
    };
    hit.addEventListener("click", go);
    hit.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  });
}

function showChartTip(wrap, mo, series, cx) {
  let tip = $("#chart-tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "chart-tip";
    tip.className = "chart-tip";
    tip.setAttribute("role", "status");
  }
  wrap.appendChild(tip);
  tip.replaceChildren();
  const add = (cls, text, parent = tip) => {
    const el = document.createElement("div");
    el.className = cls;
    el.textContent = text;
    parent.appendChild(el);
    return el;
  };
  add("tip-title", `${mo.y}년 ${mo.m + 1}월`);
  const rows = series.filter((s) => mo.values[s.key]);
  if (!rows.length) add("tip-sub", "기록 없음");
  for (const s of [...rows].reverse()) { // 막대에서 위에 있는 것이 먼저
    const row = add("tip-row", "");
    const key = document.createElement("span");
    key.className = "tip-key";
    key.style.background = s.color;
    row.appendChild(key);
    const val = document.createElement("strong");
    val.textContent = won(mo.values[s.key]);
    row.appendChild(val);
    const name = document.createElement("span");
    name.className = "tip-name";
    name.textContent = s.name;
    row.appendChild(name);
  }
  if (rows.length > 1) add("tip-total", `합계 ${won(mo.total)}`);
  if (chartState.mode === "method" && mo.count) {
    const top = Object.entries(mo.cats).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 3);
    if (top.length) add("tip-sub", `많이 쓴 곳: ${top.map(([c, v]) => `${c} ${axisWon(v)}`).join(" · ")}`);
  }
  tip.hidden = false;
  // 막대를 가리지 않게 오른쪽 옆에, 자리가 없으면 왼쪽 옆에
  const w = tip.offsetWidth;
  const right = cx + 18;
  const left = cx - 18 - w;
  tip.style.left = `${right + w <= wrap.clientWidth ? right : Math.max(0, left)}px`;
}
function hideChartTip() {
  const tip = $("#chart-tip");
  if (tip) tip.hidden = true;
}

function renderChartLegend(series) {
  const ul = $("#chart-legend");
  ul.replaceChildren(...series.map((s) => {
    const li = document.createElement("li");
    const sw = document.createElement("span");
    sw.className = "legend-swatch";
    sw.style.background = s.color;
    li.append(sw, document.createTextNode(s.name));
    return li;
  }));
}

// 한 줄 요약: 기록이 있는 달 평균, 지난달과 비교
function renderChartNote(months) {
  const note = $("#chart-note");
  const withData = months.filter((mo) => mo.count);
  if (!withData.length) { note.textContent = ""; return; }
  const avg = withData.reduce((s, mo) => s + mo.total, 0) / withData.length;
  const idx = months.findIndex((mo) => mo.ym === ymOf(state.year, state.month));
  let text = `기록이 있는 ${withData.length}개월 평균 ${won(avg)}`;
  if (idx > 0 && months[idx].count && months[idx - 1].count) {
    const diff = months[idx].total - months[idx - 1].total;
    text += diff === 0 ? ` · ${state.month + 1}월은 지난달과 같아요`
      : ` · ${state.month + 1}월은 지난달보다 ${won(Math.abs(diff))} ${diff > 0 ? "더 썼어요 ▲" : "덜 썼어요 ▼"}`;
  }
  note.textContent = text;
}

function renderChartTable(months, series) {
  const box = $("#chart-table");
  box.hidden = !chartState.table;
  $("#chart-table-toggle").textContent = chartState.table ? "표 숨기기" : "표로 보기";
  if (!chartState.table) return;
  const table = document.createElement("table");
  table.className = "data-table";
  const head = table.createTHead().insertRow();
  for (const h of ["월", ...series.map((s) => s.name), "합계"]) {
    const th = document.createElement("th");
    th.textContent = h;
    head.appendChild(th);
  }
  const body = table.createTBody();
  for (const mo of [...months].reverse()) {
    const tr = body.insertRow();
    tr.insertCell().textContent = `${mo.y}.${pad(mo.m + 1)}`;
    for (const s of series) tr.insertCell().textContent = mo.values[s.key] ? won(mo.values[s.key]) : "-";
    tr.insertCell().textContent = mo.count ? won(mo.total) : "-";
  }
  box.replaceChildren(table);
}

$$(".seg-btn").forEach((b) => (b.onclick = () => {
  chartState.mode = b.dataset.mode;
  try { localStorage.setItem(CHART_MODE_KEY, chartState.mode); } catch { /* 무시 */ }
  renderChart();
}));
$("#chart-table-toggle").onclick = () => { chartState.table = !chartState.table; renderChart(); };
let chartResizeTimer;
window.addEventListener("resize", () => { clearTimeout(chartResizeTimer); chartResizeTimer = setTimeout(renderChart, 150); });

renderChart();
