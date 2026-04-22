"""Centralised configuration loaded from environment variables."""

from __future__ import annotations

import os


# ── Database ────────────────────────────────────────────────────────────────
DB_HOST: str = os.getenv("CATALOG_DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("CATALOG_DB_PORT", "5432"))
DB_NAME: str = os.getenv("CATALOG_DB_NAME", "catalog")
DB_USER: str = os.getenv("CATALOG_DB_USER", "postgres")
DB_PASSWORD: str = os.getenv("CATALOG_DB_PASSWORD", "")

# ── GenAI endpoint (Llama 3) ────────────────────────────────────────────────
GENAI_ENDPOINT: str = os.getenv("CATALOG_GENAI_ENDPOINT", "https://internal-api/genai")

# ── Embedding dimension — must match the Llama 3 model you deploy ───────────
EMBEDDING_DIM: int = int(os.getenv("CATALOG_EMBEDDING_DIM", "1536"))

# ── RAG defaults ────────────────────────────────────────────────────────────
RAG_TOP_K: int = int(os.getenv("CATALOG_RAG_TOP_K", "5"))
