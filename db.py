"""Database access layer for the service catalog."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
import psycopg2.extras

from catalog_cli import config

# Register the UUID adapter so psycopg2 returns proper Python UUIDs.
psycopg2.extras.register_uuid()


@contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a psycopg2 connection, closing it on exit."""
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )
    try:
        yield conn
    finally:
        conn.close()


# ── Deterministic queries ───────────────────────────────────────────────────


def get_service(service_name: str) -> dict[str, Any] | None:
    """Return owner, lifecycle, and metadata for a service."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT service_name, owner, lifecycle, metadata, last_updated
                FROM service_catalog
                WHERE service_name = %s
                """,
                (service_name,),
            )
            return cur.fetchone()


def get_tags(service_name: str) -> list[str]:
    """Return the tags array from the JSONB metadata column."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT metadata->'tags' FROM service_catalog
                WHERE service_name = %s
                """,
                (service_name,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return json.loads(row[0]) if isinstance(row[0], str) else row[0]
            return []


def get_raw_content(service_name: str) -> str | None:
    """Return the full raw_content (includes Mermaid diagrams)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT raw_content FROM service_catalog WHERE service_name = %s",
                (service_name,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def list_services(
    owner: str | None = None,
    lifecycle: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    """List services with optional filters."""
    clauses: list[str] = []
    params: list[Any] = []

    if owner:
        clauses.append("owner = %s")
        params.append(owner)
    if lifecycle:
        clauses.append("lifecycle = %s")
        params.append(lifecycle)
    if tag:
        clauses.append("metadata->'tags' ? %s")
        params.append(tag)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT service_name, owner, lifecycle, last_updated
                FROM service_catalog
                {where}
                ORDER BY service_name
                """,
                params,
            )
            return cur.fetchall()


def get_dependencies(service_name: str) -> dict[str, Any]:
    """Return dependsOn and providesApis from the JSONB metadata."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    metadata->'dependsOn' AS depends_on,
                    metadata->'providesApis' AS provides_apis
                FROM service_catalog
                WHERE service_name = %s
                """,
                (service_name,),
            )
            row = cur.fetchone()
            if not row:
                return {}
            parse = lambda v: (json.loads(v) if isinstance(v, str) else v) if v else []
            return {
                "dependsOn": parse(row[0]),
                "providesApis": parse(row[1]),
            }


# ── Vector / RAG queries ───────────────────────────────────────────────────


def vector_search(embedding: list[float], top_k: int | None = None) -> list[str]:
    """Return the top-K most relevant raw_content entries by cosine similarity."""
    k = top_k or config.RAG_TOP_K
    vec_literal = "[" + ",".join(str(f) for f in embedding) + "]"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT raw_content
                FROM service_catalog
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_literal, k),
            )
            return [row[0] for row in cur.fetchall()]


# ── Upsert (used by the ingestion pipeline) ────────────────────────────────


def upsert_service(
    service_name: str,
    owner: str,
    lifecycle: str,
    metadata: dict[str, Any],
    raw_content: str,
    embedding: list[float],
) -> None:
    """Insert or update a service record."""
    vec_literal = "[" + ",".join(str(f) for f in embedding) + "]"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO service_catalog
                    (service_name, owner, lifecycle, metadata, raw_content, embedding)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s::vector)
                ON CONFLICT (service_name) DO UPDATE SET
                    owner        = EXCLUDED.owner,
                    lifecycle    = EXCLUDED.lifecycle,
                    metadata     = EXCLUDED.metadata,
                    raw_content  = EXCLUDED.raw_content,
                    embedding    = EXCLUDED.embedding,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (
                    service_name,
                    owner,
                    lifecycle,
                    json.dumps(metadata),
                    raw_content,
                    vec_literal,
                ),
            )
            conn.commit()
