"""Ollama client — embed and generate via local Ollama server."""

from __future__ import annotations

import json
from typing import Iterator

import requests

from catalog_cli import config


class GenAIError(Exception):
    """Raised when the Ollama API returns an error."""


def _ollama_post(path: str, payload: dict, stream: bool = False) -> requests.Response:
    url = f"{config.OLLAMA_BASE_URL}{path}"
    try:
        resp = requests.post(url, json=payload, stream=stream, timeout=300)
    except requests.ConnectionError as exc:
        raise GenAIError(f"Cannot reach Ollama at {config.OLLAMA_BASE_URL}: {exc}") from exc
    if resp.status_code != 200:
        raise GenAIError(f"Ollama {path} returned {resp.status_code}: {resp.text[:500]}")
    return resp


def embed(text: str) -> list[float]:
    """Return a vector embedding using Ollama's embed model."""
    resp = _ollama_post("/api/embeddings", {"model": config.OLLAMA_EMBED_MODEL, "prompt": text})
    data = resp.json()
    vector = data.get("embedding")
    if not vector or not isinstance(vector, list):
        raise GenAIError(f"Ollama embeddings response missing 'embedding' field: {data}")
    return vector


def generate(prompt: str) -> str:
    """Return a text completion from Ollama (non-streaming)."""
    resp = _ollama_post(
        "/api/generate",
        {"model": config.OLLAMA_GENERATE_MODEL, "prompt": prompt, "stream": False},
    )
    data = resp.json()
    text = data.get("response")
    if text is None:
        raise GenAIError(f"Ollama generate response missing 'response' field: {data}")
    return text


def generate_stream(prompt: str) -> Iterator[str]:
    """Stream a text completion token-by-token from Ollama."""
    resp = _ollama_post(
        "/api/generate",
        {"model": config.OLLAMA_GENERATE_MODEL, "prompt": prompt, "stream": True},
        stream=True,
    )
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        token = chunk.get("response", "")
        if token:
            yield token
        if chunk.get("done"):
            break
