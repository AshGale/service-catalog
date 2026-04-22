"""Ingestion pipeline — parse Backstage catalog-info.yaml files and upsert."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from catalog_cli import db, genai


def parse_catalog_yaml(path: str | Path) -> dict[str, Any]:
    """Parse a Backstage catalog-info.yaml and return a normalised dict.

    Returns
    -------
    dict with keys: service_name, owner, lifecycle, metadata, raw_content
    """
    path = Path(path)
    raw_content = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw_content)

    metadata_block = doc.get("metadata", {})
    spec = doc.get("spec", {})

    service_name = metadata_block.get("name", path.parent.name)
    owner = spec.get("owner", "unknown")
    lifecycle = spec.get("lifecycle", "unknown")

    # Everything that isn't a top-level column goes into the JSONB metadata.
    extra: dict[str, Any] = {}
    if "tags" in metadata_block:
        extra["tags"] = metadata_block["tags"]
    if "dependsOn" in spec:
        extra["dependsOn"] = spec["dependsOn"]
    if "providesApis" in spec:
        extra["providesApis"] = spec["providesApis"]
    if "type" in spec:
        extra["type"] = spec["type"]

    return {
        "service_name": service_name,
        "owner": owner,
        "lifecycle": lifecycle,
        "metadata": extra,
        "raw_content": raw_content,
    }


def ingest_file(path: str | Path) -> str:
    """Parse a single catalog-info.yaml, embed it, and upsert into Postgres.

    Returns the service_name that was upserted.
    """
    parsed = parse_catalog_yaml(path)
    embedding = genai.embed(parsed["raw_content"])
    db.upsert_service(
        service_name=parsed["service_name"],
        owner=parsed["owner"],
        lifecycle=parsed["lifecycle"],
        metadata=parsed["metadata"],
        raw_content=parsed["raw_content"],
        embedding=embedding,
    )
    return parsed["service_name"]


def ingest_directory(root: str | Path) -> list[str]:
    """Walk a directory tree and ingest every catalog-info.yaml found.

    Returns a list of service names that were upserted.
    """
    root = Path(root)
    ingested: list[str] = []
    for yaml_path in sorted(root.rglob("catalog-info.yaml")):
        name = ingest_file(yaml_path)
        ingested.append(name)
    return ingested
