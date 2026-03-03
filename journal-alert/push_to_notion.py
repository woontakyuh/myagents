#!/usr/bin/env python3
"""
수집된 논문을 Notion 데이터베이스에 push
Usage: python push_to_notion.py [data/spinej_2026_*.json]
       python push_to_notion.py --latest          # 가장 최근 파일
       python push_to_notion.py --all             # data/ 전체
"""

from __future__ import annotations

import json
import os
import sys
import glob
import urllib.request
import urllib.error
import time
from datetime import datetime
from llm_utils import check_llm_available, summarize_and_translate as llm_summarize

# ─── 설정 ─────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def is_source_data_file(path: str) -> bool:
    name = os.path.basename(path)
    if not name.endswith(".json"):
        return False
    return not name.startswith("new_")

def notion_api(endpoint: str, data: dict, token: str, method="POST") -> dict | None:
    """Notion API 호출"""
    url = f"https://api.notion.com/v1/{endpoint}"
    body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    })

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ❌ Notion API 오류 ({e.code}): {error_body[:200]}")
        return None

def query_existing(database_id: str, token: str) -> set:
    """이미 등록된 논문 DOI/Title 목록 조회. API 실패 시 raise."""
    existing = set()
    has_more = True
    start_cursor = None
    page_count = 0
    while has_more:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if not result:
            raise RuntimeError(
                f"Notion DB 조회 실패 (page {page_count + 1}). "
                f"지금까지 {len(existing)}건 로드됨. "
                f"dedup 불가 → 중단합니다."
            )
        for page in result.get("results", []):
            props = page.get("properties", {})
            # DOI로 중복 체크
            doi_prop = props.get("DOI", {})
            if doi_prop.get("url"):
                existing.add(doi_prop["url"])
            # Title로도 체크
            title_prop = props.get("Title", {})
            titles = title_prop.get("title", [])
            if titles:
                existing.add(titles[0].get("plain_text", "").strip()[:50])
        page_count += 1
        has_more = result.get("has_more", False)
        start_cursor = result.get("next_cursor")





# ─── 관심도/카테고리 분류 ─────────────────────────────────
def classify_interest(article: dict, config: dict) -> str:
    """관심도 자동 분류"""
    title_lower = article.get("title", "").lower()
    abstract_lower = article.get("abstract", "").lower()
    keywords_lower = " ".join(article.get("keywords", [])).lower()
    mesh_lower = " ".join(article.get("mesh_terms", [])).lower()
    all_text = f"{title_lower} {abstract_lower} {keywords_lower} {mesh_lower}"

    # 논문 유형 필터 (Letter, Erratum 등은 참고)
    pub_types = [pt.lower() for pt in article.get("pub_types", [])]
    low_priority_types = ["letter", "comment", "erratum", "published erratum", "editorial"]
    if any(lpt in pt for pt in pub_types for lpt in low_priority_types):
        return "⚪ 참고"

    # 필독 키워드
    must_read = config.get("interest_keywords", {}).get("must_read", [])
    for kw in must_read:
        if kw.lower() in all_text:
            return "🔴 필독"

    # 관심 키워드
    interested = config.get("interest_keywords", {}).get("interested", [])
    match_count = sum(1 for kw in interested if kw.lower() in all_text)
    if match_count >= 2:
        return "🔴 필독"
    elif match_count >= 1:
        return "🟡 관심"

    return "⚪ 참고"


def classify_pub_type(article: dict) -> str:
    """논문 유형 분류 (Journal Type)"""
    pub_types = [pt.lower() for pt in article.get("pub_types", [])]

    # 우선순위순 매핑
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


