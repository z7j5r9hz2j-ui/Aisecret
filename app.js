"use strict";

// ---------- 기본 설정 ----------
const STORAGE_KEY = "ledger.v1";
const EXPORT_KEY = "ledger.exported.v1";
const DELETED_KEY = "ledger.deleted.v1";
const CARD_METHOD = "삼성카드";

const CATEGORIES = [
  "식비", "카페·간식", "교통", "쇼핑", "생활·마트", "주거·통신",
  "의료·건강", "문화·여가", "교육", "경조사·선물", "기타",
];

// 가맹점 이름으로 카테고리 자동 분류
const CATEGORY_RULES = [
  ["카페·간식", /스타벅스|커피|카페|투썸|이디야|메가|빽다방|컴포즈|폴바셋|베이커리|파리바게|뚜레쥬르|배스킨|던킨|디저트/],
  ["생활·마트", /이마트|홈플러스|롯데마트|코스트코|트레이더스|마트|다이소|GS25|지에스25|CU|씨유|세븐일레븐|이마트24|편의점|올리브영/i],
  ["식비", /식당|김밥|치킨|피자|버거|맥도날드|롯데리아|KFC|서브웨이|배달의민족|배민|우아한형제들|요기요|위대한상상|쿠팡이츠|국밥|분식|한식|중식|일식|고기|초밥|반점/i],
  ["교통", /택시|카카오T|카카오모빌리티|티머니|버스|지하철|코레일|KTX|SRT|주유|오일|에너지|GS칼텍스|SK에너지|S-OIL|주차|하이패스|고속도로/i],
  ["쇼핑", /쿠팡|11번가|G마켓|지마켓|옥션|네이버페이|무신사|SSG|신세계|현대백화점|롯데백화점|아울렛|29CM|에이블리|지그재그/i],
  ["주거·통신", /SKT|KT|LG유플러스|유플러스|통신|관리비|전기|가스|수도|인터넷/i],
  ["의료·건강", /병원|의원|약국|치과|한의원|안과|피부과|헬스|필라테스|요가/],
  ["문화·여가", /CGV|메가박스|롯데시네마|넷플릭스|유튜브|멜론|스포티파이|티빙|웨이브|왓챠|디즈니|게임|스팀|인터파크|야놀자|여기어때|호텔/i],
  ["교육", /학원|교육|서점|교보문고|영풍문고|예스24|알라딘|클래스101|인프런/],
];

function guessCategory(merchant) {
  for (const [cat, re] of CATEGORY_RULES) if (re.test(merchant)) return cat;
  return "기타";
}

// ---------- 저장소 ----------
function loadTx() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}
// 삭제한 내역 id와 시각: 다른 기기에 삭제를 전달하는 데 쓴다
function loadDeleted() {
  try { return JSON.parse(localStorage.getItem(DELETED_KEY) || "{}"); } catch { return {}; }
}
function persistLocal() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.tx));
    localStorage.setItem(DELETED_KEY, JSON.stringify(state.deleted));
  } catch { toast("저장에 실패했어요. 브라우저 저장공간을 확인하세요."); }
}
function saveTx() {
  persistLocal();
  scheduleSync();
}
// 동기화 때 어느 쪽이 최신인지 가리기 위해 수정 시각을 남긴다
function touch(t) {
  t.updatedAt = Date.now();
  return t;
}
function removeTx(id) {
  state.tx = state.tx.filter((t) => t.id !== id);
  state.deleted[id] = Date.now();
}
function loadExported() {
  try { return JSON.parse(localStorage.getItem(EXPORT_KEY) || "[]"); } catch { return []; }
}
function markExported(ym) {
  try {
    const list = new Set(loadExported());
    list.add(ym);
    localStorage.setItem(EXPORT_KEY, JSON.stringify([...list]));
  } catch { /* 무시 */ }
  scheduleSync();
}

