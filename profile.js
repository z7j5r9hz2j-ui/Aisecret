"use strict";

// ---------- 사용자별 설정 ----------
// 같은 코드로 두 가계부를 운영한다. 주소가 …/hj/ 이면 HJ, 아니면 NK.
// 둘은 같은 사이트(origin)라 브라우저 저장소를 함께 쓰므로 저장 키를 서로 다르게 둔다.
const PROFILES = {
  nk: {
    id: "nk",
    title: "NK's Expense Tracker",
    keyPrefix: "ledger", // 기존 데이터를 그대로 쓰기 위해 원래 키 유지
    cards: ["삼성카드"],
    cardLabel: "삼성카드",
    methods: ["현금", "계좌이체", "삼성카드", "기타카드"],
    categories: [
      "식비", "카페·간식", "교통", "쇼핑", "생활·마트", "주거·통신",
      "보험", "의료·건강", "문화·여가", "교육", "경조사·선물", "기타",
    ],
    extraRules: [],
    chartCats: ["식비", "카페·간식", "교통", "쇼핑", "생활·마트", "주거·통신", "보험"],
    syncRepoName: "ledger-data",
    importLabel: "삼성카드 불러오기",
    importTitle: "삼성카드 내역 불러오기",
    excelHint: "삼성카드 홈페이지 또는 앱 → <b>이용내역 조회</b> → <b>엑셀 다운로드</b>로 받은 파일을 올리세요. (.xlsx, .xls, .csv)",
    smsHint: "삼성카드 승인 문자나 알림을 여러 개 한꺼번에 붙여넣어도 됩니다. 취소 문자는 마이너스 금액으로 기록돼 합계에서 빠져요. 자동결제 문자와 후불교통 월 합계 문자(그 달 마지막 날로 기록)도 인식해요.",
    smsPlaceholder: "[Web발신]\n삼성1234승인\n홍*동\n12,300원 일시불\n09/25 12:34 스타벅스\n누적1,234,567원",
  },
  hj: {
    id: "hj",
    title: "HJ's Expense Tracker",
    keyPrefix: "hj.ledger",
    cards: ["현대카드", "국민카드"],
    cardLabel: "카드",
    methods: ["현금", "계좌이체", "현대카드", "국민카드", "기타카드"],
    categories: [
      "식비", "카페·간식", "교통", "쇼핑", "생활·마트", "주거·통신", "정기구독",
      "보험", "의료·건강", "문화·여가", "교육", "경조사·선물", "기타",
    ],
    // OTT·음악·멤버십 같은 정기 결제
    extraRules: [
      ["정기구독", /넷플릭스|NETFLIX|유튜브|YOUTUBE|구글플레이|GOOGLE\s*PLAY|티빙|TVING|웨이브|WAVVE|왓챠|WATCHA|디즈니|DISNEY|쿠팡플레이|쿠팡와우|와우멤버십|APPLE\.COM|ITUNES|아이클라우드|ICLOUD|스포티파이|SPOTIFY|멜론|지니뮤직|플로|FLO|밀리의서재|리디|라프텔|네이버플러스|정기결제|구독/i],
    ],
    chartCats: ["식비", "카페·간식", "교통", "쇼핑", "생활·마트", "주거·통신", "정기구독"],
    syncRepoName: "hj-ledger-data",
    importLabel: "카드 내역 불러오기",
    importTitle: "카드 내역 불러오기",
    excelHint: "현대카드·국민카드 홈페이지 또는 앱 → <b>이용내역 조회</b> → <b>엑셀 다운로드</b>로 받은 파일을 올리고, 어느 카드인지 고르세요. (.xlsx, .xls, .csv)",
    smsHint: "현대카드·국민카드 승인 문자나 알림을 붙여넣으세요. 여러 건은 빈 줄로 띄워 주세요. 카드가 다르게 잡히면 미리보기에서 바꿀 수 있어요. 취소는 마이너스 금액으로 기록돼요.",
    smsPlaceholder: "카카오T일반택시_0\n51,400원\n홍길동 님, 현대 the Green 승인 일시불, 10/4 22:45\n누적2,324,737원\n\n다우데이타 키오스크 4\n20,000원\n21:24\n일시불\n전표매입\n알뜰폰 Hub Ⅱ카드(5019)",
  },
};

const PROFILE = /\/hj\/(index\.html)?$/.test(location.pathname) ? PROFILES.hj : PROFILES.nk;
