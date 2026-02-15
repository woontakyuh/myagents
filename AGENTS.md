# MyAgents - Spine Neurosurgeon AI Workspace

## Overview
AI-powered automation hub for spine neurosurgeon academic workflows.
OpenCode native project — multi-model orchestration (Claude + GPT + Gemini).

## Owner Profile
- **Role**: Spine neurosurgeon, journal editor, peer reviewer, AI researcher
- **Specialties**: UBE surgery, spine endoscopy education, medical AI
- **Research focus**: AI applications in spine surgery, computer vision for surgical navigation
- **Languages**: Korean (primary), English (academic writing)

## Workflow 1: Editor/Reviewer Automation

### Pipeline Overview
```
PDF 투입
  ↓ Phase 1 (즉시 전달 — 사용자가 먼저 읽을 수 있도록)
  ├→ 한글 요약본 (papers/reviews/{date}_{name}_summary_ko.md)
  ├→ 한글 전체번역본 (papers/reviews/{date}_{name}_full_ko.md)
  │     - 원본 섹션 구조 완전 유지 (Abstract→Intro→Methods→Results→Discussion)
  │     - Table은 마크다운 테이블로 재현
  │     - Figure는 캡션만 번역, 위치 표시: [Figure 1 위치]
  │     - 참고문헌은 번역하지 않음 (원문 유지)
  │
  ↓ Phase 2 (백그라운드 — 사용자가 한글본 읽는 동안 진행)
  Paper Analyzer → Methods Reviewer + Literature Checker (parallel) → Comment Writer
  ↓
  리뷰 초안 (papers/reviews/{date}_{name}_review.md)
  ↓ (필요시)
  Decision Letter (papers/decisions/)
```

### Phase 1 속도 규칙
- 한글 요약은 **채팅에 직접 출력**할 것 (파일 저장 X, 30초 내)
- PDF 텍스트 추출 → 즉시 요약 출력 → 그 다음 번역 파일 저장 → 그 다음 리뷰
- Phase 1에서는 분석/판단 금지. 번역만. 빠르게.
- 완벽한 번역보다 빠른 전달이 우선.

### How to Use
1. Place PDF in `papers/inbox/`
2. Run: `/review-paper`
3. → 한글 요약/번역이 먼저 나옴 (1-2분)
4. → 사용자는 한글본으로 직접 리뷰 시작
5. → AI 리뷰가 나중에 완료됨 (추가 3-5분)
6. → 본인 리뷰 + AI 리뷰 합쳐서 최종본

### Key Rules
- **Phase 1 → Phase 2 순서를 반드시 지킬 것** — 한글본 먼저!
- All review comments must be **constructive and specific** — cite exact sections/pages
- Statistical critiques must reference specific test used vs. appropriate alternatives
- Never fabricate references — only cite papers that actually exist
- Decision letters must follow journal-standard format

## Workflow 2: Journal Alert System

### 개요
관심 저널의 새 논문을 자동 수집하고 Notion DB에 관심도별로 분류하여 push.

### 사용법
```bash
# 환경변수 설정 (필수)
export NOTION_TOKEN='ntn_...'
export OPENAI_API_KEY='sk-...'       # 한글 요약/번역용 (또는 ANTHROPIC_API_KEY)
export GMAIL_APP_PASSWORD='xxxx ...' # 이메일 알림용

# 논문 수집
cd journal-alert
python fetch_papers.py --all --year 2026   # 전체 저널
python fetch_papers.py --days 30           # 최근 30일

# Notion에 Push (LLM으로 한글 요약 자동 생성)
python push_to_notion.py --latest

# 이메일 알림
python notify_email.py --latest --dry-run  # 미리보기
python notify_email.py --latest            # 실제 발송

# 원커맨드
cd journal-alert && python fetch_papers.py --all --year 2026 && python push_to_notion.py --latest
```

### LLM 설정 (한글 요약/번역)
config.json의 `llm` 섹션에서 프로바이더와 모델 설정 가능.
- `provider`: `"auto"` (환경변수 기반 자동 선택), `"openai"`, `"anthropic"`, `"claude-cli"`
- 환경변수: `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY`
- LLM 미설정 시에도 수집/push는 정상 동작 (요약/번역만 생략)

