---
description: 저널 논문 수집 및 Notion DB 업데이트
---

# Journal Alert

저널 논문 수집 및 Notion DB 업데이트.

## 권장 워크플로우 (Incremental)

```bash
cd journal-alert

# 1. 최초 1회: 기존 data/에서 state.json 초기화
python fetch_papers.py --init-state

# 2. 신규 논문 수집 (마지막 실행 이후 PubMed 인덱싱 기준)
python fetch_papers.py --incremental

# 3. Notion에 Push
python push_to_notion.py --latest

# 4. 이메일 알림
python notify_email.py --latest
```

### 원커맨드 (수집 + Push + 이메일)
```bash
cd journal-alert && python fetch_papers.py --incremental && python push_to_notion.py --latest && python notify_email.py --latest
```

## Incremental 모드 설명

- `state.json`에 마지막 실행 날짜 + 처리된 PMID 목록 저장
- PubMed `edat` (Entrez date = 인덱싱일) 기준으로 새 논문만 조회
- 1일 overlap으로 누락 방지 + PMID 기반 dedup으로 중복 제거
- state.json 없으면 자동으로 최근 14일 조회

## 기존 모드 (전체 연도 수집 — 초기 세팅용)

```bash
cd journal-alert
python fetch_papers.py --all --year 2026  # 모든 저널, 2026년 전체
python fetch_papers.py --days 30          # 최근 30일
python fetch_papers.py --journal "Eur Spine J" --year 2026  # 특정 저널
```

## 자동 분류 규칙

### 관심도
- 🔴 필독: endoscopy, biportal, UBE, AI/deep learning 관련
- 🟡 관심: MIS, stenosis, fusion, cervical, robot 등
- ⚪ 참고: 기타 (Letter, Erratum 포함)

### Category
config.json의 `category_rules`에 따라 자동 분류:
- Endoscopy, AI/ML, MIS, Lumbar, Cervical, Deformity, Outcome, Education 등

## 설정 변경
- 저널 추가/제거: `config.json` → `journals`
- 관심 키워드: `config.json` → `interest_keywords`
- 카테고리 규칙: `config.json` → `category_rules`
- Notion DB ID: `config.json` → `notion_database_id`

## 주의사항
- PubMed API rate limit: 초당 3회 (자동 처리됨)
- Notion API rate limit: 초당 3회 (자동 처리됨)
- 중복 논문은 PMID + DOI/Title로 자동 스킵
- NOTION_TOKEN은 환경변수 또는 config.json에 설정
- Notion DB 조회 실패 시 push가 중단됨 (대량 중복 삽입 방지)
