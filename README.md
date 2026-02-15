# MyAgents

AI-powered automation hub for spine neurosurgeon academic workflows.

Built on [OpenCode](https://opencode.ai) with multi-model orchestration (Claude + GPT + Gemini).

## Workflows

### 1. Editor/Reviewer Automation
Automate peer review and editorial tasks for academic journals.

**Commands:**
- `/review-paper` — Full peer review pipeline (PDF → Korean summary → structured review)
- `/editor-decision` — Generate editor decision letter
- `/quick-screen` — 1-minute initial paper screening
- `/stats-check` — Statistics-only focused review

**How to use:**
1. Place PDF in `papers/inbox/`
2. Open OpenCode in this project
3. Run the appropriate slash command

### 2. Journal Alert System
Automated paper collection from spine journals → Notion DB with interest classification.

**Supported Journals:**
- The Spine Journal
- Spine
- Journal of Neurosurgery: Spine
- Neurospine
- European Spine Journal
- Global Spine Journal

**Quick start:**
```bash
cd journal-alert

# Fetch papers
python fetch_papers.py --all --year 2026

# Push to Notion
export NOTION_TOKEN='ntn_...'
python push_to_notion.py --latest

# Email notification
export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'
python notify_email.py --latest
```

**Auto-classification:**
- 🔴 Must-read: endoscopy, biportal, UBE, AI/deep learning
- 🟡 Interested: MIS, stenosis, fusion, cervical, robot, education
- ⚪ Reference: other

## Agents

| Agent | Role |
|-------|------|
| paper-analyzer | PDF parsing, structure extraction |
| methods-reviewer | Methodology & statistics critique |
| literature-checker | Reference verification |
| comment-writer | Review comment synthesis |
| decision-drafter | Editor decision letters |

## Setup

### Prerequisites
- Python 3.10+
- [OpenCode](https://opencode.ai) installed
- Notion Integration token (for journal alerts)
- Gmail App Password (for email notifications)

### Environment Variables
```bash
# Required for journal-alert
export NOTION_TOKEN='ntn_...'
export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'
```

### Configuration
Edit `journal-alert/config.json` to customize:
- Target journals
- Interest keywords
- Category rules
- Notion database ID

## License
Private — personal use only.
