#!/usr/bin/env python3
"""
PubMed E-utilities로 저널 논문 수집
Usage: python fetch_papers.py [--journal "Spine J"] [--year 2026] [--days 30]
"""

import urllib.request
import json
import xml.etree.ElementTree as ET
import time
import argparse
import os
from datetime import datetime, timedelta

# ─── 설정 ─────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def search_pubmed(journal_query: str, year: int = None, days: int = None, retmax: int = 500) -> list[str]:
    """PubMed에서 논문 ID 검색"""
    term = f'"{journal_query}"[journal]'
    if year:
        term += f" AND {year}[pdat]"
    if days:
        mindate = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
        maxdate = datetime.now().strftime("%Y/%m/%d")
        term += f"&datetype=pdat&mindate={mindate}&maxdate={maxdate}"
    
    url = f"{PUBMED_BASE}/esearch.fcgi?db=pubmed&term={urllib.parse.quote(term)}&retmax={retmax}&retmode=json"
    
    req = urllib.request.Request(url, headers={"User-Agent": "JournalAlert/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    
    ids = data["esearchresult"]["idlist"]
    count = data["esearchresult"]["count"]
    print(f"  검색: {term}")
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

def parse_article(article) -> dict:
    """XML에서 논문 정보 추출"""
    # PMID
    pmid = article.findtext(".//PMID", "")
    
    # Title
    title_el = article.find(".//ArticleTitle")
    title = "".join(title_el.itertext()).strip() if title_el is not None else ""
    if not title:
        return None
    
    # Authors
    authors = []
    for auth in article.findall(".//Author"):
        last = auth.findtext("LastName", "")
        fore = auth.findtext("ForeName", "")
        init = auth.findtext("Initials", "")
        if last:
            authors.append({"last": last, "fore": fore, "initials": init})
    
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
    abstract = " ".join(abstract_parts)
    
    # DOI
    doi = ""
    for aid in article.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text
            break
    
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
        "author_list": authors[:10],  # 상세 저자 (최대 10명)
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
        y = ad.findtext("Year", "")
        m = ad.findtext("Month", "")
        d = ad.findtext("Day", "")
        if y:
            parts = [y]
            if m: parts.append(m.zfill(2))
            if d: parts.append(d.zfill(2))
            return "-".join(parts)
    
    # PubDate
    for pd in article.findall(".//PubDate"):
        y = pd.findtext("Year", "")
        m = pd.findtext("Month", "")
        d = pd.findtext("Day", "")
        if y:
            parts = [y]
            if m:
                # Month가 "Jan" 같은 문자일 수 있음
                month_map = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                             "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
                m = month_map.get(m, m).zfill(2)
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

# ─── 메인 ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PubMed 저널 논문 수집")
    parser.add_argument("--journal", help="저널명 (PubMed 약어)")
    parser.add_argument("--year", type=int, help="출판년도")
    parser.add_argument("--days", type=int, help="최근 N일 이내")
    parser.add_argument("--all", action="store_true", help="config의 모든 저널 수집")
    args = parser.parse_args()
    
    config = load_config()
    
    if args.all:
        # 모든 저널 수집
        all_articles = []
        for jkey, jinfo in config["journals"].items():
            print(f"\n{'='*50}")
            print(f"📖 {jinfo['name']}")
            print(f"{'='*50}")
            
            pmids = search_pubmed(
                jinfo["pubmed_query"],
                year=args.year or datetime.now().year,
                days=args.days
            )
            if pmids:
                articles = fetch_details(pmids)
                # 저널 키 추가
                for a in articles:
                    a["_journal_key"] = jkey
                save_results(articles, jkey, str(args.year or datetime.now().year))
                print_summary(articles)
                all_articles.extend(articles)
            time.sleep(1)
        
        # 통합 파일도 저장
        if all_articles:
            save_results(all_articles, "all_journals", str(args.year or datetime.now().year))
        
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

import urllib.parse

if __name__ == "__main__":
    main()