def auto_categorize(article: dict, config: dict) -> list[str]:
    """자동 카테고리 분류"""
    categories = []
    all_text = (
        article.get("title", "") + " " +
        article.get("abstract", "") + " " +
        " ".join(article.get("keywords", [])) + " " +
        " ".join(article.get("mesh_terms", []))
    ).lower()

    category_rules = config.get("category_rules", {})
    for cat_name, keywords in category_rules.items():
        for kw in keywords:
            if kw.lower() in all_text:
                categories.append(cat_name)
                break

    # Pub type 기반
    pub_types = [pt.lower() for pt in article.get("pub_types", [])]
    if any("review" in pt for pt in pub_types):
        if "Review" not in categories:
            categories.append("Review")
    if any("meta-analysis" in pt for pt in pub_types):
        if "Meta-analysis" not in categories:
            categories.append("Meta-analysis")
    if any("randomized" in pt for pt in pub_types):
        if "RCT" not in categories:
            categories.append("RCT")

    return categories


# ─── Notion 페이지 블록 구성 ──────────────────────────────
def build_abstract_blocks(abstract: str, translation: str) -> list[dict]:
    """페이지 본문에 들어갈 Abstract 블록들"""
    blocks = []

    if abstract:
        # English heading
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Abstract"}}]
            }
        })
        # English body — 2000자 제한 처리
        for chunk in _chunk_text(abstract, 2000):
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })

    if translation:
        # Divider
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        # Korean heading
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "한글 번역"}}]
            }
        })
        # Korean body
        for chunk in _chunk_text(translation, 2000):
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })

    return blocks


def _chunk_text(text: str, size: int) -> list[str]:
    """텍스트를 size 단위로 분할"""
    if len(text) <= size:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:size])
        text = text[size:]
    return chunks


# ─── Notion 페이지 생성 ──────────────────────────────────
def create_notion_page(article: dict, database_id: str, token: str,
                       config: dict, use_llm: bool = False) -> bool:
    interest = classify_interest(article, config)

    journal_key = article.get("_journal_key", "")
    journal_name = article.get("journal_abbr", "") or article.get("journal", "")
    if journal_key and journal_key in config.get("journals", {}):
        journal_name = config["journals"][journal_key]["name"]

    categories = auto_categorize(article, config)
    journal_type = classify_pub_type(article)

    abstract = article.get("abstract", "")
    if use_llm:
        summary_ko, translation_ko = llm_summarize(article["title"], abstract, config)
    else:
        summary_ko = abstract[:100] if abstract else ""
        translation_ko = ""

    # Properties 구성
    properties = {
        "Title": {
            "title": [{"text": {"content": article["title"][:2000]}}]
        },
        "Author": {
            "rich_text": [{"text": {"content": article.get("authors", "")[:2000]}}]
        },
        "Journal Name": {
            "select": {"name": journal_name[:100]} if journal_name else None
        },
        "Summary": {
            "rich_text": [{"text": {"content": summary_ko[:2000]}}]
        },
        "관심도": {
            "select": {"name": interest}
        },
        "읽음": {
            "checkbox": False
        },
        "Type": {
            "select": {"name": journal_type}
        },
    }

    if article.get("affiliation"):
        properties["Affiliations"] = {
            "rich_text": [{"text": {"content": article["affiliation"][:2000]}}]
        }

    if article.get("volume"):
        properties["Vol"] = {"rich_text": [{"text": {"content": article["volume"]}}]}
    if article.get("issue"):
        properties["Issue"] = {"rich_text": [{"text": {"content": article["issue"]}}]}

    # DOI URL
    if article.get("doi_url"):
        properties["DOI"] = {"url": article["doi_url"]}

    # Publication Date
    if article.get("pub_date"):
        date_str = article["pub_date"]
        if len(date_str) == 4:
            date_str = f"{date_str}-01-01"
        elif len(date_str) == 7:
            date_str = f"{date_str}-01"
        properties["Publication Date"] = {"date": {"start": date_str}}

    # Keywords (Notion multi_select doesn't allow commas)
    if article.get("keywords"):
        clean_kws = []
        for kw in article["keywords"][:5]:
            for part in kw.split(","):
                part = part.strip()[:100]
                if part:
                    clean_kws.append(part)
        if clean_kws:
            properties["Keywords"] = {
                "multi_select": [{"name": k} for k in clean_kws[:10]]
            }

    # Category
    if categories:
        properties["Category"] = {
            "multi_select": [{"name": cat} for cat in categories[:5]]
        }

    # None 제거
    properties = {k: v for k, v in properties.items() if v is not None}

    # 페이지 본문 블록 (영문 Abstract + 한글 번역)
    children = build_abstract_blocks(abstract, translation_ko)

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }
    if children:
        payload["children"] = children

    result = notion_api("pages", payload, token)
    return result is not None