// ---------- 유틸 ----------
const $ = (s) => document.querySelector(s);
const pad = (n) => String(n).padStart(2, "0");
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const ymOf = (y, m) => `${y}-${pad(m + 1)}`;
const won = (n) => `${Math.round(n).toLocaleString("ko-KR")}원`;
const shortWon = (n) => {
  const a = Math.abs(n);
  if (a >= 10000) return `${(n / 10000).toFixed(a >= 100000 ? 0 : 1).replace(/\.0$/, "")}만`;
  return Math.round(n).toLocaleString("ko-KR");
};
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const isCard = (t) => t.method === CARD_METHOD;
// 카드 내역의 "㈜우아한형제들" 같은 법인 표기 제거
const cleanMerchant = (s) => String(s || "").replace(/㈜|\(주\)|주식회사/g, "").trim();
const normName = (s) => String(s || "").replace(/\s+/g, "").toLowerCase();
const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function parseAmount(v) {
  if (typeof v === "number") return Math.round(v);
  const s = String(v ?? "").replace(/[,\s원₩]/g, "");
  if (!s) return NaN;
  const neg = /^\(.*\)$/.test(s) || s.startsWith("-");
  const n = parseInt(s.replace(/[^\d]/g, ""), 10);
  return isNaN(n) ? NaN : neg ? -n : n;
}

// 다양한 날짜 표기를 YYYY-MM-DD로
function parseDate(v) {
  if (v instanceof Date && !isNaN(v)) return ymd(v);
  if (typeof v === "number" && v > 30000 && v < 80000) {
    // 엑셀 날짜 일련번호
    const d = new Date(Math.round((v - 25569) * 86400000));
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  }
  const s = String(v ?? "").trim();
  let m;
  if ((m = s.match(/^(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})/))) return `${m[1]}-${pad(m[2])}-${pad(m[3])}`;
  if ((m = s.match(/^(\d{4})(\d{2})(\d{2})$/))) return `${m[1]}-${m[2]}-${m[3]}`;
  if ((m = s.match(/^(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})$/))) return `20${m[1]}-${pad(m[2])}-${pad(m[3])}`;
  if ((m = s.match(/^(\d{1,2})[.\-/](\d{1,2})$/))) return guessYear(+m[1], +m[2]);
  return null;
}

// 연도가 없는 날짜(MM/DD): 미래가 되면 작년으로 본다
function guessYear(month, day) {
  const now = new Date();
  let y = now.getFullYear();
  const d = new Date(y, month - 1, day);
  if (d - now > 86400000) y -= 1;
  return `${y}-${pad(month)}-${pad(day)}`;
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), 2500);
}

// ---------- 상태 ----------
const today = new Date();
const state = {
  tx: loadTx(),
  deleted: loadDeleted(),
  year: today.getFullYear(),
  month: today.getMonth(),
  selected: ymd(today),
  pendingImport: null,
};

function monthTx(y = state.year, m = state.month) {
  const prefix = ymOf(y, m);
  return state.tx.filter((t) => t.date.startsWith(prefix));
}

// ---------- 렌더링 ----------
function render() {
  renderCalendar();
  renderSummary();
  renderDay();
  renderBanner();
}

function renderCalendar() {
  const { year, month } = state;
  $("#month-label").textContent = `${year}년 ${month + 1}월`;

  const byDay = {};
  for (const t of monthTx()) {
    const d = (byDay[t.date] ||= { card: 0, cash: 0 });
    isCard(t) ? (d.card += t.amount) : (d.cash += t.amount);
  }

  const first = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  const todayStr = ymd(new Date());
  const cells = [];
  for (let i = 0; i < first; i++) cells.push(`<div class="day empty"></div>`);
  for (let d = 1; d <= days; d++) {
    const date = `${ymOf(year, month)}-${pad(d)}`;
    const dow = (first + d - 1) % 7;
    const s = byDay[date];
    const cls = ["day", dow === 0 && "sun", dow === 6 && "sat", date === todayStr && "today", date === state.selected && "selected"].filter(Boolean).join(" ");
    let body = "";
    if (s) {
      const split = [s.card && `<span class="c">${shortWon(s.card)}</span>`, s.cash && `<span class="h">${shortWon(s.cash)}</span>`].filter(Boolean).join("<br>");
      body = `<div class="day-split">${split}</div><div class="day-total">${shortWon(s.card + s.cash)}</div>`;
    }
    cells.push(`<div class="${cls}" data-date="${date}"><span class="day-num">${d}</span>${body}</div>`);
  }
  while (cells.length % 7) cells.push(`<div class="day empty"></div>`);
  $("#calendar").innerHTML = cells.join("");
}

