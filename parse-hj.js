"use strict";

// ---------- 현대카드·국민카드 알림 분석 (HJ) ----------
// 앱 푸시는 줄 순서가 카드사마다 달라서, 한 알림 안에서 금액·날짜·시간·가맹점을 각각 찾는다.
//
// 국민카드:  다우데이타 키오스크 4 / 20,000원 / 21:24 / 일시불 / 전표매입 / 알뜰폰 Hub Ⅱ카드(5019)
// 현대카드:  카카오T일반택시_0 / 51,400원 / 홍길동 님, 현대 the Green 승인 일시불, 10/4 22:45 / 누적2,324,737원
// 여러 건은 빈 줄로 구분한다. "국민카드"처럼 카드 이름만 있는 줄은 다음 알림들의 카드로 쓴다.

const HJ_CARD_HINTS = [
  ["현대카드", /현대\s*카드|현대\s*the|현대\s*[A-Z]|HYUNDAI|M포인트/i],
  ["국민카드", /국민|KB|Hub|노리|탄탄대로|청춘대로|알뜰폰/i],
];

function detectCard(text) {
  for (const [card, re] of HJ_CARD_HINTS) if (re.test(text)) return card;
  return null;
}

// 가맹점이 아닌 줄: 금액, 날짜·시간, 할부, 승인 안내, 이름, 카드 이름, 누적
function isMetaLine(l) {
  return /^-?[\d,]+\s*원(\s|$)/.test(l) // "9,500원 일시불" 처럼 금액으로 시작하는 줄
    || /^\d{1,2}\/\d{1,2}(\s+\d{1,2}:\d{2})?$/.test(l)
    || /^\d{1,2}:\d{2}$/.test(l)
    || /^(일시불|\d{1,2}\s*개월|할부|전표매입|승인|승인취소|취소|매입취소)$/.test(l)
    || /승인|님[,\s]|님$|누적|\[Web발신\]|카드\s*\(\d{3,4}\)|카드\d{3,4}/.test(l)
    || /^[가-힣]{1,2}\*[가-힣]{0,2}$/.test(l) // 김*호 같은 가린 이름
    || /^(현대|국민|KB국민|KB)\s*카드$/i.test(l);
}

function parseSmsHJ(text, fallbackDate) {
  const out = [];
  let lastCard = null;
  // 빈 줄 또는 [Web발신]에서 알림을 나눈다
  const blocks = text.replace(/\r/g, "").split(/\n\s*\n|(?=\[Web발신\])/);
  for (const block of blocks) {
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) continue;
    const body = lines.filter((l) => !/누적/.test(l)); // 누적 금액은 무시
    const joined = body.join("\n");
    const amtLine = joined.match(/(-?[\d,]{2,})\s*원/);
    if (!amtLine) { lastCard = detectCard(block) || lastCard; continue; } // "국민카드" 같은 제목 줄
    const dt = joined.match(/(\d{1,2})\/(\d{1,2})/);
    const tm = joined.match(/(\d{1,2}):(\d{2})/);
    const cancel = /취소/.test(joined);
    const inst = joined.match(/(\d{1,2})\s*개월/);
    const merchant = body.find((l) => !isMetaLine(l)) || "카드 결제";
    // 가맹점 이름(예: 현대백화점)으로 카드를 잘못 알지 않도록 나머지 줄에서만 찾는다
    const card = detectCard(lines.filter((l) => l !== merchant).join("\n"));
    out.push({
      date: dt ? guessYear(+dt[1], +dt[2]) : fallbackDate,
      noDate: !dt,
      time: tm ? `${pad(tm[1])}:${tm[2]}` : "",
      merchant: cleanMerchant(merchant) || "카드 결제",
      amount: (cancel ? -1 : 1) * Math.abs(parseAmount(amtLine[1])),
      installment: cancel ? "" : inst ? `${+inst[1]}개월` : /일시불/.test(joined) ? "일시불" : "",
      method: card || lastCard || CARD_METHOD,
      source: "sms",
    });
  }
  return out;
}