# ─── 메인 ──────────────────────────────────────────────
def main():
    config = load_config()

    # Notion 토큰 확인
    token = os.environ.get("NOTION_TOKEN") or config.get("notion_token", "")
    if not token:
        print("❌ NOTION_TOKEN 환경변수 또는 config.json에 notion_token 설정 필요")
        print("   export NOTION_TOKEN='ntn_...'")
        sys.exit(1)

    use_llm, llm_backend = check_llm_available(config)
    if use_llm:
        print(f"🤖 LLM 감지: {llm_backend} — 한글 요약/번역 생성")
    else:
        print("⚠️  LLM 미설정 — 한글 요약/번역 없이 진행 (OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 설정 필요)")

    database_id = config["notion_database_id"]

    # 입력 파일 결정
    data_dir = os.path.join(os.path.dirname(__file__), "data")

    if len(sys.argv) > 1 and sys.argv[1] == "--latest":
        files = [
            p
            for p in glob.glob(os.path.join(data_dir, "*.json"))
            if is_source_data_file(p)
        ]
        if not files:
            print("❌ data/ 에 수집 원본 JSON 파일 없음. fetch_papers.py 먼저 실행하세요.")
            sys.exit(1)
        input_files = [max(files, key=os.path.getmtime)]
    elif len(sys.argv) > 1 and sys.argv[1] == "--all":
        input_files = sorted(
            p
            for p in glob.glob(os.path.join(data_dir, "*.json"))
            if is_source_data_file(p)
        )
    elif len(sys.argv) > 1:
        input_files = sys.argv[1:]
    else:
        files = sorted(
            p
            for p in glob.glob(os.path.join(data_dir, "*.json"))
            if is_source_data_file(p)
        )
        if not files:
            print("❌ data/ 에 수집 원본 JSON 파일 없음")
            sys.exit(1)
        input_files = [files[-1]]

    # 기존 논문 목록 조회 (중복 방지)
    print("📋 기존 Notion DB 조회 중...")
    existing = query_existing(database_id, token)
    print(f"   기존 {len(existing)}건 등록됨")

    # 논문 push
    total_new = 0
    total_skip = 0
    new_articles = []  # 신규 논문 목록 (이메일 알림용)

    for filepath in input_files:
        print(f"\n📂 {os.path.basename(filepath)}")
        with open(filepath, "r", encoding="utf-8") as f:
            articles = json.load(f)

        for i, article in enumerate(articles):
            # 중복 체크
            doi_url = article.get("doi_url", "")
            title_key = article.get("title", "").strip()[:50]

            if doi_url in existing or title_key in existing:
                total_skip += 1
                continue

            interest = classify_interest(article, config)
            emoji = "🔴" if "필독" in interest else "🟡" if "관심" in interest else "⚪"

            success = create_notion_page(article, database_id, token, config, use_llm)
            if success:
                total_new += 1
                existing.add(doi_url)
                existing.add(title_key)
                new_articles.append(article)
                print(f"  {emoji} [{i+1}/{len(articles)}] {article['title'][:60]}...")
            else:
                print(f"  ❌ [{i+1}/{len(articles)}] 실패: {article['title'][:40]}...")

            time.sleep(0.35)  # Notion rate limit

    # 신규 논문을 별도 JSON으로 저장 (notify_email.py용)
    if new_articles:
        new_file = os.path.join(data_dir, f"new_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(new_file, "w", encoding="utf-8") as f:
            json.dump(new_articles, f, ensure_ascii=False, indent=2)
        print(f"  📧 신규 논문 저장: {os.path.basename(new_file)} ({len(new_articles)}건)")

    print(f"\n✅ 완료: 새로 추가 {total_new}건, 중복 스킵 {total_skip}건")
    return total_new

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result is None or result > 0 else 2)
