// 설비 문제 해결 경과 보고 (가설 → 실행 → 결과를 시간 순서로)
// 사용법: npm run build:troubleshooting  →  VeebarTech_Troubleshooting_Report.pptx
const path = require("path");
const C = require("./content-troubleshooting");
const {
  T, FONT, NUM_FONT, W, H, M,
  gradientPng, iconPng, shadow, card, eyebrow, pill, button, iconTile, header,
  createPresentation,
} = require("./lib");

// 판정 상태별 스타일
const STATUS = {
  rejected: { label: "기각", fg: T.slate, bg: "EEF1F4", node: "9AA7B4" },
  partial: { label: "부분 효과", fg: "2F6FB5", bg: T.iconBg, node: T.sky },
  confirmed: { label: "원인 확인", fg: T.teal, bg: "E3F2F4", node: T.teal },
  fixed: { label: "대책 완료", fg: T.white, bg: T.blue, node: T.blue },
};
// 대책 진행 상태 (근본 원인 슬라이드)
const ACTION = {
  done: { label: "완료", fg: T.white, bg: T.blue },
  planned: { label: "진행 예정", fg: T.blue, bg: T.iconBg },
};

function statusPill(pres, slide, status, x, y, w = 1.2) {
  const s = STATUS[status] || ACTION[status];
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.36, rectRadius: 0.18, fill: { color: s.bg }, line: { color: s.bg } });
  slide.addText(s.label, { x, y, w, h: 0.36, margin: 0, align: "center", valign: "middle", fontFace: FONT, fontSize: 11, bold: true, color: s.fg, isTextBox: true });
}

const text = (slide, str, x, y, w, h, o = {}) =>
  slide.addText(str, { x, y, w, h, margin: 0, fontFace: FONT, fontSize: 14, color: T.slate, valign: "top", isTextBox: true, ...o });