function renderSummary() {
  const list = monthTx();
  let card = 0, cash = 0;
  const cats = {};
  for (const t of list) {
    isCard(t) ? (card += t.amount) : (cash += t.amount);
    cats[t.category] = (cats[t.category] || 0) + t.amount;
  }
  const total = card + cash;
  const now = new Date();
  const isCurrent = state.year === now.getFullYear() && state.month === now.getMonth();
  const daysElapsed = isCurrent ? now.getDate() : new Date(state.year, state.month + 1, 0).getDate();

  $("#sum-total").textContent = won(total);
  $("#sum-card").textContent = won(card);
  $("#sum-cash").textContent = won(cash);
  $("#sum-avg").textContent = won(total / daysElapsed);

  const sorted = Object.entries(cats).sort((a, b) => b[1] - a[1]);
  const max = sorted[0]?.[1] || 1;
  $("#cat-list").innerHTML = sorted.length
    ? sorted.map(([c, v]) => `
        <li><div class="cat-row"><span>${escapeHtml(c)}</span><span>${won(v)}</span></div>
        <div class="cat-bar"><div style="width:${Math.max(0, (v / max) * 100)}%"></div></div></li>`).join("")
    : `<li class="tx-sub">이번 달 내역이 없어요</li>`;
}

function renderDay() {
  const date = state.selected;
  if (!date) return;
  const [, m, d] = date.split("-");
  const list = state.tx.filter((t) => t.date === date).sort((a, b) => (a.time || "").localeCompare(b.time || ""));
  const sum = list.reduce((s, t) => s + t.amount, 0);
  $("#day-title").textContent = `${+m}월 ${+d}일 · ${won(sum)}`;
  $("#day-add").hidden = false;
  $("#day-list").innerHTML = list.length
    ? list.map((t) => `
        <li data-id="${escapeHtml(t.id)}">
          <span class="tx-badge ${isCard(t) ? "card" : "cash"}">${escapeHtml(t.method)}</span>
          <div class="tx-main">
            <div class="tx-merchant">${escapeHtml(t.merchant)}</div>
            <div class="tx-sub">${escapeHtml(t.category)}${t.time ? " · " + t.time : ""}${t.installment ? " · " + escapeHtml(t.installment) : ""}${t.memo ? " · " + escapeHtml(t.memo) : ""}</div>
          </div>
          <span class="tx-amount">${won(t.amount)}</span>
        </li>`).join("")
    : `<li class="empty">내역이 없어요</li>`;
}

// 월말·월초에 CSV 다운로드 알림
function renderBanner() {
  const now = new Date();
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const exported = loadExported();
  const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const prevYm = ymOf(prev.getFullYear(), prev.getMonth());
  const curYm = ymOf(now.getFullYear(), now.getMonth());
  let target = null, text = "";

  if (now.getDate() <= 10 && !exported.includes(prevYm) && monthTx(prev.getFullYear(), prev.getMonth()).length) {
    target = prev;
    text = `${prev.getMonth() + 1}월 가계부가 마감됐어요. CSV로 받아두세요.`;
  } else if (now.getDate() >= lastDay - 2 && !exported.includes(curYm)) {
    target = now;
    text = `월말이에요! ${now.getMonth() + 1}월 내역을 확인하고 CSV로 받아두세요.`;
  }
  if (target && sessionStorageGet("bannerClosed") !== text) {
    $("#export-banner-text").textContent = text;
    $("#export-banner").hidden = false;
    $("#export-banner-btn").onclick = () => exportCsv(target.getFullYear(), target.getMonth());
  } else {
    $("#export-banner").hidden = true;
  }
}
function sessionStorageGet(k) { try { return sessionStorage.getItem(k); } catch { return null; } }
function sessionStorageSet(k, v) { try { sessionStorage.setItem(k, v); } catch { /* 무시 */ } }

