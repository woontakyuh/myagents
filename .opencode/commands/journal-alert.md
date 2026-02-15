---
description: 저널 논문 수집 및 Notion DB 업데이트
---

# Journal Alert

저널 논문 수집 및 Notion DB 업데이트.

## 워크플로우

### 1단계: 논문 수집
```bash
cd journal-alert
python fetch_papers.py                    # 기본: The Spine Journal, 올해
python fetch_papers.py --year 2026        # 특정 연도
python fetch_papers.py --days 30          # 최근 30일
python fetch_papers.py --all --year 2026  # 모든 저널, 2026년
python fetch_papers.py --journal "Eur Spine J" --year 2026  # 특정 저널
```

### 2단계: Notion에 Push
```bash
export NOTION_TOKEN='ntn_...'  # 또는 config.json에 설정
python push_to_notion.py --latest    # 가장 최근 수집 파일
python push_to_notion.py --all       # data/ 전체 파일
```

### 원커맨드 (수집 + Push)
```bash
cd journal-alert && python fetch_papers.py --all --year 2026 && python push_to_notion.py --latest
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
- 중복 논문은 DOI/Title로 자동 스킵
- NOTION_TOKEN은 환경변수 또는 config.json에 설정