### 자동 분류
- 🔴 필독: endoscopy, biportal, UBE, AI/deep learning
- 🟡 관심: MIS, stenosis, fusion, cervical, robot, education
- ⚪ 참고: 기타

### 저널 목록 (config.json)
- The Spine Journal
- Spine
- J Neurosurg Spine
- Neurospine
- European Spine Journal
- Global Spine Journal

### Notion DB
- 컬럼: Title, Publication Date, Journal Name, Author, Abstract, DOI, 관심도, 읽음, Keywords, Category, Type, Summary, Vol, Issue

---

## Project Structure
```
myagents/
├── AGENTS.md                    # This file — project instructions
├── .opencode/
│   ├── agents/                  # Agent definitions (OpenCode native)
│   │   ├── paper-analyzer.md    # PDF parsing, structure extraction
│   │   ├── methods-reviewer.md  # Methodology & statistics review
│   │   ├── literature-checker.md # Reference verification
│   │   ├── comment-writer.md    # Review comment drafting
│   │   └── decision-drafter.md  # Editor decision letters
│   ├── commands/                # Slash commands
│   │   ├── review-paper.md      # Full peer review pipeline
│   │   ├── editor-decision.md   # Editor decision workflow
│   │   ├── quick-screen.md      # Fast initial screening
│   │   ├── stats-check.md       # Statistics-only review
│   │   └── journal-alert.md     # 저널 논문 수집/Notion push
│   └── skills/                  # Reusable skills (future)
├── journal-alert/               # 저널 알림 시스템
│   ├── fetch_papers.py          # PubMed E-utilities 수집
│   ├── push_to_notion.py        # Notion DB push
│   ├── notify_email.py          # 이메일 알림
│   ├── update_existing.py       # 기존 페이지 업데이트
│   ├── daily_check.sh           # cron 자동 실행
│   ├── config.json              # 저널, 키워드, Notion 설정
│   └── data/                    # 수집된 JSON (자동 생성)
├── papers/
│   ├── inbox/                   # Drop PDFs here
│   ├── reviews/                 # Generated review outputs
│   └── decisions/               # Generated decision letters
├── templates/
│   ├── review-template.md       # Structured review format
│   └── decision-template.md     # Decision letter format
├── examples/
│   └── review-example-concise.md # 리뷰 보고서 예시
└── scripts/                     # Helper scripts
```

## Agent Communication Protocol
- Agents pass data via markdown files in `papers/reviews/`
- File naming: `{date}_{paper-short-name}_{stage}.md`
- Example: `2026-02-15_kim-ube-outcomes_analysis.md`

## Quality Standards
- Spine surgery domain knowledge is critical — check anatomical accuracy
- For UBE/endoscopy papers: verify portal placement descriptions, instrument specifications
- Statistical review must check: sample size justification, appropriate tests, effect sizes, p-value interpretation
- Methodology review: study design, control groups, blinding, follow-up duration
- Level of Evidence assessment required for all clinical studies

## 출력 규칙 (CRITICAL)

### 언어: 한글
- 모든 리뷰 산출물은 **한글**로 작성
- 의학용어는 영문 병기: "추간판 탈출증 (disc herniation)"
- 통계 용어도 영문 병기: "민감도 (sensitivity)"

### 분량: 짧고 핵심만
- 최종 리뷰 보고서: **A4 1-2장 이내** (마크다운 100줄 이내)
- 중간 분석 파일 (analysis, methods, literature): 만들지 않음
- **파이프라인 5단계를 거치되, 최종 산출물은 하나의 통합 리뷰 보고서만**

### 리뷰 보고서 포맷 (고정)
```
# 리뷰 보고서: {제목}
날짜 | 저널 | 유형 | LoE

## 한줄 요약 (2-3문장)

## 🔴 Major Issues (3-5개, 각 2-3줄)
## 🟡 Minor Issues (3-5개, 각 1줄)
## ✅ 강점 (3-4개)

## 판정 (표)
추천 | 확신도 | 핵심 요구사항
```
- examples/review-example-concise.md 참조

### 하지 말 것
- 500줄짜리 장황한 analysis 만들지 말 것
- 체크리스트 형태 ([x] Present, [x] Adequate) 나열 금지
- 원문 전체 추출/복사 금지 (Abstract, Methods 통째로 넣지 말 것)
- 영어로 작성 금지
