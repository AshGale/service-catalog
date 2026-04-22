"""Client for the internal /genai endpoint (Llama 3)."""

from __future__ import annotations

import sys
from typing import Iterator

import requests

from catalog_cli import config


class GenAIError(Exception):
    """Raised when the /genai endpoint returns a non-200 response."""


def _post(payload: dict) -> dict:
    """Fire a POST to the genai endpoint and return the JSON body."""
    try:
        resp = requests.post(
            config.GENAI_ENDPOINT,
            json=payload,
            timeout=120,
        )
    except requests.ConnectionError as exc:
        raise GenAIError(f"Cannot reach {config.GENAI_ENDPOINT}: {exc}") from exc

    if resp.status_code != 200:
        raise GenAIError(
            f"/genai returned {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()


def embed(text: str) -> list[float]:
    """Return a vector embedding for *text* from Llama 3."""
    data = _post({"prompt": text, "type": "embedding"})
    vector = data.get("vector")
    if not vector or not isinstance(vector, list):
        raise GenAIError("Response missing 'vector' field or invalid format")
    return vector


def generate(prompt: str) -> str:
    """Return a text completion from Llama 3."""
    data = _post({"prompt": prompt, "type": "generation"})
    text = data.get("text")
    if text is None:
        raise GenAIError("Response missing 'text' field")
    return text


def generate_stream(prompt: str) -> Iterator[str]:
    """Stream a text completion token-by-token.

    Falls back to a single ``generate`` call if the endpoint doesn't
    support streaming (i.e. returns a normal JSON body).
    """
    try:
        resp = requests.post(
            config.GENAI_ENDPOINT,
            json={"prompt": prompt, "type": "generation", "stream": True},
            stream=True,
            timeout=120,
        )
    except requests.ConnectionError as exc:
        raise GenAIError(f"Cannot reach {config.GENAI_ENDPOINT}: {exc}") from exc

    if resp.status_code != 200:
        raise GenAIError(f"/genai returned {resp.status_code}: {resp.text[:500]}")

    content_type = resp.headers.get("content-type", "")

    # If the endpoint returns JSON instead of a stream, fall back.
    if "application/json" in content_type:
        data = resp.json()
        text = data.get("text", "")
        yield text
        return

    # Otherwise, iterate over the streamed chunks.
    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
        if chunk:
            yield chunk