// ---------- 입력 / 수정 ----------
const txDialog = $("#tx-dialog");
const txForm = $("#tx-form");
txForm.category.innerHTML = CATEGORIES.map((c) => `<option>${c}</option>`).join("");

function openTxDialog(tx, date) {
  txForm.reset();
  $("#tx-dialog-title").textContent = tx ? "내역 수정" : "지출 입력";
  $("#tx-delete").hidden = !tx;
  txForm.id.value = tx?.id || "";
  txForm.date.value = tx?.date || date || ymd(new Date());
  txForm.amount.value = tx ? tx.amount.toLocaleString("ko-KR") : "";
  txForm.merchant.value = tx?.merchant || "";
  txForm.category.value = tx?.category || "식비";
  txForm.method.value = tx?.method || "현금";
  txForm.memo.value = tx?.memo || "";
  txDialog.showModal();
  if (!tx) txForm.amount.focus();
}

txForm.amount.addEventListener("input", () => {
  const n = parseAmount(txForm.amount.value);
  if (!isNaN(n)) txForm.amount.value = n.toLocaleString("ko-KR");
});
txForm.merchant.addEventListener("change", () => {
  if (!txForm.id.value) {
    const c = guessCategory(txForm.merchant.value);
    if (c !== "기타") txForm.category.value = c;
  }
});

txForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const amount = parseAmount(txForm.amount.value);
  if (isNaN(amount) || amount === 0) return toast("금액을 확인해 주세요");
  const data = {
    date: txForm.date.value,
    amount,
    merchant: txForm.merchant.value.trim(),
    category: txForm.category.value,
    method: txForm.method.value,
    memo: txForm.memo.value.trim(),
  };
  const id = txForm.id.value;
  if (id) {
    const t = state.tx.find((x) => x.id === id);
    touch(Object.assign(t, data));
  } else {
    state.tx.push(touch({ id: uid(), source: "manual", time: "", ...data }));
  }
  saveTx();
  state.selected = data.date;
  const [y, m] = data.date.split("-").map(Number);
  state.year = y; state.month = m - 1;
  txDialog.close();
  render();
  toast("저장했어요");
});

$("#tx-delete").addEventListener("click", () => {
  const id = txForm.id.value;
  if (!id || !confirm("이 내역을 삭제할까요?")) return;
  removeTx(id);
  saveTx();
  txDialog.close();
  render();
  toast("삭제했어요");
});

// ---------- 삼성카드 엑셀/CSV 불러오기 ----------
function decodeText(buf) {
  try { return new TextDecoder("utf-8", { fatal: true }).decode(buf); }
  catch { return new TextDecoder("euc-kr").decode(buf); }
}

async function readSheetRows(file) {
  if (typeof XLSX === "undefined") throw new Error("엑셀 라이브러리를 불러오지 못했어요. 인터넷 연결을 확인하세요.");
  const buf = await file.arrayBuffer();
  const wb = /\.csv$/i.test(file.name)
    ? XLSX.read(decodeText(buf), { type: "string", raw: true })
    : XLSX.read(buf, { type: "array", cellDates: true });
  const rows = [];
  for (const name of wb.SheetNames) {
    rows.push(...XLSX.utils.sheet_to_json(wb.Sheets[name], { header: 1, raw: true, defval: "" }));
  }
  return rows;
}

// 헤더 행을 찾아 열 위치를 알아낸다 (삼성카드 양식 변화에 유연하게 대응)
function findColumns(rows) {
  for (let i = 0; i < Math.min(rows.length, 40); i++) {
    const cells = rows[i].map((c) => String(c).replace(/\s/g, ""));
    const idx = (re) => cells.findIndex((c) => re.test(c));
    const date = idx(/이용일|승인일|거래일|사용일|매출일/);
    const merchant = idx(/가맹점|이용처|사용처|상호/);
    let amount = idx(/이용금액|승인금액|사용금액|매출금액|결제금액|거래금액/);
    if (amount < 0) amount = idx(/금액/);
    if (date >= 0 && amount >= 0) {
      return {
        header: i, date, merchant, amount,
        time: idx(/시간|승인시각/),
        installment: idx(/할부|이용구분|결제방법/),
        status: idx(/취소|상태|승인구분/),
      };
    }
  }
  return null;
}

