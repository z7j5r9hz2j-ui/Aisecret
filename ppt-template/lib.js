// Veebar Tech 디자인 시스템 — 토큰, 에셋, 공통 컴포넌트, 슬라이드 마스터
// 디자인 토큰은 veebartech.ca 화면에서 추출한 값입니다.
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const Lu = require("react-icons/lu");

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
    // 자간은 영문 대문자 라벨에만 (한글은 자간을 넓히면 어색함)
    color, charSpacing: /[가-힣]/.test(text) ? 0 : 2, isTextBox: true,
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

// 새 프레젠테이션 + 마스터 3종 (VEEBAR_LIGHT / VEEBAR_CONTENT / VEEBAR_GRADIENT)
async function createPresentation({ title: deckTitle, author }) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.author = author;
  pres.company = "Veebar Tech";
  pres.title = deckTitle;
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

  return pres;
}

module.exports = {
  T, FONT, NUM_FONT, W, H, M,
  gradientPng, iconPng, shadow, card, eyebrow, pill, button, iconTile, title, header,
  createPresentation,
};
