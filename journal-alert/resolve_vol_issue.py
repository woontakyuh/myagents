#!/usr/bin/env python3
# pyright: basic
"""
Notion DB의 Vol/Issue 누락 논문을 CrossRef + PubMed 재조회로 보완합니다.

Usage:
- python3 resolve_vol_issue.py
- python3 resolve_vol_issue.py --dry-run
- python3 resolve_vol_issue.py --crossref-only
- python3 resolve_vol_issue.py --pubmed-only
"""

import argparse
import glob
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


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
            doi_url = props.get("DOI", {}).get("url", "") or ""

            pages.append(
                {
                    "page_id": page.get("id", ""),
                    "title": title,
                    "doi_url": doi_url,
                    "vol": _extract_rich_text(props, "Vol"),
                    "issue": _extract_rich_text(props, "Issue"),
                }
            )

        has_more = result.get("has_more", False)
        start_cursor = result.get("next_cursor")

    return pages


def _normalize_title(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _extract_doi(doi_or_url: str) -> str:
    value = (doi_or_url or "").strip()
    if not value:
        return ""
    lower = value.lower()
    if lower.startswith("https://doi.org/"):
        return value[16:]
    if lower.startswith("http://doi.org/"):
        return value[15:]
    return value


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def resolve_via_crossref(doi: str) -> tuple[str, str]:
    doi = _extract_doi(doi)
    if not doi:
        return "", ""

    encoded_doi = urllib.parse.quote(doi, safe="")
    url = f"https://api.crossref.org/works/{encoded_doi}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "JournalAlert/1.0 (mailto:woontak.yuh@gmail.com)",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"    ⚠️  CrossRef HTTP 오류 ({e.code})")
        return "", ""
    except urllib.error.URLError as e:
        print(f"    ⚠️  CrossRef 연결 오류: {e}")
        return "", ""
    except Exception as e:
        print(f"    ⚠️  CrossRef 파싱 오류: {e}")
        return "", ""

    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    volume = _safe_text(message.get("volume"))
    issue = _safe_text(message.get("issue"))
    return volume, issue


def resolve_via_pubmed(pmid: str) -> tuple[str, str]:
    pmid = (pmid or "").strip()
    if not pmid:
        return "", ""

    query = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
        }
    )
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{query}"

    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            xml_text = resp.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(xml_text)
    except urllib.error.HTTPError as e:
        print(f"    ⚠️  PubMed HTTP 오류 ({e.code})")
        return "", ""
    except urllib.error.URLError as e:
        print(f"    ⚠️  PubMed 연결 오류: {e}")
        return "", ""
    except ET.ParseError as e:
        print(f"    ⚠️  PubMed XML 파싱 오류: {e}")
        return "", ""

    volume = (root.findtext(".//JournalIssue/Volume", "") or "").strip()
    issue = (root.findtext(".//JournalIssue/Issue", "") or "").strip()
    return volume, issue


def _load_latest_articles() -> list[dict]:
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), key=os.path.getmtime)
    if not files:
        return []

    selected_files = []
    all_journal_files = [p for p in files if os.path.basename(p).startswith("all_journals_")]
    if all_journal_files:
        selected_files = [all_journal_files[-1]]
    else:
        by_prefix = {}
        for path in files:
            name = os.path.basename(path)
            prefix = name.split("_202", 1)[0]
            by_prefix[prefix] = path
        selected_files = sorted(by_prefix.values())

    articles = []
    for path in selected_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                rows = json.load(f)
                if isinstance(rows, list):
                    articles.extend(rows)
        except Exception as e:
            print(f"  ⚠️  JSON 로드 실패: {os.path.basename(path)} ({e})")

    return articles


def _build_article_maps(articles: list[dict]) -> tuple[dict, dict]:
    by_doi = {}
    by_title = {}

    for article in articles:
        doi_url = (article.get("doi_url") or "").strip()
        doi = (article.get("doi") or "").strip()
        if doi_url:
            by_doi[doi_url.lower()] = article
        if doi:
            by_doi[f"https://doi.org/{doi}".lower()] = article

        title = (article.get("title") or "").strip()
        if title:
            by_title[_normalize_title(title)] = article

    return by_doi, by_title


def _update_page_vol_issue(page_id: str, volume: str, issue: str, token: str) -> bool:
    props = {}
    if volume:
        props["Vol"] = {"rich_text": [{"text": {"content": volume}}]}
    if issue:
        props["Issue"] = {"rich_text": [{"text": {"content": issue}}]}
    if not props:
        return False

    result = notion_api(f"pages/{page_id}", {"properties": props}, token, method="PATCH")
    return result is not None


