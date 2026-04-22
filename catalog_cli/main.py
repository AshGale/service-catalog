"""catalog-cli — AI-First Service Catalog CLI.

Deterministic commands (zero tokens):
    get, tags, diagram, list, deps

Generative commands (RAG via Llama 3):
    ask

Ingestion:
    ingest
"""

from __future__ import annotations

import json
import sys
import yaml
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from catalog_cli import db, genai, ingest as ingest_mod, config

app = typer.Typer(
    name="catalog-cli",
    help="AI-First Service Catalog CLI (v1.0)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _abort(msg: str) -> None:
    console.print(f"[bold red]Error:[/] {msg}", highlight=False)
    raise typer.Exit(code=1)


# ── Deterministic commands (zero tokens) ────────────────────────────────────


@app.command()
def get(service_name: str = typer.Argument(..., help="Exact service name")):
    """Return owner, lifecycle, and metadata for a service."""
    row = db.get_service(service_name)
    if not row:
        _abort(f"Service '{service_name}' not found.")

    table = Table(title=service_name, show_header=False, title_style="bold cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Owner", row["owner"] or "—")
    table.add_row("Lifecycle", row["lifecycle"] or "—")
    table.add_row("Last Updated", str(row["last_updated"]))
    if row.get("metadata"):
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        table.add_row("Metadata", json.dumps(meta, indent=2))
    console.print(table)


@app.command()
def tags(service_name: str = typer.Argument(..., help="Exact service name")):
    """List tags for a service (from JSONB metadata)."""
    tag_list = db.get_tags(service_name)
    if not tag_list:
        _abort(f"No tags found for '{service_name}' (or service doesn't exist).")
    for t in tag_list:
        rprint(f"  • {t}")


@app.command()
def diagram(service_name: str = typer.Argument(..., help="Exact service name")):
    """Print the raw Mermaid diagram embedded in the service description."""
    raw = db.get_raw_content(service_name)
    if not raw:
        _abort(f"Service '{service_name}' not found.")

    # Extract the Mermaid block from the raw YAML text.
    in_mermaid = False
    mermaid_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("```mermaid"):
            in_mermaid = True
            continue
        if in_mermaid:
            if stripped == "```":
                break
            mermaid_lines.append(line)

    if not mermaid_lines:
        _abort(f"No Mermaid diagram found in '{service_name}'.")

    console.print(
        Panel(
            "\n".join(mermaid_lines),
            title=f"{service_name} — Architecture Diagram (Mermaid)",
            border_style="green",
        )
    )


@app.command(name="list")
def list_services(
    owner: Optional[str] = typer.Option(None, "--owner", "-o", help="Filter by owner"),
    lifecycle: Optional[str] = typer.Option(None, "--lifecycle", "-l", help="Filter by lifecycle"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
):
    """List all services, optionally filtered by owner/lifecycle/tag."""
    rows = db.list_services(owner=owner, lifecycle=lifecycle, tag=tag)
    if not rows:
        _abort("No services matched the given filters.")

    table = Table(title="Service Catalog", title_style="bold cyan")
    table.add_column("Service", style="bold")
    table.add_column("Owner")
    table.add_column("Lifecycle")
    table.add_column("Last Updated")
    for r in rows:
        table.add_row(
            r["service_name"], r["owner"] or "—", r["lifecycle"] or "—", str(r["last_updated"])
        )
    console.print(table)


@app.command()
def deps(service_name: str = typer.Argument(..., help="Exact service name")):
    """Show dependencies and provided APIs for a service."""
    data = db.get_dependencies(service_name)
    if not data:
        _abort(f"Service '{service_name}' not found.")

    depends = data.get("dependsOn", [])
    provides = data.get("providesApis", [])

    if depends:
        console.print("[bold]Depends On:[/]")
        for d in depends:
            rprint(f"  → {d}")
    else:
        console.print("[dim]No dependencies declared.[/dim]")

    if provides:
        console.print("[bold]Provides APIs:[/]")
        for p in provides:
            rprint(f"  ← {p}")
    else:
        console.print("[dim]No APIs declared.[/dim]")


# ── Generative commands (RAG, uses tokens) ──────────────────────────────────


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural-language architecture question"),
    top_k: int = typer.Option(config.RAG_TOP_K, "--top-k", "-k", help="Number of context docs"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream the response"),
):
    """Ask an AI-powered architectural question (RAG over the catalog)."""
    with console.status("[bold green]Embedding your question…"):
        try:
            vector = genai.embed(question)
        except genai.GenAIError as exc:
            _abort(f"Embedding failed: {exc}")

    with console.status("[bold green]Searching catalog…"):
        context_rows = db.vector_search(vector, top_k=top_k)

    if not context_rows:
        _abort("No services in the catalog yet. Run 'catalog-cli ingest' first.")

    context_text = "\n---\n".join(context_rows)
    final_prompt = (
        "You are an expert software architect. Answer the question using ONLY "
        "the context below. If the context does not contain the answer, say so.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {question}"
    )

    console.print()
    console.rule("[bold cyan]AI Architect")

    if stream:
        try:
            for token in genai.generate_stream(final_prompt):
                sys.stdout.write(token)
                sys.stdout.flush()
        except genai.GenAIError as exc:
            _abort(f"Generation failed: {exc}")
    else:
        try:
            answer = genai.generate(final_prompt)
        except genai.GenAIError as exc:
            _abort(f"Generation failed: {exc}")
        console.print(answer)

    console.print()
    console.rule()


# ── Ingestion commands ──────────────────────────────────────────────────────


@app.command()
def ingest(
    path: str = typer.Argument(..., help="Path to a catalog-info.yaml or a directory to walk"),
):
    """Ingest one or many catalog-info.yaml files into the database."""
    p = Path(path)
    if not p.exists():
        _abort(f"Path does not exist: {path}")

    if p.is_file():
        with console.status(f"[bold green]Ingesting {p.name}…"):
            try:
                name = ingest_mod.ingest_file(p)
            except Exception as exc:
                _abort(f"Ingestion failed: {exc}")
        console.print(f"[green]✓[/] Ingested [bold]{name}[/]")
    else:
        with console.status("[bold green]Scanning for catalog-info.yaml files…"):
            try:
                names = ingest_mod.ingest_directory(p)
            except Exception as exc:
                _abort(f"Ingestion failed: {exc}")
        if not names:
            _abort(f"No catalog-info.yaml files found under {path}")
        for n in names:
            console.print(f"[green]✓[/] Ingested [bold]{n}[/]")
        console.print(f"\n[bold]{len(names)}[/] service(s) ingested.")


# ── Dump ───────────────────────────────────────────────────────────────────


@app.command()
def dump(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write to file (default: print to stdout)"),
    fmt: str = typer.Option("json", "--format", "-f", help="Output format: json or yaml"),
):
    """Dump the full catalog (all services, all fields, no embeddings) to JSON or YAML."""
    rows = db.dump_all()
    if not rows:
        _abort("Catalog is empty — ingest some services first.")

    if fmt == "yaml":
        text = yaml.dump(rows, sort_keys=False, allow_unicode=True)
    else:
        text = json.dumps(rows, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        console.print(f"[green]✓[/] Wrote {len(rows)} service(s) to [bold]{output}[/]")
    else:
        console.print(text)


# ── DB bootstrap helper ────────────────────────────────────────────────────


@app.command(name="init-db")
def init_db():
    """Create the service_catalog table and pgvector extension.

    Safe to run repeatedly — uses IF NOT EXISTS / IF EXISTS checks.
    """
    dim = config.EMBEDDING_DIM
    ddl = f"""
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS service_catalog (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        service_name VARCHAR(255) UNIQUE NOT NULL,
        owner VARCHAR(255),
        lifecycle VARCHAR(50),
        metadata JSONB,
        raw_content TEXT,
        embedding VECTOR({dim}),
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Recreate the HNSW index (idempotent via IF NOT EXISTS isn't supported
    -- for indexes on all PG versions, so we drop-and-create).
    DROP INDEX IF EXISTS service_catalog_embedding_idx;
    CREATE INDEX service_catalog_embedding_idx
        ON service_catalog USING hnsw (embedding vector_cosine_ops);
    """

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
            conn.commit()

    console.print("[green]✓[/] Database initialised (pgvector + service_catalog table).")


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
