#!/usr/bin/env python3
"""
새 논문 알림 이메일 발송
Usage: python notify_email.py --latest
       python notify_email.py --latest --status "fetch:ok push:ok"
       python notify_email.py --latest --dry-run
"""

from __future__ import annotations

import smtplib
import json
import os
import sys
import glob
import argparse
from email.mime.text import MIMEText
from datetime import datetime

# ─── 설정 ─────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


# ─── 관심도 분류 (push_to_notion.py와 동일) ─────────────
def classify_interest(article: dict, config: dict) -> str:
    """관심도 자동 분류"""
    title_lower = article.get("title", "").lower()
    abstract_lower = article.get("abstract", "").lower()
    keywords_lower = " ".join(article.get("keywords", [])).lower()
    mesh_lower = " ".join(article.get("mesh_terms", [])).lower()
    all_text = f"{title_lower} {abstract_lower} {keywords_lower} {mesh_lower}"

    # 논문 유형 필터
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


# ─── 이메일 본문 생성 ──────────────────────────────────
def build_email_body(articles: list[dict], config: dict, status: str = "") -> tuple[str, str]:
    """이메일 제목과 본문 생성. Returns: (subject, body)"""
    today = datetime.now().strftime("%Y-%m-%d")

    # 관심도별 분류
    groups = {"🔴 필독": [], "🟡 관심": [], "⚪ 참고": []}
    seen_pmids = set()

    for article in articles:
        pmid = article.get("pmid", "")
        if pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)

        interest = classify_interest(article, config)
        groups[interest].append(article)

    total = len(seen_pmids)
    n_must = len(groups["🔴 필독"])
    n_interest = len(groups["🟡 관심"])
    n_ref = len(groups["⚪ 참고"])

    # 저널 목록
    journals = set()
    for a in articles:
        jkey = a.get("_journal_key", "")
        if jkey and jkey in config.get("journals", {}):
            journals.add(config["journals"][jkey]["name"])
        elif a.get("journal_abbr"):
            journals.add(a["journal_abbr"])
    journal_str = ", ".join(sorted(journals))

    # Subject
    subject = f"[Journal Alert] {today} 새 논문 {total}편"
    if n_must > 0:
        subject += f" (🔴{n_must})"

    # Body
    lines = []
    lines.append(f"📚 Journal Alert — {today}")
    lines.append(f"저널: {journal_str}")
    lines.append("")
    lines.append(f"전체 {total}편 | 🔴 필독 {n_must}편 | 🟡 관심 {n_interest}편 | ⚪ 참고 {n_ref}편")
    lines.append("")

    # 필독 논문 (전체 나열)
    if groups["🔴 필독"]:
        lines.append("━" * 40)
        lines.append(f"🔴 필독 ({n_must}편)")
        lines.append("━" * 40)
        for i, a in enumerate(groups["🔴 필독"], 1):
            title = a["title"][:80]
            authors = a.get("authors", "")[:40]
            doi = a.get("doi_url", "")
            lines.append(f"  {i}. {title}")
            lines.append(f"     {authors}")
            if doi:
                lines.append(f"     {doi}")
            lines.append("")

    # 관심 논문 (상위 10편)
    if groups["🟡 관심"]:
        lines.append("━" * 40)
        show = groups["🟡 관심"][:10]
        lines.append(f"🟡 관심 ({n_interest}편, 상위 {len(show)}편 표시)")
        lines.append("━" * 40)
        for i, a in enumerate(show, 1):
            title = a["title"][:80]
            authors = a.get("authors", "")[:40]
            lines.append(f"  {i}. {title}")
            lines.append(f"     {authors}")
            lines.append("")

    # 참고는 건수만
    if n_ref > 0:
        lines.append(f"⚪ 참고: {n_ref}편 (목록 생략)")
        lines.append("")

    # 실행 상태
    if status:
        lines.append("━" * 40)
        lines.append(f"실행 상태: {status}")
        lines.append(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    body = "\n".join(lines)
    return subject, body


# ─── 이메일 발송 ──────────────────────────────────────
def send_email(subject: str, body: str, config: dict) -> bool:
    """Gmail SMTP로 이메일 발송"""
    email_config = config.get("email", {})
    password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not password:
        print("❌ GMAIL_APP_PASSWORD 환경변수 필요")
        print("   export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'")
        return False

    sender = email_config.get("sender_email", "")
    recipient = email_config.get("recipient_email", sender)
    host = email_config.get("smtp_host", "smtp.gmail.com")
    port = email_config.get("smtp_port", 587)

    if not sender:
        print("❌ config.json에 email.sender_email 설정 필요")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
        print(f"✅ 이메일 발송 완료: {recipient}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ 인증 실패 — Gmail App Password를 확인하세요")
        print("   https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"❌ 이메일 발송 실패: {e}")
        return False


# ─── 메인 ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="논문 알림 이메일 발송")
    parser.add_argument("--data", nargs="+", help="데이터 JSON 파일 경로")
    parser.add_argument("--latest", action="store_true", help="최신 데이터 파일 사용")
    parser.add_argument("--status", default="", help="실행 상태 (daily_check.sh에서 전달)")
    parser.add_argument("--dry-run", action="store_true", help="이메일 발송 없이 내용만 출력")
    args = parser.parse_args()

    config = load_config()

    # 입력 파일 결정
    if args.latest:
        new_files = glob.glob(os.path.join(DATA_DIR, "new_*.json"))
        if new_files:
            input_files = [max(new_files, key=os.path.getmtime)]
        else:
            files = glob.glob(os.path.join(DATA_DIR, "*.json"))
            if not files:
                print("❌ data/ 에 JSON 파일 없음")
                sys.exit(1)
            input_files = [max(files, key=os.path.getmtime)]
            print("⚠️  new_*.json 없음 — 전체 파일 사용 (신규 필터링 안 됨)")
    elif args.data:
        input_files = args.data
    else:
        print("❌ --latest 또는 --data 옵션 필요")
        sys.exit(1)

    # 논문 로드
    articles = []
    for filepath in input_files:
        print(f"📂 {os.path.basename(filepath)}")
        with open(filepath, "r", encoding="utf-8") as f:
            articles.extend(json.load(f))

    if not articles:
        print("⚠️  논문 데이터 없음 — 이메일 생략")
        return

    # 이메일 생성
    subject, body = build_email_body(articles, config, args.status)

    if args.dry_run:
        print(f"\n{'='*50}")
        print(f"Subject: {subject}")
        print(f"{'='*50}")
        print(body)
        print(f"{'='*50}")
        print("(dry-run: 이메일 미발송)")
        return

    # 발송
    send_email(subject, body, config)


if __name__ == "__main__":
    main()
