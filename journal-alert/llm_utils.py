#!/usr/bin/env python3
"""
LLM 유틸리티 — 여러 백엔드 지원. 외부 의존성 없이 stdlib만 사용.

환경변수 (우선순위순):
  GOOGLE_API_KEY      → Google Gemini API (무료 1500req/day)
  OPENAI_API_KEY      → OpenAI API (gpt-4o-mini 등)
  ANTHROPIC_API_KEY   → Anthropic API (claude-3-haiku 등)
  (없으면)            → Claude CLI (Max 구독 인증 사용)
"""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import urllib.request
from typing import Optional

SYSTEM_PROMPT = (
    "You are a medical research assistant specializing in spine surgery. "
    "Respond concisely in Korean. "
    "척추 분야 용어 규칙: "
    "cervical=경추, thoracic=흉추, lumbar=요추, sacral=천추. "
    "UBE, ACDF, TLIF, OLIF, MIS 등 척추외과 약어는 한글 부연설명 없이 그대로 사용. "
    "절대 cervical을 자궁경부로 번역하지 마세요."
)


def call_llm(prompt: str, config: dict = None) -> Optional[str]:
    """
    LLM 호출 — 자동 백엔드 선택 순서:
    1. Google Gemini (GOOGLE_API_KEY, 무료)
    2. OpenAI API (OPENAI_API_KEY)
    3. Anthropic API (ANTHROPIC_API_KEY)
    4. Claude CLI (Max 구독, 추가비용 없음)
    """
    llm_config = (config or {}).get("llm", {})
    provider = llm_config.get("provider", "auto")

    if provider == "gemini" or (provider == "auto" and os.environ.get("GOOGLE_API_KEY")):
        result = _call_gemini(prompt, llm_config)
        if result:
            return result

    if provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
        result = _call_openai(prompt, llm_config)
        if result:
            return result

    if provider == "anthropic" or (provider == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        result = _call_anthropic(prompt, llm_config)
        if result:
            return result

    if provider in ("auto", "claude-cli"):
        result = _call_claude_cli(prompt)
        if result:
            return result

    return None


def _call_gemini(prompt: str, llm_config: dict) -> Optional[str]:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return None

    model = llm_config.get("gemini_model", "gemini-2.0-flash")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2000,
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()
        return None
    except Exception as e:
        print(f"  [LLM] Gemini API 실패: {e}")
        return None


def _call_openai(prompt: str, llm_config: dict) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = llm_config.get("openai_model", "gpt-4o-mini")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [LLM] OpenAI API 실패: {e}")
        return None


def _call_anthropic(prompt: str, llm_config: dict) -> Optional[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    model = llm_config.get("anthropic_model", "claude-3-haiku-20240307")

    payload = {
        "model": model,
        "max_tokens": 2000,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "system": SYSTEM_PROMPT,
    }

    url = "https://api.anthropic.com/v1/messages"
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST", headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        content_blocks = data.get("content", [])
        texts = [b["text"] for b in content_blocks if b.get("type") == "text"]
        return "\n".join(texts).strip()
    except Exception as e:
        print(f"  [LLM] Anthropic API 실패: {e}")
        return None


def _call_claude_cli(prompt: str) -> Optional[str]:
    if not shutil.which("claude"):
        return None

    try:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku"],
            input=full_prompt,
            capture_output=True, text=True, timeout=120, env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def check_llm_available(config: dict = None) -> tuple[bool, str]:
    """
    LLM 사용 가능 여부와 백엔드명 반환.
    Returns: (available: bool, backend: str)
    """
    llm_config = (config or {}).get("llm", {})
    provider = llm_config.get("provider", "auto")

    if provider == "gemini" or (provider == "auto" and os.environ.get("GOOGLE_API_KEY")):
        model = llm_config.get("gemini_model", "gemini-2.0-flash")
        return True, f"Gemini ({model}, 무료)"

    if provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
        model = llm_config.get("openai_model", "gpt-4o-mini")
        return True, f"OpenAI ({model})"

    if provider == "anthropic" or (provider == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        model = llm_config.get("anthropic_model", "claude-3-haiku-20240307")
        return True, f"Anthropic ({model})"

    if provider in ("auto", "claude-cli") and shutil.which("claude"):
        return True, "Claude CLI (Max 구독)"

    return False, "없음"


def summarize_and_translate(title: str, abstract: str, config: dict = None) -> tuple[str, str]:
    """
    논문 제목+Abstract → (1줄 한글 요약, 한글 번역)
    LLM 실패 시 fallback으로 abstract 앞부분 반환.
    """
    if not abstract:
        return "", ""

    prompt = f"""논문 제목: {title}

Abstract:
{abstract}

아래 형식 그대로 출력하세요. 제목, 헤더, 라벨, 번호 매기기 등 절대 붙이지 마세요.
"# 1줄 요약", "[1줄 요약]", "**1줄 요약**", "1)", "2)" 같은 것 붙이면 안 됩니다.
오직 요약문과 번역문 본문만 출력하세요.

(한글 1줄 요약 — 50자 내외, 핵심 수치 포함, 의학용어 영문 병기)
---
(Abstract 한글 번역 — 의학용어 영문 병기, 원문 구조 유지)"""

    result = call_llm(prompt, config)
    if not result:
        return abstract[:100] if abstract else "", ""

    parts = result.split("---", 1)
    summary = _clean_llm_header(parts[0].strip())
    translation = _clean_llm_header(parts[1].strip()) if len(parts) > 1 else ""

    if not summary and abstract:
        summary = summarize_only(title, abstract, config)

    return summary, translation


def summarize_only(title: str, abstract: str, config: dict = None) -> str:
    if not abstract:
        return ""

    prompt = f"""논문 제목: {title}

Abstract:
{abstract}

이 논문의 핵심 결론을 한글 한 문장으로 요약하세요 (50자 내외).
의학용어는 영문 병기. 헤더, 라벨, 번호, 마크다운 서식 일절 금지.
오직 요약 문장 하나만 출력하세요."""

    result = call_llm(prompt, config)
    if not result:
        return ""
    return _clean_llm_header(result.strip())


def _clean_llm_header(text: str) -> str:
    import re
    if not text or not text.strip():
        return ""

    full = text.strip()

    _REFUSE = [
        "도움을 드릴 수 없습니다",
        "소프트웨어 엔지니어링과 무관한",
        "코드 작성 및 디버깅",
        "프로그래밍이나 개발 관련",
    ]
    if any(r in full for r in _REFUSE):
        return ""

    _PREAMBLE_RE = re.compile(
        r'^(저는\s*이\s*논문|이\s*작업은\s*논문|이\s*논문의\s*요약|요청하신\s*형식으로|다음은\s*논문)',
        re.MULTILINE,
    )

    # label keywords used in various header formats
    _LABEL = (
        r'1줄\s*요약|한글\s*(1줄\s*)?요약(\s*및\s*번역)?|한글\s*번역|'
        r'논문\s*요약(\s*및\s*번역)?|논문\s*분석(\s*결과)?|'
        r'결론\s*(1줄\s*)?요약|'
        r'요약|Summary|Translation'
    )

    _PROMPT_LEAK_RE = re.compile(
        r'^\(?\s*\d*자\s*내외.*\)?\s*:?\s*\**\s*$'
    )

    _PASTED_RE = re.compile(r'^\[Pasted\s*~?\d+')

    lines = full.splitlines()
    cleaned = []

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if _PREAMBLE_RE.match(s):
            continue

        if _PASTED_RE.match(s):
            continue

        if _PROMPT_LEAK_RE.match(s):
            continue

        # standalone ** or *** (bold markers with no content)
        if re.match(r'^\*{2,3}$', s):
            continue

        # markdown heading → strip the # prefix
        s = re.sub(r'^#{1,4}\s+', '', s)

        # numbered prefix: 1) 2)
        s = re.sub(r'^[12]\)\s*', '', s)

        # **label** or **label**: or **[label]**: or [label] — with any combo of **, [], :
        s = re.sub(
            rf'^[\*\[\s]*({_LABEL})[\]\*\s]*:?\s*',
            '', s, flags=re.IGNORECASE,
        )

        # **목표**: style bold-label prefix
        s = re.sub(r'^\*\*([^*]{1,10})\*\*\s*:\s*', '', s)

        # strip wrapping bold from entire line: **content** → content
        if s.startswith('**') and s.endswith('**') and len(s) > 4:
            inner = s[2:-2].strip()
            if inner and not re.match(rf'^({_LABEL})$', inner, re.IGNORECASE):
                s = inner

        # leading ** without closing (partial bold)
        if s.startswith('**') and '**' not in s[2:]:
            s = s[2:].strip()

        if not s:
            continue

        cleaned.append(s)

    return "\n".join(cleaned).strip()
