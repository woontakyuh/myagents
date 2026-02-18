# Schedule Agent MCP Server

Notion Schedule DB + Google Calendar + Dropbox 통합 일정관리 MCP Server.
Claude Desktop에서 자연어로 일정을 추가/조회/수정합니다.

## Tools

| Tool | 기능 |
|------|------|
| `list_schedules` | 일정 목록 조회 (날짜/상태/분류 필터) |
| `search_schedules` | 이름으로 일정 검색 |
| `get_schedule` | 특정 일정 상세 조회 |
| `add_schedule` | 일정 추가 (Notion + GCal + Dropbox 폴더 생성) |
| `update_schedule` | 기존 일정 수정 |
| `create_event_folder` | Dropbox 폴더만 단독 생성 |

## 환경 변수

`~/.journal_alert_env` 파일에 아래 값이 있어야 합니다:

```
export NOTION_TOKEN=ntn_xxx
```

## 설치 (각 기기에서 최초 1회)

### macOS (맥북에어, 맥미니)

```bash
# 1. 코드 받기
git clone https://github.com/woontakyuh/myagents.git ~/Projects/myagents

# 2. 의존성 설치 & 빌드
cd ~/Projects/myagents/schedule-agent
bun install && bun run build

# 3. Claude Desktop 설정
# ~/Library/Application Support/Claude/claude_desktop_config.json 에 추가:
```

```json
"schedule-agent": {
  "command": "/usr/local/bin/node",
  "args": ["/Users/{username}/Projects/myagents/schedule-agent/build/index.js"]
}
```

```bash
# 4. Claude Desktop 완전 종료 후 재시작
```

### Windows PC

```powershell
# 1. 코드 받기
git clone https://github.com/woontakyuh/myagents.git C:\Users\{username}\Projects\myagents

# 2. 의존성 설치 & 빌드
cd C:\Users\{username}\Projects\myagents\schedule-agent
npm install && npm run build

# 3. Claude Desktop 설정
# %AppData%\Claude\claude_desktop_config.json 에 추가:
```

```json
"schedule-agent": {
  "command": "node",
  "args": ["C:\\Users\\{username}\\Projects\\myagents\\schedule-agent\\build\\index.js"]
}
```

> **Windows 주의**: Dropbox 경로가 `C:\Users\{username}\Dropbox\...` — 코드에서 자동 감지함

## 코드 업데이트

```bash
cd ~/Projects/myagents
git pull
cd schedule-agent
bun run build
# Claude Desktop 재시작
```

## Google Calendar 연동 (추후)

현재 GCal은 stub 상태. 연동하려면:
1. Google Cloud Console에서 Calendar API 활성화
2. OAuth 2.0 Desktop App 자격증명 생성 → `credentials.json` 다운로드
3. `src/gcal-client.ts` 실제 구현

## Dropbox 경로

| OS | Dropbox 경로 |
|----|-------------|
| macOS (iCloud Drive 방식) | `~/Library/CloudStorage/Dropbox/Tak/2. 학회/{year}/` |
| macOS (기본) | `~/Dropbox/Tak/2. 학회/{year}/` |
| Windows | `C:\Users\{username}\Dropbox\Tak\2. 학회\{year}\` |

폴더 형식: `yyyy-mm-dd 행사명`
