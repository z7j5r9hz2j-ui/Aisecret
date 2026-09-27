// Veebar Tech 브랜드 PPT 생성기
// 사용법: npm install && npm run build  →  VeebarTech_Quality_Report.pptx
// 디자인 토큰은 veebartech.ca 화면에서 추출한 값입니다.
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const Lu = require("react-icons/lu");
const C = require("./content");

// ── Design tokens ────────────────────────────────────────────────
const T = {
  ink: "0A1722", // 헤드라인·다크 버튼
  blue: "024996", // 프라이머리 (Book a call, eyebrow, 강조 이탤릭)
  teal: "1C7A8C", // 그라디언트 끝·포인트 dot
  deep: "0F4A59", // 로고 V 마크·다크 틸 버튼
  sky: "4F90D6", // 카드 상단 그라디언트 끝
  slate: "5A6B7B", // 본문
  muted: "8A96A3", // 캡션
  tint: "EEF4F9", // pill 배경
  iconBg: "EAF2FC", // 아이콘 타일 배경
  border: "E3E9F0", // 카드 테두리·구분선
  page: "F8FAFC", // 콘텐츠 페이지 배경
  white: "FFFFFF",
};
const FONT = "Malgun Gothic";
const NUM_FONT = "Arial";
const W = 13.333, H = 7.5, M = 0.6; // LAYOUT_WIDE, 여백

// ── Asset helpers ────────────────────────────────────────────────
const asset = (f) => path.join(__dirname, "assets", f);
const b64 = (buf) => "image/png;base64," + buf.toString("base64");

