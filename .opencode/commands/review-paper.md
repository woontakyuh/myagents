---
description: Full peer review pipeline - PDF to structured review with Korean summary
---

# Review Paper

논문 PDF를 리뷰한다.

## 워크플로우

### Phase 1: 한글본 (즉시 전달)
1. `papers/inbox/`에서 최신 PDF 찾기
2. PDF 텍스트 추출
3. **한글 요약본** → `papers/reviews/{date}_{name}_summary_ko.md`
   - 1-2페이지 한글 요약 (연구목적, 방법, 결과, 결론)
   - 핵심 수치 포함
4. **한글 전체번역본** → `papers/reviews/{date}_{name}_full_ko.md`
   - 원본 섹션 구조 유지, Table은 마크다운, Figure는 캡션만
   - References는 원문 유지
5. **즉시 사용자에게 알림** — "한글본 준비됨, Phase 2 진행 중"

### Phase 2: 리뷰 (한글본 전달 후 진행)
6. 논문 분석 (study design, stats, references)
7. **리뷰 보고서 1개만 생성** → `papers/reviews/{date}_{name}_review.md`
   - AGENTS.md의 "리뷰 보고서 포맷" 엄격히 따를 것
   - 한글, A4 1-2장, Major/Minor/강점/판정
   - examples/review-example-concise.md 참조

## ⚡ 규칙
- Phase 1 먼저 완료 후 Phase 2
- 중간 파일 (analysis.md, methods.md, literature.md) 만들지 않음
- 최종 산출물 = summary_ko + full_ko + review 총 3개만
- 리뷰는 반드시 한글, 100줄 이내