function parseSheet(rows) {
  const col = findColumns(rows);
  if (!col) throw new Error("이용일/금액 열을 찾지 못했어요. 삼성카드 이용내역 파일이 맞는지 확인하세요.");
  const out = [];
  for (const r of rows.slice(col.header + 1)) {
    const rawDate = r[col.date];
    // 엑셀 셀에 '2026.09.25 12:34' 처럼 시간이 같이 있는 경우
    const dateStr = rawDate instanceof Date ? rawDate : String(rawDate).trim();
    const date = parseDate(typeof dateStr === "string" ? dateStr.split(/\s+/)[0] : dateStr);
    const amount = parseAmount(r[col.amount]);
    if (!date || isNaN(amount) || amount === 0) continue;
    let time = "";
    const tm = (col.time >= 0 ? String(r[col.time]) : String(rawDate)).match(/(\d{1,2}):(\d{2})/);
    if (tm) time = `${pad(tm[1])}:${tm[2]}`;
    const status = col.status >= 0 ? String(r[col.status]) : "";
    const merchant = col.merchant >= 0 ? cleanMerchant(r[col.merchant]) : "삼성카드 결제";
    const inst = col.installment >= 0 ? String(r[col.installment]).trim() : "";
    out.push({
      date, time, merchant: merchant || "삼성카드 결제",
      amount: /취소/.test(status) && amount > 0 ? -amount : amount,
      installment: /^\d+$/.test(inst) ? (+inst > 1 ? `${+inst}개월` : "일시불") : inst,
      source: "excel",
    });
  }
  return out;
}

// ---------- 승인 문자 분석 ----------
function parseSms(text) {
  const out = [];
  const re = /삼성\s*(?:카드)?\s*\(?\d{0,4}\)?\s*(승인취소|취소|승인)/g;
  const marks = [...text.matchAll(re)];
  marks.forEach((m, i) => {
    const chunk = text.slice(m.index, i + 1 < marks.length ? marks[i + 1].index : undefined);
    // 누적 금액은 무시: "누적" 부터 그 줄 끝까지 지운다 (누적금액, 누적: 등 표기 포함)
    const clean = chunk.replace(/누적[^\n]*/g, "");
    const amt = clean.match(/(-?[\d,]+)\s*원/);
    const dt = clean.match(/(\d{1,2})\/(\d{1,2})\s+(\d{1,2}):(\d{2})/);
    if (!amt || !dt) return;
    let merchant = clean.slice(dt.index + dt[0].length).split("\n")[0].trim();
    if (!merchant) {
      const lines = clean.slice(dt.index + dt[0].length).split("\n").map((l) => l.trim()).filter(Boolean);
      merchant = lines[0] || "삼성카드 결제";
    }
    const inst = clean.match(/(\d{1,2})\s*개월/);
    out.push({
      date: guessYear(+dt[1], +dt[2]),
      time: `${pad(dt[3])}:${dt[4]}`,
      merchant: cleanMerchant(merchant) || "삼성카드 결제",
      amount: Math.abs(parseAmount(amt[1])),
      installment: inst ? `${+inst[1]}개월` : /일시불/.test(clean) ? "일시불" : "",
      cancel: m[1] !== "승인",
      source: "sms",
    });
  });
  return out;
}

// ---------- 중복 확인 & 가져오기 ----------
function sameCardTx(a, b) {
  if (!isCard(a) || a.date !== b.date || a.amount !== b.amount) return false;
  const x = normName(a.merchant), y = normName(b.merchant);
  // 문자와 엑셀의 가맹점명이 조금 다를 수 있어 앞부분만 비교
  return !x || !y || x.startsWith(y.slice(0, 4)) || y.startsWith(x.slice(0, 4)) || (a.time && b.time && a.time === b.time);
}