async function build() {
  const pres = await createPresentation({ title: "설비 문제 해결 경과 보고", author: C.meta.author });

  // 1. 표지 ----------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_LIGHT" });
    pill(pres, s, C.meta.eyebrow, M, 1.75);
    s.addText(
      C.meta.titleParts.map((p) => ({ text: p.text, options: p.accent ? { color: T.blue, italic: true } : { color: T.ink } })),
      { x: M, y: 2.45, w: 7.0, h: 2.2, margin: 0, fontFace: FONT, fontSize: 44, bold: true, valign: "top", lineSpacingMultiple: 1.05, isTextBox: true }
    );
    text(s, C.meta.subtitle, M, 4.75, 6.4, 0.8, { fontSize: 16 });
    text(s, `${C.meta.date}   ·   ${C.meta.author}`, M, 6.35, 5, 0.35, { fontSize: 12, bold: true, color: T.ink });

    const cx = 8.0, cy = 1.1, cw = W - M - cx, ch = 5.6;
    s.addImage({ data: await gradientPng(cw, ch, 0.35), x: cx, y: cy, w: cw, h: ch });
    s.addImage({ data: await iconPng("LuWrench", "FFFFFF", 512), x: cx + cw - 2.4, y: cy + ch - 2.5, w: 2.2, h: 2.2, transparency: 88 });
    eyebrow(s, "AT A GLANCE", cx + 0.55, cy + 0.55, 4, "C9E3EC");
    C.meta.coverStats.forEach((st, i) => {
      const yy = cy + 1.15 + i * 1.4;
      s.addText(st.value, { x: cx + 0.55, y: yy, w: 4, h: 0.8, margin: 0, fontFace: NUM_FONT, fontSize: 40, bold: true, color: T.white, isTextBox: true });
      text(s, st.label, cx + 0.55, yy + 0.78, 3.8, 0.35, { color: "D5E6EE" });
    });
  }

  // 2. 문제 정의 -----------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "PROBLEM", `문제 정의 · ${C.problem.equipment}`);
    const y0 = 2.45, lw = 7.6, rowH = 1.3, gap = 0.2;
    for (const [i, r] of C.problem.rows.entries()) {
      const y = y0 + i * (rowH + gap);
      card(pres, s, M, y, lw, rowH);
      await iconTile(pres, s, r.icon, M + 0.35, y + 0.27, 0.76);
      eyebrow(s, r.label, M + 1.4, y + 0.28, 3, T.blue);
      text(s, r.text, M + 1.4, y + 0.62, lw - 1.7, 0.5, { fontSize: 16, bold: true, color: T.ink });
    }
    const rx = M + lw + 0.4, rw = W - M - rx, sh = (rowH * 3 + gap * 2 - gap * 2) / 3;
    C.problem.stats.forEach((st, i) => {
      const y = y0 + i * (sh + gap);
      card(pres, s, rx, y, rw, sh);
      s.addText(st.value, { x: rx + 0.4, y: y + 0.18, w: rw - 0.8, h: 0.7, margin: 0, fontFace: NUM_FONT, fontSize: 34, bold: true, color: T.ink, valign: "middle", isTextBox: true });
      text(s, st.label, rx + 0.4, y + 0.88, rw - 0.8, 0.3, { fontSize: 13 });
    });
  }

  // 3. 타임라인 개요 -------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "TIMELINE", "가설·실행 타임라인");
    const items = C.items, n = items.length;
    const axisY = 4.3, x0 = M + 1.0, x1 = W - M - 1.0, step = (x1 - x0) / (n - 1);
    const cw = Math.min(2.9, step * 2 - 0.25), ch = 1.45;
    s.addShape(pres.shapes.LINE, { x: M, y: axisY, w: W - 2 * M, h: 0, line: { color: "C9D5E2", width: 2 } });
    items.forEach((it, i) => {
      const cx = x0 + i * step, up = i % 2 === 0;
      const x = Math.max(M, Math.min(W - M - cw, cx - cw / 2));
      const y = up ? axisY - 0.35 - ch : axisY + 0.35;
      s.addShape(pres.shapes.LINE, { x: cx, y: up ? y + ch : axisY, w: 0, h: 0.35, line: { color: "C9D5E2", width: 1.25 } });
      card(pres, s, x, y, cw, ch);
      s.addText([
        { text: it.id, options: { bold: true, color: T.blue } },
        { text: `  ${it.date}`, options: { color: T.muted } },
      ], { x: x + 0.25, y: y + 0.18, w: cw - 0.5, h: 0.3, margin: 0, fontFace: NUM_FONT, fontSize: 12, isTextBox: true });
      text(s, it.hypothesis, x + 0.25, y + 0.5, cw - 0.5, 0.4, { fontSize: 14, bold: true, color: T.ink });
      statusPill(pres, s, it.status, x + 0.25, y + 0.95, 1.15);
      const st = STATUS[it.status];
      s.addShape(pres.shapes.OVAL, { x: cx - 0.13, y: axisY - 0.13, w: 0.26, h: 0.26, fill: { color: st.node }, line: { color: T.white, width: 2.5 } });
    });
    // 범례
    Object.keys(STATUS).forEach((k, i) => statusPill(pres, s, k, M + i * 1.35, 6.55, 1.2));
  }

  // 4. 가설·실행 로그 표 ---------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "ACTION LOG", "가설별 검증·실행 내역");
    const tx = M, ty = 2.35, tw = W - 2 * M, inner = tw - 0.7;
    const rowH = 0.5;
    card(pres, s, tx, ty, tw, 0.7 + rowH * (C.items.length + 1));
    const none = { type: "none" }, line = { type: "solid", color: T.border, pt: 0.75 };
    const colW = [0.06, 0.08, 0.22, 0.23, 0.26, 0.15].map((f) => +(f * inner).toFixed(3));
    const head = ["#", "날짜", "가설", "검증·실행", "결과", "판정"].map((h, i) => ({
      text: h, options: { bold: true, color: T.blue, fill: { color: T.tint }, align: i >= 5 ? "center" : "left", border: [none, none, none, none] },
    }));
    const rows = C.items.map((it) => {
      const st = STATUS[it.status];
      const cell = (v, o = {}) => ({ text: v, options: { color: T.slate, border: [none, none, line, none], ...o } });
      return [
        cell(it.id, { bold: true, color: T.blue, fontFace: NUM_FONT }),
        cell(it.date, { fontFace: NUM_FONT }),
        cell(it.hypothesis, { bold: true, color: T.ink }),
        cell(it.action),
        cell(it.result),
        cell("● " + st.label, { bold: true, align: "center", color: it.status === "fixed" ? T.blue : st.fg === T.slate ? "8A96A3" : st.fg }),
      ];
    });
    s.addTable([head, ...rows], { x: tx + 0.35, y: ty + 0.35, colW, rowH, fontFace: FONT, fontSize: 12, valign: "middle", margin: [0, 0.1, 0, 0.1] });
  }

  // 5. 핵심 가설 상세 ------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    const d = C.deepDive;
    header(s, `KEY HYPOTHESIS · ${d.id}`, d.title);
    const n = d.steps.length, gap = 0.5, cw = (W - 2 * M - gap * (n - 1)) / n, y = 2.4, ch = 2.25;
    for (const [i, st] of d.steps.entries()) {
      const x = M + i * (cw + gap), last = i === n - 1;
      if (last) s.addImage({ data: await gradientPng(cw, ch, 0.28), x, y, w: cw, h: ch });
      else card(pres, s, x, y, cw, ch);
      s.addText(String(i + 1).padStart(2, "0"), { x: x + 0.35, y: y + 0.3, w: 0.5, h: 0.4, margin: 0, fontFace: NUM_FONT, fontSize: 14, bold: true, color: last ? "C9E3EC" : T.blue, valign: "middle", isTextBox: true });
      text(s, st.label, x + 0.85, y + 0.3, cw - 1.1, 0.4, { fontSize: 15, bold: true, color: last ? T.white : T.ink, valign: "middle" });
      text(s, st.text, x + 0.35, y + 0.85, cw - 0.7, 1.2, { fontSize: 14, color: last ? T.white : T.slate, lineSpacingMultiple: 1.15 });
      if (!last) s.addImage({ data: await iconPng("LuArrowRight", "9FB3C8"), x: x + cw + gap / 2 - 0.15, y: y + ch / 2 - 0.15, w: 0.3, h: 0.3 });
    }
    const ey = 5.0, eh = 1.7;
    card(pres, s, M, ey, W - 2 * M, eh);
    eyebrow(s, "EVIDENCE", M + 0.45, ey + 0.3, 3);
    const colors = [T.ink, "C2410C", T.teal];
    const ew = (W - 2 * M - 3.2) / d.evidence.length;
    d.evidence.forEach((e, i) => {
      const x = M + 3.0 + i * ew;
      s.addText([
        { text: e.value, options: { fontSize: 34, bold: true, color: colors[i % 3] } },
        { text: " " + e.unit, options: { fontSize: 14, color: T.slate } },
      ], { x, y: ey + 0.3, w: ew - 0.2, h: 0.7, margin: 0, fontFace: NUM_FONT, valign: "middle", isTextBox: true });
      text(s, e.label, x, ey + 1.05, ew - 0.2, 0.35, { fontSize: 13 });
    });
    text(s, "칠러 출구 냉각수 유량", M + 0.45, ey + 0.7, 2.4, 0.6, { fontSize: 13, bold: true, color: T.ink });
  }

  // 6. 대책 효과 (주간 정지 추이) -----------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "RESULT", "주간 알람 정지 횟수 추이");
    const tr = C.trend, cx = M, cy = 2.4, cw = 8.3, ch = 4.4;
    card(pres, s, cx, cy, cw, ch);
    const before = tr.values.map((v, i) => (i < tr.fixFrom ? v : 0));
    const after = tr.values.map((v, i) => (i >= tr.fixFrom ? v : 0));
    s.addChart(pres.charts.BAR, [
      { name: "대책 전", labels: tr.labels, values: before },
      { name: "대책 후", labels: tr.labels, values: after },
    ], {
      x: cx + 0.25, y: cy + 0.2, w: cw - 0.5, h: ch - 0.35, barDir: "col", barGrouping: "stacked", barGapWidthPct: 55,
      chartColors: ["9FB3C8", T.teal],
      showValue: true, dataLabelPosition: "inEnd", dataLabelColor: T.white, dataLabelFontSize: 11, dataLabelFontBold: true, dataLabelFormatCode: "0;;;",
      showLegend: true, legendPos: "t", legendFontFace: FONT, legendFontSize: 11, legendColor: T.slate,
      catAxisLabelColor: T.slate, valAxisLabelColor: T.slate, catAxisLabelFontFace: NUM_FONT, valAxisLabelFontFace: NUM_FONT,
      catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, valAxisMinVal: 0, valAxisMaxVal: 14, valAxisMajorUnit: 2,
      valGridLine: { color: "E8EDF2", size: 0.75 }, catGridLine: { style: "none" }, catAxisLineShow: false, valAxisLineShow: false,
      showValAxisTitle: true, valAxisTitle: "정지 횟수 (회/주)", valAxisTitleFontSize: 11, valAxisTitleColor: T.slate, valAxisTitleFontFace: FONT,
    });
    const ix = cx + cw + 0.4, iw = W - M - ix;
    card(pres, s, ix, cy, iw, ch);
    text(s, "적용한 조치", ix + 0.4, cy + 0.35, iw - 0.8, 0.4, { fontSize: 14, bold: true, color: T.blue });
    tr.markers.forEach((m, i) => {
      const y = cy + 1.0 + i * 0.72;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ix + 0.4, y, w: 0.95, h: 0.4, rectRadius: 0.2, fill: { color: T.tint }, line: { color: T.tint } });
      s.addText(m.week, { x: ix + 0.4, y, w: 0.95, h: 0.4, margin: 0, align: "center", valign: "middle", fontFace: NUM_FONT, fontSize: 12, bold: true, color: T.blue, isTextBox: true });
      text(s, m.text, ix + 1.5, y, iw - 1.8, 0.4, { fontSize: 15, bold: true, color: T.ink, valign: "middle" });
    });
    // 대책 적용 다음 주부터의 결과 요약
    const after1 = tr.values.slice(tr.fixFrom + 1);
    const avg = after1.reduce((a, b) => a + b, 0) / after1.length;
    const summary = avg === 0 ? `${after1.length}주 연속 0회` : `주 평균 ${avg.toFixed(1)}회`;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ix + 0.4, y: cy + ch - 1.25, w: iw - 0.8, h: 0.85, rectRadius: 0.2, fill: { color: "E3F2F4" }, line: { color: "E3F2F4" } });
    text(s, "대책 후", ix + 0.65, cy + ch - 1.12, iw - 1.3, 0.3, { fontSize: 12, color: T.teal });
    text(s, summary, ix + 0.65, cy + ch - 0.85, iw - 1.3, 0.4, { fontSize: 18, bold: true, color: T.teal });
  }

  // 7. 근본 원인 & 대책 ----------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "ROOT CAUSE & ACTIONS", "근본 원인과 대책");
    const y = 2.4, h = 4.4, lw = 4.7;
    s.addImage({ data: await gradientPng(lw, h, 0.3), x: M, y, w: lw, h });
    eyebrow(s, "ROOT CAUSE", M + 0.45, y + 0.45, 4, "C9E3EC");
    text(s, C.rootCause.title, M + 0.45, y + 0.85, lw - 0.9, 1.1, { fontSize: 26, bold: true, color: T.white });
    text(s, C.rootCause.desc, M + 0.45, y + 2.1, lw - 0.9, 2.0, { fontSize: 14, color: "DCEAF1", lineSpacingMultiple: 1.2 });
    const rx = M + lw + 0.4, rw = W - M - rx, gap = 0.25, rh = (h - gap * 2) / 3;
    for (const [i, a] of C.rootCause.actions.entries()) {
      const yy = y + i * (rh + gap);
      card(pres, s, rx, yy, rw, rh);
      await iconTile(pres, s, a.icon, rx + 0.35, yy + (rh - 0.75) / 2, 0.75);
      eyebrow(s, a.tag, rx + 1.4, yy + 0.25, 3);
      text(s, a.title, rx + 1.4, yy + 0.55, rw - 3.1, 0.4, { fontSize: 17, bold: true, color: T.ink });
      text(s, a.desc, rx + 1.4, yy + 0.95, rw - 3.1, 0.35, { fontSize: 12.5 });
      statusPill(pres, s, a.done ? "done" : "planned", rx + rw - 1.55, yy + (rh - 0.36) / 2, 1.2);
    }
  }

  // 8. 교훈 & 향후 계획 ----------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "LESSONS & NEXT", "교훈과 향후 계획");
    const n = C.lessons.length, gap = 0.4, cw = (W - 2 * M - gap * (n - 1)) / n, y = 2.4, ch = 3.9;
    for (const [i, it] of C.lessons.entries()) {
      const x = M + i * (cw + gap);
      card(pres, s, x, y, cw, ch);
      await iconTile(pres, s, it.icon, x + 0.45, y + 0.5, 0.85);
      eyebrow(s, it.eyebrow, x + 0.45, y + 1.65, cw - 0.9);
      text(s, it.title, x + 0.45, y + 2.02, cw - 0.9, 0.55, { fontSize: 20, bold: true, color: T.ink });
      text(s, it.desc, x + 0.45, y + 2.65, cw - 0.9, 1.1, { fontSize: 14, lineSpacingMultiple: 1.2 });
    }
  }

  // 9. 마무리 --------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_LIGHT" });
    const cx = 1.6, cy = 1.25, cw = W - 2 * cx, ch = 5.4;
    s.addImage({ data: await gradientPng(cw, ch, 0.45), x: cx, y: cy, w: cw, h: ch });
    s.addText(C.closing.title, { x: cx, y: cy + 1.0, w: cw, h: 1.2, margin: 0, fontFace: FONT, fontSize: 54, bold: true, color: T.white, align: "center", valign: "middle", isTextBox: true });
    text(s, C.closing.desc, cx + 1, cy + 2.3, cw - 2, 0.6, { fontSize: 18, color: "DCEAF1", align: "center", valign: "middle" });
    const bw = 2.6;
    button(pres, s, C.closing.primary, W / 2 - bw - 0.15, cy + 3.5, bw, "white");
    button(pres, s, C.closing.secondary, W / 2 + 0.15, cy + 3.5, bw, "ghost");
  }

  const out = path.join(__dirname, "VeebarTech_Troubleshooting_Report.pptx");
  await pres.writeFile({ fileName: out });
  console.log("wrote", out);
}

build().catch((e) => { console.error(e); process.exit(1); });
