#!/usr/bin/env python3
"""
기존 Notion 페이지에 Type + 한글 요약/번역 업데이트
Usage: python update_existing.py
"""

import json
import os
import sys
import glob
import urllib.error
import urllib.request
import time
from datetime import datetime
from llm_utils import check_llm_available, summarize_and_translate as llm_summarize

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def notion_api(endpoint: str, data: dict, token: str, method="POST") -> dict | None:
    url = f"https://api.notion.com/v1/{endpoint}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ❌ Notion API 오류 ({e.code}): {error_body[:200]}")
        return None

def query_all_pages(database_id: str, token: str) -> list[dict]:
    """모든 페이지 조회 (page_id, title, doi)"""
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
            # Title
            title = ""
            title_prop = props.get("Title", {}).get("title", [])
            if title_prop:
                title = title_prop[0].get("plain_text", "").strip()
            # DOI
            doi_url = props.get("DOI", {}).get("url", "") or ""

            pages.append({
                "page_id": page["id"],
                "title": title,
                "doi_url": doi_url,
            })

        has_more = result.get("has_more", False)
        start_cursor = result.get("next_cursor")

    return pages

def classify_pub_type(article: dict) -> str:
    pub_types = [pt.lower() for pt in article.get("pub_types", [])]
    if any("randomized controlled trial" in pt for pt in pub_types):
        return "RCT"
    if any("meta-analysis" in pt for pt in pub_types):
        return "Meta-analysis"
    if any("systematic review" in pt for pt in pub_types):
        return "Systematic Review"
    if any("review" in pt for pt in pub_types):
        return "Review"
    if any("editorial" in pt for pt in pub_types):
        return "Editorial"
    if any("letter" in pt for pt in pub_types):
        return "Letter to Editor"
    if any("comment" in pt for pt in pub_types):
        return "Letter to Editor"
    if any("published erratum" in pt or "erratum" in pt for pt in pub_types):
        return "Erratum"
    if any("case reports" in pt for pt in pub_types):
        return "Case Report"
    if any("observational" in pt for pt in pub_types):
        return "Observational Study"
    if any("comparative study" in pt for pt in pub_types):
        return "Comparative Study"
    if any("multicenter study" in pt for pt in pub_types):
        return "Multicenter Study"
    if any("validation study" in pt for pt in pub_types):
        return "Validation Study"
    if any("historical article" in pt for pt in pub_types):
        return "Historical Article"
    return "Clinical Study"



def _chunk_text(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:size])
        text = text[size:]
    return chunks

def update_page(page_id: str, article: dict, token: str, use_llm: bool, config: dict = None) -> bool:
    pub_type = classify_pub_type(article)

    abstract = article.get("abstract", "")
    if use_llm and abstract:
        summary_ko, translation_ko = llm_summarize(article["title"], abstract, config)
    else:
        summary_ko = abstract[:100] if abstract else ""
        translation_ko = ""

    props = {
        "Type": {"select": {"name": pub_type}},
    }
    volume = article.get("volume", "")
    issue = article.get("issue", "")
    if volume:
        props["Vol"] = {"rich_text": [{"text": {"content": volume}}]}
    if issue:
        props["Issue"] = {"rich_text": [{"text": {"content": issue}}]}

    if summary_ko:
        props["Summary"] = {"rich_text": [{"text": {"content": summary_ko[:2000]}}]}

    result = notion_api(f"pages/{page_id}", {"properties": props}, token, method="PATCH")
    if not result:
        return False

    # 한글 번역 블록 추가
    if translation_ko:
        blocks = [
            {"object": "block", "type": "divider", "divider": {}},
            {
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "한글 번역"}}]}
            },
        ]
        for chunk in _chunk_text(translation_ko, 2000):
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
            })

        notion_api(f"blocks/{page_id}/children", {"children": blocks}, token, method="PATCH")

    return True


def main():
    config = load_config()
    token = os.environ.get("NOTION_TOKEN") or config.get("notion_token", "")
    if not token:
        print("❌ NOTION_TOKEN 필요")
        sys.exit(1)

    database_id = config["notion_database_id"]

    use_llm, llm_backend = check_llm_available(config)
    if use_llm:
        print(f"🤖 LLM 감지: {llm_backend} — 한글 요약/번역 생성")
    else:
        print("⚠️  LLM 미설정 — Type만 업데이트")

    # 1. Notion 기존 페이지 조회
    print("📋 Notion DB 조회 중...")
    pages = query_all_pages(database_id, token)
    print(f"   {len(pages)}건 조회됨")

    # 2. 데이터 JSON 로드
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    if not files:
        print("❌ data/ 에 JSON 파일 없음")
        sys.exit(1)

    articles = []
    with open(files[-1], "r", encoding="utf-8") as f:
        articles = json.load(f)
    print(f"📂 {os.path.basename(files[-1])} ({len(articles)}편)")

    # 3. DOI/Title로 매칭 인덱스 구축
    by_doi = {}
    by_title = {}
    for a in articles:
        if a.get("doi_url"):
            by_doi[a["doi_url"]] = a
        if a.get("title"):
            by_title[a["title"].strip()[:50]] = a

    # 4. 업데이트
    updated = 0
    skipped = 0
    failed = 0

    for i, page in enumerate(pages):
        # 매칭
        article = by_doi.get(page["doi_url"]) or by_title.get(page["title"][:50])
        if not article:
            skipped += 1
            continue

        pub_type = classify_pub_type(article)
        print(f"  [{i+1}/{len(pages)}] {pub_type:20s} | {page['title'][:50]}...")

        if update_page(page["page_id"], article, token, use_llm, config):
            updated += 1
        else:
            failed += 1

        time.sleep(0.5)  # rate limit (Claude CLI + Notion)

    print(f"\n✅ 완료: 업데이트 {updated}건, 매칭실패 {skipped}건, 오류 {failed}건")


if __name__ == "__main__":
    main()
