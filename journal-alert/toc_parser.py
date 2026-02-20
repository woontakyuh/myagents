#!/usr/bin/env python3
# pyright: basic, reportMissingImports=false
"""
The Spine Journal TOC PDF를 파싱해 Vol/Issue 누락 Notion 페이지를 보완합니다.

실행 예시:
- .venv/bin/python3 toc_parser.py
- .venv/bin/python3 toc_parser.py --pdf toc/TOC_2026_No1_Vol26.pdf --dry-run

주의:
- pdfplumber는 프로젝트 venv(.venv)에 설치되어 있으므로
  venv 활성화 후 실행하거나 `.venv/bin/python3`로 실행하세요.
"""

from __future__ import annotations

import argparse
import difflib
import glob
import json
import os
import re
import time
import urllib.error
import urllib.request

import pdfplumber


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
TOC_DIR = os.path.join(os.path.dirname(__file__), "toc")

PAGE_PATTERN = re.compile(r"^(.*?)(\.{3,})(\d+)\s*$")
VOL_PATTERN = re.compile(r"Volume\s+(\d+)", re.IGNORECASE)
ISSUE_PATTERN = re.compile(r"Number\s+(\d+)", re.IGNORECASE)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def notion_api(endpoint: str, data: dict, token: str, method: str = "POST") -> dict | None:
    url = f"https://api.notion.com/v1/{endpoint}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ❌ Notion API 오류 ({e.code}): {error_body[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"  ❌ Notion 연결 오류: {e}")
        return None


def _extract_rich_text(props: dict, key: str) -> str:
    parts = props.get(key, {}).get("rich_text", [])
    if not parts:
        return ""
    return "".join(part.get("plain_text", "") for part in parts).strip()


def query_all_pages(database_id: str, token: str) -> list[dict]:
    pages = []
    has_more = True
    start_cursor = None

    while has_more:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        result = notion_api(f"databases/{database_id}/query", payload, token)
        if not result:
            break

        for page in result.get("results", []):
            props = page.get("properties", {})
            title_items = props.get("Title", {}).get("title", [])
            title = title_items[0].get("plain_text", "").strip() if title_items else ""

            pages.append(
                {
                    "page_id": page.get("id", ""),
                    "title": title,
                    "vol": _extract_rich_text(props, "Vol"),
                    "issue": _extract_rich_text(props, "Issue"),
                }
            )

        has_more = result.get("has_more", False)
        start_cursor = result.get("next_cursor")

    return pages


def _normalize_match_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _looks_like_author_line(line: str) -> bool:
    if line.count(",") < 2:
        return False
    credentials = ["md", "phd", "mbbs", "bs", "ms", "do", "frcsc", "mba", "msc", "bsc"]
    lowered = line.lower()
    return any(f",{cred}" in lowered for cred in credentials)


def _looks_like_noise(line: str) -> bool:
    lowered = line.lower()
    noise_tokens = [
        "financialconflictofinterestdisclosurekey",
        "postmaster",
        "copyright",
        "photocopying",
        "advertising",
        "www.spine.org",
        "tagged",
        "northamericanspinesociety",
        "nass",
        "customer service",
        "permission",
    ]
    return any(token in lowered for token in noise_tokens)


