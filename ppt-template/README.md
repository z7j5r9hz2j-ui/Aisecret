# Veebar Tech PPT 템플릿

veebartech.ca 디자인(색상·그라디언트·둥근 카드·알약형 버튼·아이콘 타일)을 적용한 PowerPoint 생성기입니다.

```bash
cd ppt-template
npm install
npm run build                  # 품질 보고서 → VeebarTech_Quality_Report.pptx
npm run build:troubleshooting  # 설비 문제 해결 경과 보고 → VeebarTech_Troubleshooting_Report.pptx
```

| 덱 | 내용 파일 | 생성 스크립트 |
|---|---|---|
| 품질 보고서 | `content.js` | `build.js` |
| 설비 문제 해결 경과 보고 (가설 → 실행 → 결과, 시간순) | `content-troubleshooting.js` | `build-troubleshooting.js` |

- 내용 파일만 바꾸면 같은 디자인으로 다시 만들어집니다 (현재 수치는 모두 예시).
- 문제 해결 보고서의 `items` 판정 값: `rejected`(기각) · `partial`(부분 효과) · `confirmed`(원인 확인) · `fixed`(대책 완료).
- `lib.js` — 디자인 토큰, 공통 컴포넌트, 슬라이드 마스터.
- 슬라이드 마스터 3종(`VEEBAR_LIGHT`, `VEEBAR_CONTENT`, `VEEBAR_GRADIENT`)이 포함되어 PowerPoint의 "새 슬라이드"에서도 쓸 수 있습니다.

| 토큰 | 값 | 용도 |
|---|---|---|
| ink | `#0A1722` | 헤드라인, 다크 버튼 |
| blue | `#024996` | 프라이머리, eyebrow, 강조 |
| teal | `#1C7A8C` | 그라디언트 끝, 포인트 |
| slate | `#5A6B7B` | 본문 |
| tint | `#EEF4F9` | pill·아이콘 타일 배경 |
| gradient | `#024996 → #1B788C` | 섹션·표지 카드 |