def resolve_all(
    database_id: str,
    token: str,
    dry_run: bool = False,
    crossref_only: bool = False,
    pubmed_only: bool = False,
):
    print("📋 Notion DB 조회 중...")
    pages = query_all_pages(database_id, token)
    print(f"   {len(pages)}건 조회됨")

    targets = [p for p in pages if not p.get("vol") or not p.get("issue")]
    print(f"   Vol/Issue 누락: {len(targets)}건")
    if not targets:
        print("✅ 업데이트 대상 없음")
        return

    print("📂 최신 JSON 로드 중...")
    articles = _load_latest_articles()
    print(f"   {len(articles)}건 로드")
    by_doi, by_title = _build_article_maps(articles)

    total_resolved = 0
    total_updated = 0
    total_failed = 0
    total_skipped = 0

    for idx, page in enumerate(targets, 1):
        try:
            title = page.get("title", "")
            doi_url = page.get("doi_url", "")
            vol_now = page.get("vol", "")
            issue_now = page.get("issue", "")

            article = None
            if doi_url:
                article = by_doi.get(doi_url.lower())
            if not article and title:
                article = by_title.get(_normalize_title(title))

            doi = _extract_doi(doi_url)
            pmid = ""
            if article:
                if not doi:
                    doi = _extract_doi(article.get("doi_url") or article.get("doi") or "")
                pmid = (article.get("pmid") or "").strip()

            print(f"\n🔎 [{idx}/{len(targets)}] {title[:70]}...")

            found_vol = ""
            found_issue = ""
            source = ""

            if not pubmed_only and doi:
                print(f"    🌐 CrossRef 조회: {doi}")
                found_vol, found_issue = resolve_via_crossref(doi)
                time.sleep(1.0)
                if found_vol or found_issue:
                    source = "CrossRef"

            if not source and not crossref_only and pmid:
                print(f"    🧬 PubMed 재조회: PMID {pmid}")
                found_vol, found_issue = resolve_via_pubmed(pmid)
                if found_vol or found_issue:
                    source = "PubMed"

            new_vol = vol_now or found_vol
            new_issue = issue_now or found_issue
            if not new_vol and not new_issue:
                total_skipped += 1
                print("    ⏭️  해상 실패 (CrossRef/PubMed 모두 값 없음)")
                continue

            if (new_vol == vol_now) and (new_issue == issue_now):
                total_skipped += 1
                print("    ⏭️  변경 없음")
                continue

            total_resolved += 1
            print(f"    ✅ 해상 성공 ({source}): Vol={new_vol or '-'} / Issue={new_issue or '-'}")

            if dry_run:
                print("    🧪 DRY-RUN: Notion 업데이트 생략")
                continue

            ok = _update_page_vol_issue(page["page_id"], new_vol, new_issue, token)
            if ok:
                total_updated += 1
                print("    💾 Notion 업데이트 완료")
            else:
                total_failed += 1
                print("    ❌ Notion 업데이트 실패")

            time.sleep(0.5)
        except Exception as e:
            total_failed += 1
            print(f"    ❌ 처리 오류: {e}")

    print(
        f"\n✅ 완료: 해상 {total_resolved}건, 업데이트 {total_updated}건, "
        f"스킵 {total_skipped}건, 오류 {total_failed}건"
    )


def main():
    parser = argparse.ArgumentParser(description="CrossRef + PubMed 재조회로 Vol/Issue 보완")
    parser.add_argument("--dry-run", action="store_true", help="실제 Notion 업데이트 없이 결과만 출력")
    parser.add_argument("--crossref-only", action="store_true", help="CrossRef만 사용")
    parser.add_argument("--pubmed-only", action="store_true", help="PubMed만 사용")
    args = parser.parse_args()

    if args.crossref_only and args.pubmed_only:
        print("❌ --crossref-only 와 --pubmed-only 는 동시에 사용할 수 없습니다")
        return 1

    config = load_config()
    token = os.environ.get("NOTION_TOKEN") or config.get("notion_token", "")
    if not token:
        print("❌ NOTION_TOKEN 환경변수 또는 config.json에 notion_token 설정 필요")
        return 1

    database_id = config.get("notion_database_id", "")
    if not database_id:
        print("❌ config.json에 notion_database_id 없음")
        return 1

    resolve_all(
        database_id=database_id,
        token=token,
        dry_run=args.dry_run,
        crossref_only=args.crossref_only,
        pubmed_only=args.pubmed_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