function prepareImport(items) {
  // 기존 내역 하나는 새 내역 하나에만 대응시킨다 (같은 날 같은 커피 2잔도 구분)
  const used = new Set();
  const seenSms = [];
  const rows = items.map((it) => {
    if (it.cancel) {
      const target = state.tx.find((t) => !used.has(t.id) && sameCardTx(t, { ...it, time: "" }));
      if (target) used.add(target.id);
      return { ...it, status: target ? "cancel" : "cancel-miss", targetId: target?.id };
    }
    const cand = { ...it, method: CARD_METHOD };
    const match = state.tx.find((t) => !used.has(t.id) && sameCardTx(t, cand));
    if (match) { used.add(match.id); return { ...it, status: "dup" }; }
    // 같은 문자를 두 번 붙여넣은 경우
    if (it.source === "sms" && seenSms.some((t) => sameCardTx(t, cand) && t.time === cand.time)) return { ...it, status: "dup" };
    if (it.source === "sms") seenSms.push(cand);
    return { ...it, status: "new" };
  });
  state.pendingImport = rows;
  const counts = { new: 0, dup: 0, cancel: 0 };
  rows.forEach((r) => { if (r.status === "new") counts.new++; else if (r.status === "dup") counts.dup++; else if (r.status === "cancel") counts.cancel++; });

  const label = { new: "", dup: "이미 있음", cancel: "승인취소", "cancel-miss": "취소(원거래 없음)" };
  $("#import-preview").innerHTML = rows.length
    ? `<p><b>새 내역 ${counts.new}건</b> · 중복 ${counts.dup}건 · 취소 ${counts.cancel}건</p>
       <table>${rows.map((r) => `<tr class="${r.status === "dup" ? "dup" : r.status.startsWith("cancel") ? "cancel" : ""}">
         <td>${r.date.slice(5)}</td><td>${escapeHtml(r.merchant)}</td><td class="num">${won(r.amount)}</td><td>${label[r.status]}</td></tr>`).join("")}</table>`
    : `<p>인식된 결제 내역이 없어요.</p>`;
  $("#import-confirm").disabled = !(counts.new || counts.cancel);
}

function commitImport() {
  const rows = state.pendingImport || [];
  let added = 0, removed = 0, lastDate = null;
  for (const r of rows) {
    if (r.status === "new") {
      state.tx.push(touch({
        id: uid(), date: r.date, time: r.time || "", amount: r.amount, merchant: r.merchant,
        category: guessCategory(r.merchant), method: CARD_METHOD, memo: "",
        installment: r.installment || "", source: r.source,
      }));
      added++; lastDate = r.date;
    } else if (r.status === "cancel") {
      removeTx(r.targetId);
      removed++; lastDate = r.date;
    }
  }
  saveTx();
  if (lastDate) {
    const [y, m] = lastDate.split("-").map(Number);
    state.year = y; state.month = m - 1; state.selected = lastDate;
  }
  $("#import-dialog").close();
  render();
  toast(`${added}건 추가${removed ? `, ${removed}건 취소 반영` : ""}`);
}