async function gradientPng(wIn, hIn, radiusIn = 0, from = T.blue, to = T.teal) {
  const s = 150, w = Math.round(wIn * s), h = Math.round(hIn * s), r = Math.round(radiusIn * s);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#${from}"/><stop offset="1" stop-color="#${to}"/></linearGradient></defs>
    <rect width="${w}" height="${h}" rx="${r}" ry="${r}" fill="url(#g)"/></svg>`;
  return b64(await sharp(Buffer.from(svg)).png().toBuffer());
}

async function iconPng(name, color, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Lu[name], { color: "#" + color, size: px, strokeWidth: 2 })
  );
  return b64(await sharp(Buffer.from(svg)).png().toBuffer());
}

// ── Reusable components ──────────────────────────────────────────
const shadow = () => ({ type: "outer", color: "0A1722", opacity: 0.08, blur: 18, offset: 4, angle: 90 });

function card(pres, slide, x, y, w, h, fill = T.white, withShadow = true) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.28, fill: { color: fill },
    line: { color: T.border, width: 0.75 }, ...(withShadow ? { shadow: shadow() } : {}),
  });
}

// 대문자 eyebrow 라벨 (GROWTH TECHNOLOGY 스타일)
function eyebrow(slide, text, x, y, w = 6, color = T.blue) {
  slide.addText(text, {
    x, y, w, h: 0.35, margin: 0, fontFace: NUM_FONT, fontSize: 12, bold: true,
    color, charSpacing: 2, isTextBox: true,
  });
}

// 알약형 태그 (● YOUR TECHNOLOGY PARTNER 스타일)
function pill(pres, slide, text, x, y) {
  const w = 0.8 + text.length * 0.16;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.44, rectRadius: 0.22, fill: { color: T.tint }, line: { color: T.tint } });
  slide.addShape(pres.shapes.OVAL, { x: x + 0.24, y: y + 0.165, w: 0.11, h: 0.11, fill: { color: T.teal }, line: { color: T.teal } });
  slide.addText(text, { x: x + 0.45, y, w: w - 0.55, h: 0.44, margin: 0, fontFace: NUM_FONT, fontSize: 12, bold: true, color: T.blue, charSpacing: 2, valign: "middle", isTextBox: true });
}

// 둥근 버튼
function button(pres, slide, text, x, y, w, style) {
  const s = {
    primary: { fill: T.blue, line: T.blue, color: T.white },
    dark: { fill: T.ink, line: T.ink, color: T.white },
    white: { fill: T.white, line: T.white, color: T.blue },
    ghost: { fill: null, line: "9DB9CE", color: T.white },
    outline: { fill: T.white, line: T.border, color: T.ink },
  }[style];
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h: 0.62, rectRadius: 0.31,
    fill: s.fill ? { color: s.fill } : { type: "none" }, line: { color: s.line, width: 1.25 },
  });
  slide.addText(text, { x, y, w, h: 0.62, margin: 0, align: "center", valign: "middle", fontFace: FONT, fontSize: 15, bold: true, color: s.color, isTextBox: true });
}

// 아이콘 타일 (연한 파란 배경 + 파란 아이콘)
async function iconTile(pres, slide, name, x, y, size = 0.8) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: size, h: size, rectRadius: size * 0.28, fill: { color: T.iconBg }, line: { color: T.iconBg } });
  const p = size * 0.25;
  slide.addImage({ data: await iconPng(name, T.blue), x: x + p, y: y + p, w: size - 2 * p, h: size - 2 * p });
}

function title(slide, text, x, y, w, size = 34) {
  slide.addText(text, { x, y, w, h: 0.8, margin: 0, fontFace: FONT, fontSize: size, bold: true, color: T.ink, valign: "top", isTextBox: true });
}

function header(slide, eb, ttl) {
  eyebrow(slide, eb, M, 0.95);
  title(slide, ttl, M, 1.3, 9);
}

// ── Build ────────────────────────────────────────────────────────
async function build() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.author = C.meta.author;
  pres.company = "Veebar Tech";
  pres.title = "Veebar Tech 품질 보고서";
  pres.theme = { headFontFace: FONT, bodyFontFace: FONT };

  const logoW = 2.1, logoH = logoW * 219 / 1176;
  const numStyle = { x: W - M - 1, y: H - 0.55, w: 1, h: 0.3, fontFace: NUM_FONT, fontSize: 10, color: T.muted, align: "right" };

  // 슬라이드 마스터 — PowerPoint의 "새 슬라이드"에서 레이아웃으로 선택 가능
  pres.defineSlideMaster({
    title: "VEEBAR_LIGHT",
    background: { color: T.white },
    objects: [{ image: { path: asset("logo.png"), x: M, y: 0.4, w: logoW, h: logoH } }],
    slideNumber: numStyle,
  });
  pres.defineSlideMaster({
    title: "VEEBAR_CONTENT",
    background: { color: T.page },
    objects: [{ image: { path: asset("logo.png"), x: W - M - 1.6, y: 0.42, w: 1.6, h: 1.6 * 219 / 1176 } }],
    slideNumber: numStyle,
  });
  pres.defineSlideMaster({
    title: "VEEBAR_GRADIENT",
    background: { data: await gradientPng(W, H) },
    objects: [{ image: { path: asset("logo_white.png"), x: M, y: 0.4, w: logoW, h: logoH } }],
    slideNumber: { ...numStyle, color: "C9DCEA" },
  });

  // 1. 표지 ----------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_LIGHT" });
    pill(pres, s, C.meta.eyebrow, M, 1.75);
    s.addText(
      C.meta.titleParts.map((p) => ({
        text: p.text,
        options: p.accent ? { color: T.blue, italic: true } : { color: T.ink },
      })),
      { x: M, y: 2.45, w: 6.9, h: 2.2, margin: 0, fontFace: FONT, fontSize: 46, bold: true, valign: "top", lineSpacingMultiple: 1.05, isTextBox: true }
    );
    s.addText(C.meta.subtitle, { x: M, y: 4.75, w: 6.2, h: 0.8, margin: 0, fontFace: FONT, fontSize: 16, color: T.slate, valign: "top", isTextBox: true });
    s.addText(`${C.meta.date}   ·   ${C.meta.author}`, { x: M, y: 6.35, w: 5, h: 0.35, margin: 0, fontFace: FONT, fontSize: 12, bold: true, color: T.ink, isTextBox: true });

    // 오른쪽 그라디언트 카드 + 핵심 수치
    const cx = 8.0, cy = 1.1, cw = W - M - cx, ch = 5.6;
    s.addImage({ data: await gradientPng(cw, ch, 0.35), x: cx, y: cy, w: cw, h: ch });
    s.addImage({ data: await iconPng("LuNetwork", "FFFFFF", 512), x: cx + cw - 2.5, y: cy + ch - 2.6, w: 2.3, h: 2.3, transparency: 88 });
    eyebrow(s, "AT A GLANCE", cx + 0.55, cy + 0.55, 4, "C9E3EC");
    C.meta.coverStats.forEach((st, i) => {
      const yy = cy + 1.15 + i * 1.4;
      s.addText(st.value, { x: cx + 0.55, y: yy, w: 3.8, h: 0.8, margin: 0, fontFace: NUM_FONT, fontSize: 42, bold: true, color: T.white, isTextBox: true });
      s.addText(st.label, { x: cx + 0.55, y: yy + 0.78, w: 3.8, h: 0.35, margin: 0, fontFace: FONT, fontSize: 14, color: "D5E6EE", isTextBox: true });
    });
  }

  // 2. 목차 ----------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_LIGHT" });
    eyebrow(s, "CONTENTS", M, 1.6);
    title(s, "목차", M, 1.95, 4, 44);
    s.addText("보고서는 네 개의 파트로 구성됩니다.", { x: M, y: 2.95, w: 3.8, h: 0.8, margin: 0, fontFace: FONT, fontSize: 15, color: T.slate, valign: "top", isTextBox: true });
    const x0 = 5.2, rw = W - M - x0, rh = 1.05, gap = 0.3;
    C.contents.forEach((c, i) => {
      const y = 1.25 + i * (rh + gap);
      card(pres, s, x0, y, rw, rh);
      s.addText(String(i + 1).padStart(2, "0"), { x: x0 + 0.4, y, w: 0.9, h: rh, margin: 0, fontFace: NUM_FONT, fontSize: 28, bold: true, color: T.blue, valign: "middle", isTextBox: true });
      s.addText(c.title, { x: x0 + 1.45, y, w: 2.9, h: rh, margin: 0, fontFace: FONT, fontSize: 20, bold: true, color: T.ink, valign: "middle", isTextBox: true });
      s.addText(c.desc, { x: x0 + 4.4, y, w: rw - 4.8, h: rh, margin: 0, fontFace: FONT, fontSize: 14, color: T.slate, valign: "middle", isTextBox: true });
    });
  }

  // 3. 섹션 구분 -----------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_GRADIENT" });
    s.addText(C.section.number, { x: W - M - 5, y: 3.4, w: 5, h: 3.2, margin: 0, fontFace: NUM_FONT, fontSize: 200, bold: true, color: T.white, transparency: 85, align: "right", valign: "bottom", isTextBox: true });
    eyebrow(s, C.section.eyebrow, M, 2.6, 6, "C9E3EC");
    s.addText(C.section.title, { x: M, y: 3.0, w: 8, h: 1.1, margin: 0, fontFace: FONT, fontSize: 48, bold: true, color: T.white, valign: "top", isTextBox: true });
    s.addText(C.section.desc, { x: M, y: 4.2, w: 7, h: 0.6, margin: 0, fontFace: FONT, fontSize: 17, color: "DCEAF1", valign: "top", isTextBox: true });
  }

  // 4. KPI 요약 ------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "EXECUTIVE SUMMARY", "핵심 품질 지표");
    const n = C.kpis.length, gap = 0.35, cw = (W - 2 * M - gap * (n - 1)) / n, y = 2.75, ch = 3.4;
    C.kpis.forEach((k, i) => {
      const x = M + i * (cw + gap);
      card(pres, s, x, y, cw, ch);
      s.addText(k.label, { x: x + 0.4, y: y + 0.45, w: cw - 0.8, h: 0.4, margin: 0, fontFace: FONT, fontSize: 15, color: T.slate, isTextBox: true });
      s.addText(k.value, { x: x + 0.4, y: y + 1.0, w: cw - 0.6, h: 1.1, margin: 0, fontFace: NUM_FONT, fontSize: 48, bold: true, color: T.ink, valign: "middle", isTextBox: true });
      const col = k.good ? T.teal : "C2410C", bg = k.good ? "E6F3F5" : "FDEEE6";
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.4, y: y + 2.5, w: 1.45, h: 0.42, rectRadius: 0.21, fill: { color: bg }, line: { color: bg } });
      s.addText(k.delta, { x: x + 0.4, y: y + 2.5, w: 1.45, h: 0.42, margin: 0, align: "center", valign: "middle", fontFace: FONT, fontSize: 12, bold: true, color: col, isTextBox: true });
    });
    s.addText("전분기 대비 증감", { x: M, y: 6.45, w: 4, h: 0.3, margin: 0, fontFace: FONT, fontSize: 11, color: T.muted, isTextBox: true });
  }

  // 5. 차트 ----------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "TREND", "월별 불량률 추이");
    const cx = M, cy = 2.5, cw = 7.9, ch = 4.3;
    card(pres, s, cx, cy, cw, ch);
    s.addChart(pres.charts.LINE, [
      { name: "불량률(%)", labels: C.trend.labels, values: C.trend.actual },
      { name: "목표(%)", labels: C.trend.labels, values: C.trend.target },
    ], {
      x: cx + 0.25, y: cy + 0.25, w: cw - 0.5, h: ch - 0.45,
      chartColors: [T.blue, "9FB3C8"], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 7,
      showLegend: true, legendPos: "t", legendFontFace: FONT, legendFontSize: 11, legendColor: T.slate,
      catAxisLabelColor: T.slate, valAxisLabelColor: T.slate, catAxisLabelFontFace: FONT, valAxisLabelFontFace: NUM_FONT,
      catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, valAxisLabelFormatCode: "0.0",
      valAxisMinVal: 0, valAxisMaxVal: 0.8, valAxisMajorUnit: 0.2,
      valGridLine: { color: "E8EDF2", size: 0.75 }, catGridLine: { style: "none" },
      catAxisLineShow: false, valAxisLineShow: false,
    });
    const ix = cx + cw + 0.4, iw = W - M - ix;
    C.trend.insights.forEach((it, i) => {
      const y = cy + i * 1.5, h = 1.25;
      card(pres, s, ix, y, iw, h);
    });
    for (const [i, it] of C.trend.insights.entries()) {
      const y = cy + i * 1.5;
      await iconTile(pres, s, it.icon, ix + 0.3, y + 0.28, 0.7);
      s.addText(it.title, { x: ix + 1.2, y: y + 0.24, w: iw - 1.4, h: 0.4, margin: 0, fontFace: FONT, fontSize: 16, bold: true, color: T.ink, isTextBox: true });
      s.addText(it.desc, { x: ix + 1.2, y: y + 0.64, w: iw - 1.4, h: 0.4, margin: 0, fontFace: FONT, fontSize: 12, color: T.slate, isTextBox: true });
    }
  }

  // 6. 표 ------------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "DEFECT ANALYSIS", "불량 유형별 현황");
    const tx = M, ty = 2.5, tw = W - 2 * M;
    card(pres, s, tx, ty, tw, 4.25);
    const inner = tw - 0.7, colW = [0.3, 0.14, 0.14, 0.2, 0.22].map((f) => +(f * inner).toFixed(3));
    const border = { type: "solid", color: T.border, pt: 0.75 };
    const none = { type: "none" };
    const statusColor = { "완료": T.teal, "진행 중": T.blue, "모니터링": T.slate };
    const rows = [
      C.defects.header.map((h, i) => ({
        text: h, options: { bold: true, color: T.blue, fill: { color: T.tint }, align: i === 0 ? "left" : "center", border: [none, none, none, none] },
      })),
      ...C.defects.rows.map((r) => r.map((v, i) => ({
        text: v,
        options: {
          color: i === 4 ? statusColor[v] || T.ink : i === 0 ? T.ink : T.slate,
          bold: i === 0 || i === 4, align: i === 0 ? "left" : "center",
          border: [none, none, border, none],
        },
      }))),
    ];
    s.addTable(rows, {
      x: tx + 0.35, y: ty + 0.35, colW, rowH: 0.52,
      fontFace: FONT, fontSize: 14, valign: "middle", margin: [0, 0.15, 0, 0.15],
    });
    s.addText(C.defects.note, { x: tx + 0.35, y: ty + 3.72, w: 8, h: 0.35, margin: 0, fontFace: FONT, fontSize: 12, color: T.muted, isTextBox: true });
  }

  // 7. 전후 비교 -----------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "BEFORE / AFTER", C.compare.title);
    const y = 2.5, h = 3.7, gap = 1.1, cw = (W - 2 * M - gap) / 2;
    const lx = M, rx = M + cw + gap;
    card(pres, s, lx, y, cw, h);
    s.addImage({ data: await gradientPng(cw, h, 0.28), x: rx, y, w: cw, h });
    // 가운데 화살표 원
    s.addShape(pres.shapes.OVAL, { x: lx + cw + gap / 2 - 0.35, y: y + h / 2 - 0.35, w: 0.7, h: 0.7, fill: { color: T.white }, line: { color: T.border, width: 0.75 }, shadow: shadow() });
    s.addImage({ data: await iconPng("LuArrowRight", T.blue), x: lx + cw + gap / 2 - 0.18, y: y + h / 2 - 0.18, w: 0.36, h: 0.36 });

    const side = (x, d, dark) => {
      eyebrow(s, d.label, x + 0.5, y + 0.5, 4, dark ? "C9E3EC" : T.slate);
      s.addText(d.title, { x: x + 0.5, y: y + 0.9, w: cw - 1, h: 0.6, margin: 0, fontFace: FONT, fontSize: 26, bold: true, color: dark ? T.white : T.ink, isTextBox: true });
      s.addText(d.items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < d.items.length - 1 } })), {
        x: x + 0.5, y: y + 1.85, w: cw - 1, h: 2.0, margin: 0, fontFace: FONT, fontSize: 17,
        color: dark ? T.white : T.slate, paraSpaceAfter: 14, valign: "top", isTextBox: true,
      });
    };
    side(lx, C.compare.before, false);
    side(rx, C.compare.after, true);
  }

  // 8. 개선 과제 (아이콘 카드) ---------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_CONTENT" });
    header(s, "NEXT QUARTER", "4분기 개선 과제");
    const n = C.initiatives.length, gap = 0.4, cw = (W - 2 * M - gap * (n - 1)) / n, y = 2.5, ch = 3.9;
    for (const [i, it] of C.initiatives.entries()) {
      const x = M + i * (cw + gap);
      card(pres, s, x, y, cw, ch);
      await iconTile(pres, s, it.icon, x + 0.45, y + 0.5, 0.85);
      eyebrow(s, it.eyebrow, x + 0.45, y + 1.65, cw - 0.9);
      s.addText(it.title, { x: x + 0.45, y: y + 2.02, w: cw - 0.9, h: 0.55, margin: 0, fontFace: FONT, fontSize: 22, bold: true, color: T.ink, isTextBox: true });
      s.addText(it.desc, { x: x + 0.45, y: y + 2.7, w: cw - 0.9, h: 1.2, margin: 0, fontFace: FONT, fontSize: 14, color: T.slate, valign: "top", lineSpacingMultiple: 1.2, isTextBox: true });
    }
  }

  // 9. 마무리 --------------------------------------------------------
  {
    const s = pres.addSlide({ masterName: "VEEBAR_LIGHT" });
    const cx = 1.6, cy = 1.25, cw = W - 2 * cx, ch = 5.4;
    s.addImage({ data: await gradientPng(cw, ch, 0.45), x: cx, y: cy, w: cw, h: ch });
    s.addText(C.closing.title, { x: cx, y: cy + 1.0, w: cw, h: 1.2, margin: 0, fontFace: FONT, fontSize: 54, bold: true, color: T.white, align: "center", valign: "middle", isTextBox: true });
    s.addText(C.closing.desc, { x: cx + 1, y: cy + 2.3, w: cw - 2, h: 0.6, margin: 0, fontFace: FONT, fontSize: 18, color: "DCEAF1", align: "center", valign: "middle", isTextBox: true });
    const bw = 2.6, bx = W / 2 - bw - 0.15;
    button(pres, s, C.closing.primary, bx, cy + 3.5, bw, "white");
    button(pres, s, C.closing.secondary, W / 2 + 0.15, cy + 3.5, bw, "ghost");
  }

  const out = path.join(__dirname, "VeebarTech_Quality_Report.pptx");
  await pres.writeFile({ fileName: out });
  console.log("wrote", out);
}

build().catch((e) => { console.error(e); process.exit(1); });
