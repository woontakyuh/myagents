#!/usr/bin/env python3
"""
새 논문 알림 이메일 발송 (HTML)
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
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from collections import Counter

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


# ─── 카테고리 분류 ────────────────────────────────────
def auto_categorize(article: dict, config: dict) -> list[str]:
    title_lower = article.get("title", "").lower()
    abstract_lower = article.get("abstract", "").lower()
    keywords_lower = " ".join(article.get("keywords", [])).lower()
    all_text = f"{title_lower} {abstract_lower} {keywords_lower}"

    categories = []
    for cat, keywords in config.get("category_rules", {}).items():
        if any(kw.lower() in all_text for kw in keywords):
            categories.append(cat)
    return categories


# ─── HTML 이메일 본문 생성 ─────────────────────────────
def build_email_body(articles: list[dict], config: dict, status: str = "") -> tuple[str, str]:
    today = datetime.now().strftime("%Y-%m-%d")

    groups = {"🔴 필독": [], "🟡 관심": [], "⚪ 참고": []}
    seen_pmids = set()
    journal_counter = Counter()
    category_counter = Counter()

    for article in articles:
        pmid = article.get("pmid", "")
        if pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)

        interest = classify_interest(article, config)
        groups[interest].append(article)

        jkey = article.get("_journal_key", "")
        jname = config.get("journals", {}).get(jkey, {}).get("name", article.get("journal_abbr", "기타"))
        journal_counter[jname] += 1

        cats = auto_categorize(article, config)
        for c in cats:
            category_counter[c] += 1

    total = len(seen_pmids)
    n_must = len(groups["🔴 필독"])
    n_interest = len(groups["🟡 관심"])
    n_ref = len(groups["⚪ 참고"])

    subject = f"[Journal Alert] {today} 새 논문 {total}편"
    if n_must > 0:
        subject += f" (🔴{n_must})"

    journal_pills = " &nbsp;".join(
        f'<span style="background:#27272a;padding:2px 8px;border-radius:10px;font-size:12px;color:#a1a1aa;">'
        f'{name} <b style="color:#e4e4e7;">{cnt}</b></span>'
        for name, cnt in journal_counter.most_common()
    )

    cat_pills = " &nbsp;".join(
        f'<span style="background:#1e1e2e;padding:2px 8px;border-radius:10px;font-size:11px;color:#93c5fd;">'
        f'{cat} {cnt}</span>'
        for cat, cnt in category_counter.most_common(8)
    )

    def _article_row(a: dict, idx: int, show_summary: bool = False) -> str:
        title = a["title"]
        authors = a.get("authors", "")[:50]
        doi = a.get("doi_url", "")
        summary = a.get("_summary", "") or a.get("summary", "")
        jkey = a.get("_journal_key", "")
        jname = config.get("journals", {}).get(jkey, {}).get("name", "")

        title_html = f'<a href="{doi}" style="color:#e4e4e7;text-decoration:none;">{title}</a>' if doi else title
        summary_html = ""
        if show_summary and summary:
            summary_html = f'<div style="color:#93c5fd;font-size:12px;margin-top:2px;font-style:italic;">{summary[:120]}</div>'

        return f"""<tr>
<td style="padding:8px 12px;border-bottom:1px solid #3f3f46;vertical-align:top;width:24px;color:#71717a;font-size:12px;">{idx}</td>
<td style="padding:8px 12px;border-bottom:1px solid #3f3f46;">
  <div style="color:#e4e4e7;font-size:13px;line-height:1.4;">{title_html}</div>
  {summary_html}
  <div style="color:#71717a;font-size:11px;margin-top:2px;">{authors} · {jname}</div>
</td>
</tr>"""

    must_read_rows = "".join(_article_row(a, i, show_summary=True) for i, a in enumerate(groups["🔴 필독"], 1))
    interested_rows = "".join(_article_row(a, i) for i, a in enumerate(groups["🟡 관심"][:15], 1))
    interested_note = f" (상위 15편)" if n_interest > 15 else ""

    status_html = ""
    if status:
        status_html = f"""
<div style="margin-top:16px;padding:8px 12px;background:#1c1c1c;border-radius:6px;font-size:11px;color:#71717a;">
  실행 상태: {status} · {datetime.now().strftime('%H:%M:%S')}
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#09090b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:24px 16px;">

<div style="margin-bottom:20px;">
  <h1 style="color:#fafafa;font-size:20px;margin:0;">📚 Journal Alert</h1>
  <p style="color:#71717a;font-size:13px;margin:4px 0 0;">{today}</p>
</div>

<div style="display:flex;gap:8px;margin-bottom:16px;">
  <div style="background:#450a0a;border:1px solid #7f1d1d;border-radius:8px;padding:8px 14px;text-align:center;">
    <div style="color:#fca5a5;font-size:18px;font-weight:700;">{n_must}</div>
    <div style="color:#fca5a5;font-size:10px;">필독</div>
  </div>
  <div style="background:#422006;border:1px solid #78350f;border-radius:8px;padding:8px 14px;text-align:center;">
    <div style="color:#fcd34d;font-size:18px;font-weight:700;">{n_interest}</div>
    <div style="color:#fcd34d;font-size:10px;">관심</div>
  </div>
  <div style="background:#18181b;border:1px solid #3f3f46;border-radius:8px;padding:8px 14px;text-align:center;">
    <div style="color:#a1a1aa;font-size:18px;font-weight:700;">{n_ref}</div>
    <div style="color:#a1a1aa;font-size:10px;">참고</div>
  </div>
  <div style="background:#18181b;border:1px solid #3f3f46;border-radius:8px;padding:8px 14px;text-align:center;margin-left:auto;">
    <div style="color:#fafafa;font-size:18px;font-weight:700;">{total}</div>
    <div style="color:#a1a1aa;font-size:10px;">전체</div>
  </div>
</div>

<div style="margin-bottom:12px;">{journal_pills}</div>
<div style="margin-bottom:20px;">{cat_pills}</div>

{"" if not groups["🔴 필독"] else f'''
<div style="margin-bottom:20px;">
  <h2 style="color:#fca5a5;font-size:14px;margin:0 0 8px;border-bottom:1px solid #7f1d1d;padding-bottom:6px;">
    🔴 필독 ({n_must}편)
  </h2>
  <table style="width:100%;border-collapse:collapse;">{must_read_rows}</table>
</div>
'''}

{"" if not groups["🟡 관심"] else f'''
<div style="margin-bottom:20px;">
  <h2 style="color:#fcd34d;font-size:14px;margin:0 0 8px;border-bottom:1px solid #78350f;padding-bottom:6px;">
    🟡 관심 ({n_interest}편{interested_note})
  </h2>
  <table style="width:100%;border-collapse:collapse;">{interested_rows}</table>
</div>
'''}

{"" if n_ref == 0 else f'''
<div style="color:#71717a;font-size:12px;margin-bottom:16px;">⚪ 참고: {n_ref}편 (목록 생략)</div>
'''}

{status_html}

<div style="margin-top:24px;padding-top:12px;border-top:1px solid #27272a;color:#52525b;font-size:10px;text-align:center;">
  Spinoscopy AI · Journal Alert System
</div>

</div></body></html>"""

    return subject, html


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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body, "html", "utf-8"))

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
