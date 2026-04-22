"""catalog-cli web server — thin FastAPI layer over the existing CLI modules.

Run with:  uvicorn catalog_cli.server:app --reload
Or:        make serve
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from catalog_cli import db, genai, ingest as ingest_mod, config

# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(title="Service Catalog API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ──────────────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    question: str
    top_k: int = config.RAG_TOP_K


class AskResponse(BaseModel):
    answer: str
    context_count: int


class IngestResponse(BaseModel):
    ingested: list[str]


# ── Deterministic endpoints ─────────────────────────────────────────────────


@app.get("/api/services")
def list_services(
    owner: str | None = Query(None),
    lifecycle: str | None = Query(None),
    tag: str | None = Query(None),
) -> list[dict[str, Any]]:
    rows = db.list_services(owner=owner, lifecycle=lifecycle, tag=tag)
    # Convert datetime to string for JSON serialisation
    for r in rows:
        if r.get("last_updated"):
            r["last_updated"] = str(r["last_updated"])
    return rows


@app.get("/api/services/{service_name}")
def get_service(service_name: str) -> dict[str, Any]:
    row = db.get_service(service_name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    if row.get("last_updated"):
        row["last_updated"] = str(row["last_updated"])
    if row.get("metadata") and isinstance(row["metadata"], str):
        row["metadata"] = json.loads(row["metadata"])
    return row


@app.get("/api/services/{service_name}/tags")
def get_tags(service_name: str) -> list[str]:
    return db.get_tags(service_name)


@app.get("/api/services/{service_name}/diagram")
def get_diagram(service_name: str) -> dict[str, str | None]:
    raw = db.get_raw_content(service_name)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

    in_mermaid = False
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("```mermaid"):
            in_mermaid = True
            continue
        if in_mermaid:
            if stripped == "```":
                break
            lines.append(line)

    return {"mermaid": "\n".join(lines) if lines else None}


@app.get("/api/services/{service_name}/deps")
def get_deps(service_name: str) -> dict[str, Any]:
    data = db.get_dependencies(service_name)
    if not data:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    return data


# ── RAG endpoint ────────────────────────────────────────────────────────────


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    try:
        vector = genai.embed(req.question)
    except genai.GenAIError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}")

    context_rows = db.vector_search(vector, top_k=req.top_k)
    if not context_rows:
        raise HTTPException(status_code=404, detail="No services in the catalog yet.")

    context_text = "\n---\n".join(context_rows)
    prompt = (
        "You are an expert software architect. Answer the question using ONLY "
        "the context below. If the context does not contain the answer, say so.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Question: {req.question}"
    )

    try:
        answer = genai.generate(prompt)
    except genai.GenAIError as exc:
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}")

    return AskResponse(answer=answer, context_count=len(context_rows))


# ── Ingestion endpoint ──────────────────────────────────────────────────────


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_yaml(file: UploadFile = File(...)) -> IngestResponse:
    """Upload a catalog-info.yaml file to ingest."""
    if not file.filename or not file.filename.endswith((".yaml", ".yml")):
        raise HTTPException(status_code=400, detail="File must be a .yaml or .yml file")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        name = ingest_mod.ingest_file(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Ingestion failed: {exc}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return IngestResponse(ingested=[name])


# ── Serve the frontend (if built) ──────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
