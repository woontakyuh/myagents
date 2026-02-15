# 📋 리뷰 보고서: AI-Assisted Assessment of Cervical Fusion on F/E Radiographs

**날짜:** 2026-02-15 | **저널:** Neurospine | **유형:** Retrospective diagnostic study | **LoE:** III

---

## 한줄 요약
ACDF 후 F/E 방사선에서 AI가 interspinous distance를 측정하여 fusion 판정 → 기존 1mm rule 대신 0.45mm cut-off 제안. 그러나 AI specificity 0.11, AUC 0.49로 실제 진단 성능은 random 수준.

---

## 🔴 Major Issues (반드시 지적)

**1. AI 진단 성능이 random 수준**
- AUC 0.49 = 동전 던지기와 동일
- Specificity 0.11 = non-fusion 89% 오분류
- 그런데 제목/초록은 AI가 우월한 것처럼 기술 → misleading

**2. 극심한 class imbalance**
- Fusion 93명 vs Non-fusion 9명
- 9명으로 specificity, ROC 산출은 통계적으로 불안정
- Youden's J 기반 cut-off도 이 불균형에 의해 편향

**3. AI-Human 일치도 사실상 0**
- CCC 0.06-0.08 = agreement 거의 없음
- AI와 사람이 근본적으로 다른 것을 측정하고 있을 가능성 → 논문에서 이 해석 부재

**4. 외부 검증 없음**
- 단일기관, training data 출처/규모 미기재
- 최소한 pilot/feasibility study로 프레이밍 필요

## 🟡 Minor Issues

**5.** 21년간 데이터 수집 (2003-2024) → 수술기법, 영상장비, implant 변화 미고려
**6.** CT fusion 판독 inter-observer reliability 미보고 (reference standard 신뢰성)
**7.** 0.45mm cut-off → 일반 방사선에서 sub-millimeter 정밀도 현실적으로 불가능
**8.** Multiple comparison correction 미시행

## ✅ 강점
- 중요한 임상 질문 (F/E radiograph의 fusion 판정 한계)
- Human rater blinding 적절
- CT를 reference standard로 사용
- AI 한계를 Discussion에서 일부 인정

---

## 판정

| 항목 | 평가 |
|------|------|
| **추천** | **Major Revision** |
| **확신도** | High |
| **핵심 요구** | AI 성능 해석 재구성 (현재 misleading), class imbalance 한계 명시, 외부 검증 또는 pilot study로 재포지셔닝 |

---
*AI 보조 리뷰 초안 — 최종 제출 전 반드시 본인 검토 필요*