def _looks_like_heading(line: str) -> bool:
    compact = re.sub(r"\s+", "", line)
    if len(compact) > 60:
        return False
    letters = [c for c in compact if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio > 0.9


def _clean_title_text(text: str) -> str:
    cleaned = re.sub(r"\(cid:[^)]+\)", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .\t\r\n")


def _extract_volume_issue(raw_text: str, first_page_text: str = "", source_path: str = "") -> tuple[str, str]:
    volume = ""
    issue = ""

    header_source = first_page_text or raw_text
    pair_match = re.search(r"Volume\s*(\d+)\s*Number\s*(\d+)", header_source, re.IGNORECASE | re.DOTALL)
    if pair_match:
        return pair_match.group(1), pair_match.group(2)

    vol_m = VOL_PATTERN.search(header_source)
    issue_m = ISSUE_PATTERN.search(header_source)
    if vol_m:
        volume = vol_m.group(1)
    if issue_m:
        issue = issue_m.group(1)

    if not volume:
        vol_m = re.search(r"Volume\s*(\d+)", header_source, re.IGNORECASE)
        if vol_m:
            volume = vol_m.group(1)
    if not issue:
        issue_m = re.search(r"Number\s*(\d+)", header_source, re.IGNORECASE)
        if issue_m:
            issue = issue_m.group(1)

    if (not volume or not issue) and raw_text:
        pair_match = re.search(r"Volume\s*(\d+)\s*Number\s*(\d+)", raw_text, re.IGNORECASE | re.DOTALL)
        if pair_match:
            volume = volume or pair_match.group(1)
            issue = issue or pair_match.group(2)

    if (not volume or not issue) and source_path:
        name = os.path.basename(source_path)
        file_m = re.search(r"No(\d+)_Vol(\d+)", name, re.IGNORECASE)
        if file_m:
            issue = issue or file_m.group(1)
            volume = volume or file_m.group(2)

    return volume, issue


def parse_toc_pdf(pdf_path: str) -> dict:
    raw_lines: list[str] = []
    full_text_parts: list[str] = []
    first_page_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text:
                if idx == 0:
                    first_page_text = text
                full_text_parts.append(text)
                raw_lines.extend(text.splitlines())

    full_text = "\n".join(full_text_parts)
    volume, issue = _extract_volume_issue(full_text, first_page_text=first_page_text, source_path=pdf_path)

    articles: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    pending_parts: list[str] = []

    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            continue
        if _looks_like_noise(line):
            pending_parts = []
            continue
        if _looks_like_author_line(line):
            continue
        if _looks_like_heading(line):
            pending_parts = []
            continue

        match = PAGE_PATTERN.match(line)
        if match:
            title_tail = _clean_title_text(match.group(1))
            page_no = match.group(3).strip()

            title_parts = [p for p in pending_parts if p]
            if title_tail:
                title_parts.append(title_tail)

            full_title = _clean_title_text(" ".join(title_parts))
            pending_parts = []

            if not full_title:
                continue
            if _looks_like_noise(full_title):
                continue

            key = (_normalize_match_text(full_title), page_no)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            articles.append({"title": full_title, "page": page_no})
            continue

        if _looks_like_noise(line):
            pending_parts = []
            continue

        if len(line) > 20 and not _looks_like_author_line(line):
            pending_parts.append(_clean_title_text(line))
            if len(pending_parts) > 3:
                pending_parts = pending_parts[-3:]

    return {"volume": volume, "issue": issue, "articles": articles}


def _patch_vol_issue(page_id: str, volume: str, issue: str, token: str) -> bool:
    props = {
        "Vol": {"rich_text": [{"text": {"content": volume}}]},
        "Issue": {"rich_text": [{"text": {"content": issue}}]},
    }
    result = notion_api(f"pages/{page_id}", {"properties": props}, token, method="PATCH")
    return result is not None


def match_and_update_notion(toc_data: dict, database_id: str, token: str, dry_run: bool = False):
    volume = toc_data.get("volume", "")
    issue = toc_data.get("issue", "")
    articles = toc_data.get("articles", [])

    if not volume or not issue:
        print("❌ TOC에서 Volume/Issue 추출 실패")
        return

    print(f"📋 Notion DB 조회 중... (Vol {volume}, Issue {issue})")
    pages = query_all_pages(database_id, token)
    print(f"   {len(pages)}건 조회됨")

    target_pages = [p for p in pages if not p.get("vol") or not p.get("issue")]
    print(f"   Vol/Issue 누락 페이지: {len(target_pages)}건")

    if not target_pages:
        print("✅ 업데이트 대상 없음")
        return

    normalized_targets = [
        {
            "page_id": p["page_id"],
            "title": p["title"],
            "title_norm": _normalize_match_text(p["title"]),
            "vol": p.get("vol", ""),
            "issue": p.get("issue", ""),
        }
        for p in target_pages
        if p.get("title")
    ]

    matched = 0
    updated = 0
    skipped_low_score = 0
    failed = 0
    used_page_ids: set[str] = set()

    for idx, article in enumerate(articles, 1):
        toc_title = article.get("title", "").strip()
        if not toc_title:
            continue

        toc_norm = _normalize_match_text(toc_title)
        best = None
        best_score = 0.0

        for page in normalized_targets:
            if page["page_id"] in used_page_ids:
                continue
            score = difflib.SequenceMatcher(None, toc_norm, page["title_norm"]).ratio()
            if score > best_score:
                best_score = score
                best = page

        if not best or best_score < 0.7:
            skipped_low_score += 1
            continue

        matched += 1
        used_page_ids.add(best["page_id"])
        print(
            f"  🔎 [{idx}/{len(articles)}] 매칭 {best_score:.2f} | "
            f"TOC: {toc_title[:45]}... -> Notion: {best['title'][:45]}..."
        )

        if dry_run:
            print(f"     🧪 DRY-RUN: Vol={volume}, Issue={issue} 업데이트 예정")
            continue

        ok = _patch_vol_issue(best["page_id"], volume, issue, token)
        if ok:
            updated += 1
            print("     ✅ 업데이트 완료")
        else:
            failed += 1
            print("     ❌ 업데이트 실패")

        time.sleep(0.5)

    print(
        f"✅ 결과: TOC {len(articles)}건 | 매칭 {matched}건 | "
        f"업데이트 {updated}건 | 저신뢰 스킵 {skipped_low_score}건 | 오류 {failed}건"
    )


def _resolve_pdf_targets(single_pdf: str | None) -> list[str]:
    if single_pdf:
        return [single_pdf]
    return sorted(glob.glob(os.path.join(TOC_DIR, "*.pdf")))


def main():
    parser = argparse.ArgumentParser(description="TSJ TOC PDF 파싱 + Notion Vol/Issue 보완")
    parser.add_argument("--pdf", help="단일 PDF 경로")
    parser.add_argument("--dry-run", action="store_true", help="매칭만 출력, Notion 업데이트 생략")
    args = parser.parse_args()

    config = load_config()
    token = os.environ.get("NOTION_TOKEN") or config.get("notion_token", "")
    if not token:
        print("❌ NOTION_TOKEN 환경변수 또는 config.json에 notion_token 설정 필요")
        return 1

    database_id = config.get("notion_database_id", "")
    if not database_id:
        print("❌ config.json에 notion_database_id 없음")
        return 1

    pdf_paths = _resolve_pdf_targets(args.pdf)
    if not pdf_paths:
        print("❌ 처리할 TOC PDF가 없습니다")
        return 1

    print(f"📚 TOC PDF 처리 시작: {len(pdf_paths)}개")
    for pdf_path in pdf_paths:
        print(f"\n📄 {os.path.basename(pdf_path)}")
        try:
            toc_data = parse_toc_pdf(pdf_path)
            print(
                f"   추출: Vol {toc_data.get('volume', '?')} / "
                f"Issue {toc_data.get('issue', '?')} / "
                f"Articles {len(toc_data.get('articles', []))}건"
            )
            match_and_update_notion(toc_data, database_id, token, dry_run=args.dry_run)
        except Exception as e:
            print(f"  ❌ 파일 처리 실패: {e}")

    print("\n🏁 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
