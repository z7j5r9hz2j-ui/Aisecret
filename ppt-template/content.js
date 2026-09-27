// 보고서 내용. 실제 품질보고서 내용으로 이 파일만 바꾸면 같은 디자인으로 다시 생성됩니다.
// 아래 수치는 모두 레이아웃 확인용 예시 데이터입니다.
module.exports = {
  meta: {
    eyebrow: "QUALITY REPORT",
    // titleParts: 일부 단어를 파란 이탤릭으로 강조 (웹사이트의 "behind" 스타일)
    titleParts: [
      { text: "3분기 품질, " },
      { text: "데이터", accent: true },
      { text: "로\n증명합니다." },
    ],
    subtitle: "2026년 3분기 품질 현황과 개선 과제를 한눈에 정리했습니다.",
    date: "2026. 10",
    author: "품질관리팀",
    coverStats: [
      { value: "0.42%", label: "평균 불량률" },
      { value: "98.6%", label: "납기 준수율" },
      { value: "1.48", label: "공정능력 Cpk" },
    ],
  },

  contents: [
    { title: "핵심 품질 지표", desc: "3분기 주요 KPI 요약" },
    { title: "불량률 추이", desc: "월별 불량률과 목표 대비 현황" },
    { title: "불량 유형 분석", desc: "유형별 건수·비중·조치 상태" },
    { title: "개선 과제", desc: "개선 전후 비교와 4분기 계획" },
  ],

  section: { number: "01", eyebrow: "SECTION 01", title: "3분기 품질 현황", desc: "핵심 지표와 월별 추이를 중심으로 살펴봅니다." },

  kpis: [
    { value: "0.42%", label: "평균 불량률", delta: "▼ 0.18%p", good: true },
    { value: "7건", label: "고객 클레임", delta: "▼ 3건", good: true },
    { value: "1.48", label: "공정능력 Cpk", delta: "▲ 0.12", good: true },
    { value: "98.6%", label: "납기 준수율", delta: "▼ 0.4%p", good: false },
  ],

  trend: {
    labels: ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월"],
    actual: [0.71, 0.66, 0.63, 0.58, 0.55, 0.60, 0.47, 0.43, 0.36],
    target: [0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50],
    insights: [
      { icon: "LuTrendingDown", title: "3개월 연속 하락", desc: "7월 이후 목표(0.50%) 이하 유지" },
      { icon: "LuTarget", title: "9월 최저치 0.36%", desc: "연초 대비 49% 개선" },
      { icon: "LuGauge", title: "6월 일시 상승", desc: "신규 금형 교체 초기 불량 영향" },
    ],
  },

  defects: {
    header: ["불량 유형", "건수", "비중", "전분기 대비", "조치 상태"],
    rows: [
      ["치수 불량", "42", "34%", "▼ 12", "완료"],
      ["외관 스크래치", "31", "25%", "▼ 5", "진행 중"],
      ["조립 누락", "24", "19%", "▲ 3", "진행 중"],
      ["도장 불균일", "16", "13%", "▼ 8", "완료"],
      ["기타", "11", "9%", "–", "모니터링"],
    ],
    note: "합계 124건 · 전분기 대비 22건 감소",
  },

  compare: {
    title: "검사 공정 자동화 전후",
    before: { label: "BEFORE", title: "수작업 육안 검사", items: ["검사 시간 개당 45초", "검사자별 판정 편차 발생", "불량 유출 월 평균 4건"] },
    after: { label: "AFTER", title: "비전 검사 자동화", items: ["검사 시간 개당 8초", "판정 기준 표준화", "불량 유출 월 평균 1건"] },
  },

  initiatives: [
    { icon: "LuBot", eyebrow: "AUTOMATION", title: "비전 검사 확대", desc: "2라인까지 자동 검사를 확대해 외관 불량 유출을 차단합니다." },
    { icon: "LuWrench", eyebrow: "PROCESS", title: "금형 관리 표준화", desc: "교체 후 초기 100개 전수 검사로 초기 불량을 줄입니다." },
    { icon: "LuUsers", eyebrow: "PEOPLE", title: "작업자 교육", desc: "조립 누락 방지를 위해 체크리스트 기반 교육을 진행합니다." },
  ],

  closing: {
    title: "감사합니다.",
    desc: "보고서 관련 문의는 품질관리팀으로 연락 주세요.",
    primary: "문의하기",
    secondary: "상세 자료 요청",
  },
};