// ---------- CSV / 백업 ----------
function csvCell(v) {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function download(name, content, type) {
  const blob = new Blob([content], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function exportCsv(y = state.year, m = state.month) {
  const list = monthTx(y, m).sort((a, b) => (a.date + (a.time || "")).localeCompare(b.date + (b.time || "")));
  if (!list.length) return toast("이 달에는 내역이 없어요");
  const header = ["날짜", "시간", "내용", "카테고리", "결제수단", "할부", "금액", "메모"];
  const lines = [header.join(",")];
  for (const t of list) {
    lines.push([t.date, t.time, t.merchant, t.category, t.method, t.installment, t.amount, t.memo].map(csvCell).join(","));
  }
  const card = list.filter(isCard).reduce((s, t) => s + t.amount, 0);
  const total = list.reduce((s, t) => s + t.amount, 0);
  lines.push("");
  lines.push(["", "", "삼성카드 합계", "", "", "", card, ""].join(","));
  lines.push(["", "", "현금·기타 합계", "", "", "", total - card, ""].join(","));
  lines.push(["", "", "총 합계", "", "", "", total, ""].join(","));
  // BOM을 붙여야 엑셀에서 한글이 깨지지 않는다
  download(`ledger_${ymOf(y, m)}.csv`, "\uFEFF" + lines.join("\r\n"), "text/csv;charset=utf-8");
  markExported(ymOf(y, m));
  renderBanner();
  toast(`${m + 1}월 CSV를 저장했어요`);
}

function backup() {
  download(`ledger_backup_${ymd(new Date())}.json`, JSON.stringify({ version: 1, tx: state.tx }, null, 2), "application/json");
}

async function restore(file) {
  try {
    const data = JSON.parse(await file.text());
    const list = Array.isArray(data) ? data : data.tx;
    if (!Array.isArray(list)) throw new Error();
    if (!confirm(`백업의 ${list.length}건으로 현재 내역을 바꿀까요?`)) return;
    // 백업에 없는 내역은 삭제로 기록해야 다른 기기에서도 사라진다
    const keep = new Set(list.map((t) => t.id));
    for (const t of state.tx) if (!keep.has(t.id)) removeTx(t.id);
    state.tx = list.map((t) => {
      delete state.deleted[t.id];
      return touch({ ...t });
    });
    saveTx();
    render();
    toast("복원했어요");
  } catch { toast("백업 파일을 읽지 못했어요"); }
}

// ---------- 이벤트 ----------
$("#calendar").addEventListener("click", (e) => {
  const cell = e.target.closest(".day[data-date]");
  if (!cell) return;
  if (state.selected === cell.dataset.date) return openTxDialog(null, cell.dataset.date);
  state.selected = cell.dataset.date;
  renderCalendar();
  renderDay();
});
$("#day-list").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-id]");
  if (li) openTxDialog(state.tx.find((t) => t.id === li.dataset.id));
});
$("#prev-month").onclick = () => shiftMonth(-1);
$("#next-month").onclick = () => shiftMonth(1);
$("#today-btn").onclick = () => {
  const n = new Date();
  state.year = n.getFullYear(); state.month = n.getMonth(); state.selected = ymd(n);
  render();
};
function shiftMonth(d) {
  const n = new Date(state.year, state.month + d, 1);
  state.year = n.getFullYear(); state.month = n.getMonth();
  state.selected = `${ymOf(state.year, state.month)}-01`;
  render();
}

$("#btn-add").onclick = () => openTxDialog(null, state.selected);
$("#day-add").onclick = () => openTxDialog(null, state.selected);
$("#btn-export").onclick = () => exportCsv();
$("#btn-backup").onclick = backup;
$("#restore-file").onchange = (e) => { if (e.target.files[0]) restore(e.target.files[0]); e.target.value = ""; };
$("#export-banner-close").onclick = () => {
  sessionStorageSet("bannerClosed", $("#export-banner-text").textContent);
  $("#export-banner").hidden = true;
};

document.querySelectorAll("[data-close]").forEach((b) => (b.onclick = () => b.closest("dialog").close()));

$("#btn-import").onclick = () => {
  state.pendingImport = null;
  $("#import-preview").innerHTML = "";
  $("#import-confirm").disabled = true;
  $("#import-file").value = "";
  $("#import-dialog").showModal();
};
document.querySelectorAll(".tab").forEach((tab) => (tab.onclick = () => {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
  document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = p.dataset.panel !== tab.dataset.tab));
}));
$("#import-file").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try { prepareImport(parseSheet(await readSheetRows(file))); }
  catch (err) { $("#import-preview").innerHTML = `<p class="cancel">${escapeHtml(err.message)}</p>`; }
};
$("#sms-parse").onclick = () => prepareImport(parseSms($("#sms-text").value));
$("#import-confirm").onclick = commitImport;

render();
