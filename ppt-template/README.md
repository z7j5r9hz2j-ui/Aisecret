# Veebar Tech PPT 템플릿

veebartech.ca 디자인(색상·그라디언트·둥근 카드·알약형 버튼·아이콘 타일)을 적용한 PowerPoint 생성기입니다.

```bash
cd ppt-template
npm install
npm run build   # → VeebarTech_Quality_Report.pptx
```

- `content.js` — 보고서 내용. 실제 품질보고서 내용으로 이 파일만 바꾸면 같은 디자인으로 다시 만들어집니다 (현재 수치는 예시).
- `build.js` — 디자인 토큰과 슬라이드 레이아웃.
- 슬라이드 마스터 3종(`VEEBAR_LIGHT`, `VEEBAR_CONTENT`, `VEEBAR_GRADIENT`)이 포함되어 PowerPoint의 "새 슬라이드"에서도 쓸 수 있습니다.

| 토큰 | 값 | 용도 |
|---|---|---|
| ink | `#0A1722` | 헤드라인, 다크 버튼 |
| blue | `#024996` | 프라이머리, eyebrow, 강조 |
| teal | `#1C7A8C` | 그라디언트 끝, 포인트 |
| slate | `#5A6B7B` | 본문 |
| tint | `#EEF4F9` | pill·아이콘 타일 배경 |
| gradient | `#024996 → #1B788C` | 섹션·표지 카드 |
