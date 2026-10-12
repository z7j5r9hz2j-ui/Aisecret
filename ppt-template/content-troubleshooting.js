// 설비 문제 해결 경과 보고 — 내용 파일
// 실제 설비·가설·실행 내용으로 이 파일만 바꾸면 같은 디자인으로 다시 생성됩니다.
// 아래 내용은 모두 레이아웃 확인용 예시입니다.
//
// status 값: "rejected"(기각) | "partial"(부분 효과) | "confirmed"(원인 확인) | "fixed"(대책 완료)
module.exports = {
  meta: {
    eyebrow: "TROUBLESHOOTING REPORT",
    titleParts: [
      { text: "3호기 스핀들 과열,\n" },
      { text: "원인", accent: true },
      { text: "을 찾기까지" },
    ],
    subtitle: "6주간 세운 가설 7개와 검증·실행 결과를 시간 순서로 정리했습니다.",
    date: "2026. 10",
    author: "설비보전팀",
    coverStats: [
      { value: "12 → 0회", label: "주간 알람 정지" },
      { value: "6주", label: "문제 해결 기간" },
      { value: "7개", label: "검증한 가설" },
    ],
  },

  problem: {
    equipment: "CNC 가공기 3호기",
    rows: [
      { icon: "LuTriangleAlert", label: "현상", text: "가공 중 스핀들 과열 알람(AL-2041)으로 설비 정지" },
      { icon: "LuCalendarClock", label: "발생 시점", text: "8월 첫째 주부터 주 10회 이상 반복 발생" },
      { icon: "LuFactory", label: "영향", text: "정지 1회당 평균 25분 · 후속 공정 대기 발생" },
    ],
    stats: [
      { value: "12회", label: "주간 최대 정지" },
      { value: "38h", label: "누적 정지 시간" },
      { value: "4.1%", label: "가동률 하락" },
    ],
  },

  // 시간 순서대로 나열한 가설·실행 아이템
  items: [
    { id: "H1", date: "08/04", hypothesis: "절삭유 농도 저하", action: "농도 5% → 8% 보정", result: "알람 빈도 변화 없음", status: "rejected" },
    { id: "H2", date: "08/08", hypothesis: "냉각 팬 필터 막힘", action: "필터 교체 및 청소", result: "주 12 → 9회, 2주 후 재발", status: "partial" },
    { id: "H3", date: "08/14", hypothesis: "스핀들 베어링 마모", action: "진동 측정(FFT 분석)", result: "결함 주파수 미검출", status: "rejected" },
    { id: "H4", date: "08/20", hypothesis: "하절기 실내 온도 상승", action: "온도 로거 2주 기록", result: "알람과 상관 낮음 (r=0.21)", status: "rejected" },
    { id: "H5", date: "08/27", hypothesis: "칠러 냉매 부족", action: "압력 점검 · 냉매 보충", result: "주 10 → 6회, 완전 해소 안 됨", status: "partial" },
    { id: "H6", date: "09/03", hypothesis: "칠러 순환 펌프 성능 저하", action: "냉각수 유량 측정", result: "정격 대비 62%로 저하 확인", status: "confirmed" },
    { id: "H7", date: "09/10", hypothesis: "펌프 교체로 유량 회복", action: "펌프 교체 · 유량 알람 추가", result: "4주 연속 정지 0회", status: "fixed" },
  ],

  // 핵심 가설 상세 (원인 확인된 가설)
  deepDive: {
    id: "H6",
    title: "칠러 순환 펌프 성능 저하",
    steps: [
      { label: "가설", text: "냉각수 유량이 부족해 스핀들 열을 충분히 빼내지 못한다" },
      { label: "검증 방법", text: "초음파 유량계로 칠러 출구 유량을 3일간 측정" },
      { label: "결과", text: "평균 24.8 L/min, 정격 40 L/min 대비 62%" },
      { label: "판단", text: "임펠러 마모로 인한 유량 저하가 근본 원인" },
    ],
    evidence: [
      { value: "40", unit: "L/min", label: "정격 유량" },
      { value: "24.8", unit: "L/min", label: "측정 유량 (62%)" },
      { value: "39.6", unit: "L/min", label: "펌프 교체 후" },
    ],
  },

  // 주간 알람 정지 횟수 (대책 효과)
  trend: {
    labels: ["8/4", "8/11", "8/18", "8/25", "9/1", "9/8", "9/15", "9/22", "9/29", "10/6"],
    values: [12, 9, 11, 10, 6, 7, 1, 0, 0, 0],
    fixFrom: 6, // 이 인덱스부터 "대책 후" 색상
    markers: [
      { week: "8/11", text: "H2 필터 교체" },
      { week: "9/1", text: "H5 냉매 보충" },
      { week: "9/15", text: "H7 펌프 교체" },
    ],
  },

  rootCause: {
    title: "칠러 순환 펌프 임펠러 마모",
    desc: "냉각수 유량이 정격의 62%까지 떨어져 고부하 가공 시 스핀들 온도가 알람 기준을 넘었습니다. 필터·냉매 조치는 증상을 일부 줄였을 뿐 원인은 아니었습니다.",
    actions: [
      { icon: "LuWrench", tag: "즉시 조치", title: "순환 펌프 교체", desc: "09/10 교체 완료, 유량 39.6 L/min 회복", done: true },
      { icon: "LuBellRing", tag: "재발 방지", title: "유량 저하 알람 추가", desc: "정격 80% 미만 시 사전 경보", done: true },
      { icon: "LuClipboardCheck", tag: "관리 표준", title: "유량 점검 PM 항목 추가", desc: "월 1회 유량 측정을 예방보전 항목에 반영", done: false },
    ],
  },

  lessons: [
    { icon: "LuGauge", eyebrow: "MEASURE FIRST", title: "측정 먼저, 교체는 나중", desc: "유량을 처음부터 측정했다면 3주를 단축할 수 있었습니다." },
    { icon: "LuChartLine", eyebrow: "PARTIAL ≠ ROOT", title: "부분 효과에 주의", desc: "증상이 줄어든 조치(H2, H5)를 원인으로 오판하지 않도록 기록했습니다." },
    { icon: "LuNetwork", eyebrow: "SCALE OUT", title: "동일 설비 확대 점검", desc: "같은 칠러를 쓰는 1·2·5호기 유량을 10월 중 점검합니다." },
  ],

  closing: {
    title: "감사합니다.",
    desc: "추가 데이터나 측정 기록이 필요하시면 설비보전팀으로 요청해 주세요.",
    primary: "문의하기",
    secondary: "측정 데이터 요청",
  },
};
