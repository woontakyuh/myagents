#!/usr/bin/env python3
"""
LLM 유틸리티 — 여러 백엔드 지원 (OpenAI, Anthropic, Claude CLI fallback)
외부 의존성 없이 stdlib만 사용.

환경변수:
  OPENAI_API_KEY      → OpenAI API (gpt-4o-mini 등)
  OPENAI_BASE_URL     → 커스텀 엔드포인트 (Antigravity 프록시 등)
  ANTHROPIC_API_KEY   → Anthropic API (claude-3-haiku 등)

config.json의 "llm" 섹션으로 모델/프로바이더 설정 가능.
"""

import json
import os
import subprocess
import shutil
import urllib.request
from typing import Optional


def call_llm(prompt: str, config: dict = None) -> Optional[str]:
    """
    LLM 호출 (자동 백엔드 선택)
    
    순서:
    1. OpenAI API (OPENAI_API_KEY)
    2. Anthropic API (ANTHROPIC_API_KEY)
    3. Claude CLI (legacy fallback)
    4. None
    """
    llm_config = (config or {}).get("llm", {})
    provider = llm_config.get("provider", "auto")

    if provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
        result = _call_openai(prompt, llm_config)
        if result:
            return result

    if provider == "anthropic" or (provider == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        result = _call_anthropic(prompt, llm_config)
        if result:
            return result

    skip_cli = llm_config.get("skip_cli_fallback", False)
    if not skip_cli and provider in ("auto", "claude-cli"):
        result = _call_claude_cli(prompt)
        if result:
            return result

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
            {"role": "system", "content": "You are a medical research assistant specializing in spine surgery. Respond concisely."},
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
        "system": "You are a medical research assistant specializing in spine surgery. Respond concisely.",
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
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", prompt],
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

    if provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
        model = llm_config.get("openai_model", "gpt-4o-mini")
        return True, f"OpenAI ({model})"

    if provider == "anthropic" or (provider == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        model = llm_config.get("anthropic_model", "claude-3-haiku-20240307")
        return True, f"Anthropic ({model})"

    skip_cli = llm_config.get("skip_cli_fallback", False)
    if not skip_cli and provider in ("auto", "claude-cli") and shutil.which("claude"):
        return True, "Claude CLI (haiku)"

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

다음 2가지를 출력하세요. 구분자 "---" 를 사이에 넣으세요.

1) 이 논문의 결론을 한글 1줄로 요약 (50자 내외, 핵심 수치 포함). 의학용어는 영문 병기.
2) Abstract 전체를 한글로 번역 (의학용어 영문 병기, 원문 구조 유지).

형식:
[1줄 요약]
---
[한글 번역]"""

    result = call_llm(prompt, config)
    if not result:
        return abstract[:100] if abstract else "", ""

    parts = result.split("---", 1)
    summary = parts[0].strip()
    translation = parts[1].strip() if len(parts) > 1 else ""

    return summary, translation
