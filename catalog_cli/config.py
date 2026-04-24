"""Centralised configuration loaded from environment variables."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


# ── Database ────────────────────────────────────────────────────────────────
DB_HOST: str = os.getenv("CATALOG_DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("CATALOG_DB_PORT", "5432"))
DB_NAME: str = os.getenv("CATALOG_DB_NAME", "catalog")
DB_USER: str = os.getenv("CATALOG_DB_USER", "postgres")
DB_PASSWORD: str = os.getenv("CATALOG_DB_PASSWORD", "")

# ── Ollama ──────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("CATALOG_OLLAMA_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL: str = os.getenv("CATALOG_OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_GENERATE_MODEL: str = os.getenv("CATALOG_OLLAMA_GENERATE_MODEL", "llama3.1:8b-instruct-q5_1")

# ── Embedding dimension — must match the embed model output ─────────────────
# nomic-embed-text → 768, mxbai-embed-large → 1024, all-minilm → 384
EMBEDDING_DIM: int = int(os.getenv("CATALOG_EMBEDDING_DIM", "768"))

# ── RAG defaults ────────────────────────────────────────────────────────────
RAG_TOP_K: int = int(os.getenv("CATALOG_RAG_TOP_K", "5"))
