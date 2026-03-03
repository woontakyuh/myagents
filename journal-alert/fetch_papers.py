#!/usr/bin/env python3
"""
PubMed E-utilities로 저널 논문 수집
Usage: python fetch_papers.py --incremental           # 마지막 실행 이후 신규만 (권장)
       python fetch_papers.py --all --year 2026       # 전체 연도 수집 (초기 세팅용)
       python fetch_papers.py --days 30               # 최근 30일
       python fetch_papers.py --journal "Spine J"     # 특정 저널
"""

from __future__ import annotations

import urllib.request
import urllib.error
import urllib.parse
import json
import xml.etree.ElementTree as ET
import time
import argparse
import os
import re
import html as html_mod
from datetime import datetime, timedelta

# ─── 설정 ─────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_INCREMENTAL_DAYS = 14  # state.json 없을 때 기본 조회 범위


# ─── State 관리 ────────────────────────────────────────
def load_state() -> dict:
    """state.json 로드. 없으면 빈 dict 반환."""
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ state.json 로드 실패 ({e}), 초기 상태로 시작")
        return {}


def save_state(state: dict) -> None:
    """state.json 저장."""
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"  💾 state.json 저장 완료 (known_pmids: {len(state.get('known_pmids', []))}건)")


def fetch_abstract_from_doi(doi: str) -> str:
    if not doi:
        return ""

    doi = doi.strip()
    if not doi:
        return ""

    doi_url = f"https://doi.org/{doi}"
    headers = {"User-Agent": "JournalAlert/1.0"}

    final_url = ""
    try:
        req = urllib.request.Request(doi_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            final_url = resp.geturl()
    except Exception as e:
        print(f"  ⚠ DOI 이동 실패 ({doi}): {e}")
        return ""
    finally:
        time.sleep(0.5)

    if not final_url:
        return ""

    domain = urllib.parse.urlparse(final_url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    if domain != "link.springer.com":
        return ""

    try:
        req = urllib.request.Request(final_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            page_html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  ⚠ DOI 본문 조회 실패 ({doi}): {e}")
        return ""
    finally:
        time.sleep(0.5)

    m = re.search(r'id="Abs1-content"[^>]*>(.*?)</div>', page_html, re.DOTALL)
    if not m:
        return ""

    # 태그를 공백으로 치환 (구조화 abstract에서 라벨+본문 사이 공백 보존)
    text = re.sub(r"<[^>]+>", " ", m.group(1))
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    # 구조화 abstract 라벨 포맷팅: PurposeRobotic → Purpose: Robotic
    text = re.sub(
        r"(Purpose|Background|Objective|Methods?|Results?|Conclusions?|Study Design|Setting|Patients?|Outcome Measures?|Introduction|Discussion|Significance)"
        r"(?=[A-Z])",
        r"\1: ",
        text,
    )
    return text

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def search_pubmed(journal_query: str, year: int | None = None, days: int | None = None,
                  edat_min: str | None = None, edat_max: str | None = None,
                  retmax: int = 500) -> list[str]:
    """PubMed에서 논문 ID 검색.

    edat_min/edat_max가 주어지면 datetype=edat로 Entrez date 기반 검색 (incremental 모드).
    그 외에는 기존 pdat 기반 검색.
    """
    term = f'"{journal_query}"[journal]'

    extra_params = ""
    if edat_min and edat_max:
        # Incremental 모드: Entrez date (인덱싱일) 기반
        extra_params = f"&datetype=edat&mindate={edat_min}&maxdate={edat_max}"
        if year:
            term += f" AND {year}[pdat]"
    elif year:
        term += f" AND {year}[pdat]"
    elif days:
        mindate = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
        maxdate = datetime.now().strftime("%Y/%m/%d")
        extra_params = f"&datetype=pdat&mindate={mindate}&maxdate={maxdate}"

    url = (
        f"{PUBMED_BASE}/esearch.fcgi?db=pubmed"
        f"&term={urllib.parse.quote(term)}"
        f"{extra_params}"
        f"&retmax={retmax}&retmode=json"
    )

    req = urllib.request.Request(url, headers={"User-Agent": "JournalAlert/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    ids = data["esearchresult"]["idlist"]
    count = data["esearchresult"]["count"]
    print(f"  검색: {term} {extra_params}")
    print(f"  결과: {count}건 중 {len(ids)}건 가져옴")
    return ids

def fetch_details(pmids: list[str]) -> list[dict]:
    """PubMed에서 논문 상세 정보 가져오기"""
    articles = []
    batch_size = 50

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i+batch_size]
        id_str = ",".join(batch)
        url = f"{PUBMED_BASE}/efetch.fcgi?db=pubmed&id={id_str}&retmode=xml"

        req = urllib.request.Request(url, headers={"User-Agent": "JournalAlert/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)

        for article in root.findall(".//PubmedArticle"):
            try:
                parsed = parse_article(article)
                if parsed:
                    articles.append(parsed)
            except Exception as e:
                pmid = article.findtext(".//PMID", "unknown")
                print(f"  ⚠ PMID {pmid} 파싱 오류: {e}")

        if i + batch_size < len(pmids):
            time.sleep(0.4)  # rate limit

    return articles

def parse_article(article) -> dict | None:
    """XML에서 논문 정보 추출"""
    # PMID
    pmid = article.findtext(".//PMID", "")

    # Title
    title_el = article.find(".//ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""
    if not title:
        return None

    authors = []
    first_affiliation = ""
    for auth in article.findall(".//Author"):
        last = auth.findtext("LastName", "")
        fore = auth.findtext("ForeName", "")
        init = auth.findtext("Initials", "")
        if last:
            authors.append({"last": last, "fore": fore, "initials": init})
            if not first_affiliation:
                aff_el = auth.find(".//AffiliationInfo/Affiliation")
                if aff_el is not None and aff_el.text:
                    first_affiliation = aff_el.text.strip()

    author_str = format_authors(authors)

    # Abstract
    abstract_parts = []
    for abs_text in article.findall(".//Abstract/AbstractText"):
        label = abs_text.get("Label", "")
        text = "".join(abs_text.itertext()).strip()
        if label:
            abstract_parts.append(f"{label}: {text}")
        else:
            abstract_parts.append(text)
    # DOI
    doi = ""
    for aid in article.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text
            break

    abstract = " ".join(abstract_parts)
    if not abstract and doi:
        abstract = fetch_abstract_from_doi(doi)
        if abstract:
            print(f"  📥 DOI fallback abstract: {pmid} ({len(abstract)} chars)")

    # Journal info
    journal = article.findtext(".//Journal/Title", "")
    journal_abbr = article.findtext(".//ISOAbbreviation", "")
    volume = article.findtext(".//Volume", "")
    issue = article.findtext(".//Issue", "")
    pages = article.findtext(".//MedlinePgn", "")

    # Publication date
    pub_date = extract_pub_date(article)

    # Keywords
    keywords = []
    for kw in article.findall(".//Keyword"):
        if kw.text:
            keywords.append(kw.text.strip())

    # MeSH terms
    mesh = []
    for mh in article.findall(".//MeshHeading/DescriptorName"):
        if mh.text:
            mesh.append(mh.text.strip())

    # Publication types
    pub_types = []
    for pt in article.findall(".//PublicationType"):
        if pt.text:
            pub_types.append(pt.text.strip())

    return {
        "pmid": pmid,
        "title": title,
        "authors": author_str,
        "author_list": authors[:10],
        "affiliation": first_affiliation,
        "abstract": abstract,
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else "",
        "journal": journal,
        "journal_abbr": journal_abbr,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "pub_date": pub_date,
        "keywords": keywords,
        "mesh_terms": mesh,
        "pub_types": pub_types,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }

def format_authors(authors: list[dict], max_show: int = 3) -> str:
    """저자 목록 포맷팅"""
    if not authors:
        return ""
    names = [f"{a['last']} {a['initials']}" for a in authors[:max_show]]
    result = ", ".join(names)
    if len(authors) > max_show:
        result += f" et al."
    return result

def extract_pub_date(article) -> str:
    """출판일 추출 → YYYY-MM-DD or YYYY-MM or YYYY"""
    # ArticleDate (epub) 우선
    for ad in article.findall(".//ArticleDate"):
        y = ad.findtext("Year") or ""
        m = ad.findtext("Month") or ""
        d = ad.findtext("Day") or ""
        if y:
            parts = [y]
            if m: parts.append(m.zfill(2))
            if d: parts.append(d.zfill(2))
            return "-".join(parts)

    # PubDate
    for pd in article.findall(".//PubDate"):
        y = pd.findtext("Year") or ""
        m = pd.findtext("Month") or ""
        d = pd.findtext("Day") or ""
        if y:
            parts = [y]
            if m:
                # Month가 "Jan" 같은 문자일 수 있음
                month_map = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                             "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
                if m in month_map:
                    m = month_map[m]
                m = m.zfill(2)
                parts.append(m)
            if d: parts.append(d.zfill(2))
            return "-".join(parts)

    return ""

def save_results(articles: list[dict], journal_key: str, label: str = ""):
    """결과를 JSON으로 저장"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{journal_key}_{label}_{timestamp}.json" if label else f"{journal_key}_{timestamp}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"  💾 저장: {filepath} ({len(articles)}건)")
    return filepath

def print_summary(articles: list[dict]):
    """결과 요약 출력"""
    if not articles:
        print("  결과 없음")
        return

    # Issue별 분류
    by_issue = {}
    for a in articles:
        iss = a.get("issue", "unknown") or "unknown"
        by_issue.setdefault(iss, []).append(a)

    print(f"\n  📊 총 {len(articles)}편")
    for iss in sorted(by_issue.keys()):
        print(f"     Issue {iss}: {len(by_issue[iss])}편")

    # Article type별
    types = {}
    for a in articles:
        for pt in a.get("pub_types", []):
            types[pt] = types.get(pt, 0) + 1
    if types:
        print(f"  📋 유형: {', '.join(f'{k}({v})' for k,v in sorted(types.items(), key=lambda x:-x[1])[:5])}")


# ─── Incremental 모드 ─────────────────────────────────
def run_incremental(config: dict) -> list[dict]:
    """마지막 실행 이후 새로 인덱싱된 논문만 수집 (edat 기반)."""
    state = load_state()
    last_fetch = state.get("last_fetch", "")
    known_pmids = set(state.get("known_pmids", []))

    # mindate 결정: state 있으면 last_fetch - 1일, 없으면 14일 전
    if last_fetch:
        try:
            last_dt = datetime.strptime(last_fetch, "%Y/%m/%d")
        except ValueError:
            last_dt = datetime.now() - timedelta(days=DEFAULT_INCREMENTAL_DAYS)
        # 1일 overlap (PubMed edat 24h visibility lag 대응)
        min_dt = last_dt - timedelta(days=1)
    else:
        min_dt = datetime.now() - timedelta(days=DEFAULT_INCREMENTAL_DAYS)
        print(f"  ℹ️  state.json 없음 → 최근 {DEFAULT_INCREMENTAL_DAYS}일 조회")

    edat_min = min_dt.strftime("%Y/%m/%d")
    edat_max = datetime.now().strftime("%Y/%m/%d")

    print(f"\n🔄 Incremental 모드: edat {edat_min} ~ {edat_max}")
    if known_pmids:
        print(f"   기존 known_pmids: {len(known_pmids)}건")

    all_new_articles = []
    all_fetched_pmids = set()

    for jkey, jinfo in config["journals"].items():
        print(f"\n{'='*50}")
        print(f"📖 {jinfo['name']}")
        print(f"{'='*50}")

        pmids = search_pubmed(
            jinfo["pubmed_query"],
            edat_min=edat_min,
            edat_max=edat_max,
        )

        if not pmids:
            print("  신규 없음")
            continue

        # known_pmids로 이미 처리한 PMID 제외
        new_pmids = [p for p in pmids if p not in known_pmids]
        skipped = len(pmids) - len(new_pmids)
        if skipped:
            print(f"  ⏭ 기존 PMID {skipped}건 스킵")

        if not new_pmids:
            print("  신규 없음 (모두 기존)")
            continue

        print(f"  🆕 신규 PMID: {len(new_pmids)}건")
        articles = fetch_details(new_pmids)

        for a in articles:
            a["_journal_key"] = jkey

        all_new_articles.extend(articles)
        all_fetched_pmids.update(new_pmids)
        time.sleep(1)

    # 결과 저장
    if all_new_articles:
        save_results(all_new_articles, "incremental", edat_max.replace("/", ""))
        print_summary(all_new_articles)

    # state.json 업데이트 (성공 시에만)
    new_state = {
        "last_fetch": datetime.now().strftime("%Y/%m/%d"),
        "last_fetch_iso": datetime.now().isoformat(timespec="seconds"),
        "known_pmids": sorted(known_pmids | all_fetched_pmids),
    }
    save_state(new_state)

    print(f"\n✅ Incremental 완료: 신규 {len(all_new_articles)}편")
    return all_new_articles


# ─── 메인 ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PubMed 저널 논문 수집")
    parser.add_argument("--journal", help="저널명 (PubMed 약어)")
    parser.add_argument("--year", type=int, help="출판년도")
    parser.add_argument("--days", type=int, help="최근 N일 이내")
    parser.add_argument("--all", action="store_true", help="config의 모든 저널 수집")
    parser.add_argument("--incremental", action="store_true",
                        help="마지막 실행 이후 새로 인덱싱된 논문만 수집 (권장)")
    parser.add_argument("--init-state", action="store_true",
                        help="현재 data/ 파일에서 state.json 초기화 (기존 PMID 등록)")
    args = parser.parse_args()

    config = load_config()

    # state.json 초기화 모드
    if args.init_state:
        _init_state_from_data(config)
        return

    # Incremental 모드 (권장)
    if args.incremental:
        return run_incremental(config)

    if args.all:
        # 모든 저널 수집
        all_articles = []
        for jkey, jinfo in config["journals"].items():
            print(f"\n{'='*50}")
            print(f"📖 {jinfo['name']}")
            print(f"{'='*50}")

            pmids = search_pubmed(
                jinfo["pubmed_query"],
                year=args.year if args.year else (None if args.days else datetime.now().year),
                days=args.days
            )
            if pmids:
                articles = fetch_details(pmids)
                # 저널 키 추가
                for a in articles:
                    a["_journal_key"] = jkey
                label = str(args.year) if args.year else (f'days{args.days}' if args.days else str(datetime.now().year))
                save_results(articles, jkey, label)
                print_summary(articles)
                all_articles.extend(articles)
            time.sleep(1)

        # 통합 파일도 저장
        if all_articles:
            label = str(args.year) if args.year else (f'days{args.days}' if args.days else str(datetime.now().year))
            save_results(all_articles, "all_journals", label)

        print(f"\n✅ 전체 {len(all_articles)}편 수집 완료")
        return all_articles

    elif args.journal:
        # 단일 저널
        print(f"\n📖 {args.journal}")
        pmids = search_pubmed(args.journal, year=args.year, days=args.days)
        if pmids:
            articles = fetch_details(pmids)
            save_results(articles, args.journal.replace(" ", "_"), str(args.year or ""))
            print_summary(articles)
            return articles

    else:
        # 기본: config의 첫 번째 저널, 올해
        jkey = list(config["journals"].keys())[0]
        jinfo = config["journals"][jkey]
        year = args.year or datetime.now().year

        print(f"\n📖 {jinfo['name']} ({year})")
        pmids = search_pubmed(jinfo["pubmed_query"], year=year)
        if pmids:
            articles = fetch_details(pmids)
            for a in articles:
                a["_journal_key"] = jkey
            save_results(articles, jkey, str(year))
            print_summary(articles)
            return articles


def _init_state_from_data(config: dict):
    """기존 data/ JSON에서 PMID를 추출하여 state.json 초기화."""
    import glob as glob_mod

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    files = glob_mod.glob(os.path.join(data_dir, "*.json"))
    if not files:
        print("❌ data/ 에 JSON 파일 없음")
        return

    all_pmids = set()
    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                articles = json.load(f)
            for a in articles:
                pmid = a.get("pmid", "")
                if pmid:
                    all_pmids.add(pmid)
        except Exception as e:
            print(f"  ⚠ {os.path.basename(filepath)} 로드 실패: {e}")

    state = {
        "last_fetch": datetime.now().strftime("%Y/%m/%d"),
        "last_fetch_iso": datetime.now().isoformat(timespec="seconds"),
        "known_pmids": sorted(all_pmids),
    }
    save_state(state)
    print(f"✅ state.json 초기화 완료: {len(all_pmids)}개 PMID 등록")


if __name__ == "__main__":
    main()
