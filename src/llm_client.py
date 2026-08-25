"""
The ONLY file that talks to the LLM API. Swap providers/models by editing
just this file — every other module calls `ask_llm(system, user)` and
doesn't know or care which provider is behind it.

Currently wired to Gemini via the google-genai SDK.
"""

import re
import time

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from src import config

_client = None

# Gemini's free tier occasionally returns 503 (server overloaded) during
# high-traffic periods. Retry a few times with a short backoff before
# giving up — this keeps a transient blip from crashing a live demo.
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 4

# 429 (rate limit) is different: it's expected on the free tier (20 req/min
# on gemini-2.5-flash) and the API tells us exactly how long to wait via
# retryDelay in the error body. Retry once with that delay (plus a small
# buffer) before giving up — most 429s during a demo resolve within seconds.
RATE_LIMIT_MAX_RETRIES = 1
RATE_LIMIT_DEFAULT_DELAY_SECONDS = 15


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _extract_retry_delay_seconds(error) -> float:
    """
    Gemini's 429 error body includes a 'Please retry in 13.45s' message and/or
    a structured retryDelay field. Parse whichever we can find; fall back to
    a sane default if the format changes.
    """
    message = str(error)
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", message, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1  # small buffer
    match = re.search(r"'retryDelay':\s*'(\d+)s'", message)
    if match:
        return float(match.group(1)) + 1
    return RATE_LIMIT_DEFAULT_DELAY_SECONDS


def ask_llm(system_prompt: str, user_prompt: str, max_tokens: int = None) -> str:
    """Single-turn call. Returns plain text response.

    Retries on transient server errors (503) up to MAX_RETRIES times, and on
    rate-limit errors (429) once, waiting however long Gemini says to. If
    every attempt fails, returns a friendly message instead of raising, so
    the Streamlit app doesn't crash mid-demo.
    """
    client = _get_client()

    rate_limit_retries_used = 0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=config.LLM_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens or config.LLM_MAX_TOKENS,
                ),
            )
            return response.text or ""
        except genai_errors.ServerError as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS * attempt)  # backoff: 4s, 8s
                continue
            return (
                "⚠️ Gemini's servers are currently overloaded (503) and didn't "
                "respond after several retries. This is usually temporary — "
                "please wait a moment and try asking again."
            )
        except genai_errors.ClientError as e:
            if getattr(e, "code", None) == 429 and rate_limit_retries_used < RATE_LIMIT_MAX_RETRIES:
                delay = _extract_retry_delay_seconds(e)
                rate_limit_retries_used += 1
                time.sleep(delay)
                continue
            if getattr(e, "code", None) == 429:
                return (
                    "⚠️ Free-tier rate limit reached (Gemini allows ~20 requests/min "
                    "on gemini-2.5-flash). Please wait about a minute and try again."
                )
            # Other client errors (bad request / auth) won't fix themselves on retry.
            return f"⚠️ Gemini API error (not retryable): {e}"

    return "⚠️ Something went wrong contacting Gemini. Please try again."
