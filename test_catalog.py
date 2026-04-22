"""Tests for catalog-cli.

Run with:  pytest tests/ -v
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── YAML Parsing ────────────────────────────────────────────────────────────


class TestParseYaml:
    """Test the Backstage YAML parser without touching DB or genai."""

    SAMPLE_YAML = textwrap.dedent("""\
        apiVersion: backstage.io/v1alpha1
        kind: Component
        metadata:
          name: payment-processing-service
          description: |
            Handles credit card processing.

            Architecture Diagram:
            ```mermaid
            graph TD
              A[Web UI] -->|REST API| B(Payment Service)
            ```
          tags:
            - python
            - fastapi
            - critical-path
        spec:
          type: service
          lifecycle: production
          owner: team-finance
          dependsOn:
            - resource:kafka-payments-topic
          providesApis:
            - api:payment-rest-api
    """)

    @pytest.fixture()
    def yaml_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "catalog-info.yaml"
        p.write_text(self.SAMPLE_YAML)
        return p

    def test_parses_service_name(self, yaml_file: Path):
        from catalog_cli.ingest import parse_catalog_yaml

        result = parse_catalog_yaml(yaml_file)
        assert result["service_name"] == "payment-processing-service"

    def test_parses_owner_and_lifecycle(self, yaml_file: Path):
        from catalog_cli.ingest import parse_catalog_yaml

        result = parse_catalog_yaml(yaml_file)
        assert result["owner"] == "team-finance"
        assert result["lifecycle"] == "production"

    def test_parses_tags_into_metadata(self, yaml_file: Path):
        from catalog_cli.ingest import parse_catalog_yaml

        result = parse_catalog_yaml(yaml_file)
        assert result["metadata"]["tags"] == ["python", "fastapi", "critical-path"]

    def test_parses_dependencies(self, yaml_file: Path):
        from catalog_cli.ingest import parse_catalog_yaml

        result = parse_catalog_yaml(yaml_file)
        assert "resource:kafka-payments-topic" in result["metadata"]["dependsOn"]
        assert "api:payment-rest-api" in result["metadata"]["providesApis"]

    def test_raw_content_is_full_yaml(self, yaml_file: Path):
        from catalog_cli.ingest import parse_catalog_yaml

        result = parse_catalog_yaml(yaml_file)
        assert "apiVersion: backstage.io/v1alpha1" in result["raw_content"]
        assert "```mermaid" in result["raw_content"]

    def test_missing_optional_fields_default_to_unknown(self, tmp_path: Path):
        from catalog_cli.ingest import parse_catalog_yaml

        minimal = tmp_path / "catalog-info.yaml"
        minimal.write_text(
            textwrap.dedent("""\
                apiVersion: backstage.io/v1alpha1
                kind: Component
                metadata:
                  name: bare-service
                spec: {}
            """)
        )
        result = parse_catalog_yaml(minimal)
        assert result["service_name"] == "bare-service"
        assert result["owner"] == "unknown"
        assert result["lifecycle"] == "unknown"

    def test_directory_walk_finds_nested_files(self, tmp_path: Path):
        from catalog_cli.ingest import parse_catalog_yaml

        # Create nested structure
        svc_a = tmp_path / "svc-a"
        svc_a.mkdir()
        (svc_a / "catalog-info.yaml").write_text(self.SAMPLE_YAML)

        svc_b = tmp_path / "nested" / "svc-b"
        svc_b.mkdir(parents=True)
        (svc_b / "catalog-info.yaml").write_text(
            self.SAMPLE_YAML.replace("payment-processing-service", "other-service")
        )

        yamls = sorted(tmp_path.rglob("catalog-info.yaml"))
        assert len(yamls) == 2


# ── Mermaid Extraction ──────────────────────────────────────────────────────


class TestMermaidExtraction:
    """Test the diagram extraction logic used by both CLI and server."""

    RAW_WITH_MERMAID = textwrap.dedent("""\
        description: |
          Some service.

          Architecture Diagram:
          ```mermaid
          graph TD
            A[Web UI] -->|REST| B(Service)
            B --> C{Kafka}
          ```
        tags:
          - python
    """)

    RAW_WITHOUT_MERMAID = "description: A simple service with no diagram.\n"

    def _extract(self, raw: str) -> str | None:
        """Same extraction logic as main.py and server.py."""
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
        return "\n".join(lines) if lines else None

    def test_extracts_mermaid_block(self):
        result = self._extract(self.RAW_WITH_MERMAID)
        assert result is not None
        assert "graph TD" in result
        assert "```mermaid" not in result
        assert "```" not in result

    def test_returns_none_when_no_mermaid(self):
        assert self._extract(self.RAW_WITHOUT_MERMAID) is None


# ── GenAI Client ────────────────────────────────────────────────────────────


class TestGenAIClient:
    """Test the genai module with mocked HTTP responses."""

    def test_embed_returns_vector(self):
        from catalog_cli.genai import embed

        fake_vector = [0.1] * 4096
        with patch("catalog_cli.genai.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"vector": fake_vector},
            )
            result = embed("test text")
            assert result == fake_vector
            call_body = mock_post.call_args[1]["json"]
            assert call_body["type"] == "embedding"

    def test_generate_returns_text(self):
        from catalog_cli.genai import generate

        with patch("catalog_cli.genai.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"text": "The answer is 42."},
            )
            result = generate("What is the answer?")
            assert result == "The answer is 42."

    def test_embed_raises_on_bad_status(self):
        from catalog_cli.genai import embed, GenAIError

        with patch("catalog_cli.genai.requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=500,
                text="Internal Server Error",
            )
            with pytest.raises(GenAIError, match="500"):
                embed("test")

    def test_embed_raises_on_connection_error(self):
        import requests as req
        from catalog_cli.genai import embed, GenAIError

        with patch("catalog_cli.genai.requests.post", side_effect=req.ConnectionError("nope")):
            with pytest.raises(GenAIError, match="Cannot reach"):
                embed("test")


# ── FastAPI Endpoints ───────────────────────────────────────────────────────


class TestAPI:
    """Test the FastAPI server with mocked DB layer."""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from catalog_cli.server import app

        return TestClient(app)

    def test_list_services_empty(self, client):
        with patch("catalog_cli.db.list_services", return_value=[]):
            resp = client.get("/api/services")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_list_services_returns_data(self, client):
        rows = [
            {
                "service_name": "svc-a",
                "owner": "team-x",
                "lifecycle": "production",
                "last_updated": "2025-01-01 00:00:00",
            }
        ]
        with patch("catalog_cli.db.list_services", return_value=rows):
            resp = client.get("/api/services")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["service_name"] == "svc-a"

    def test_get_service_not_found(self, client):
        with patch("catalog_cli.db.get_service", return_value=None):
            resp = client.get("/api/services/nope")
            assert resp.status_code == 404

    def test_get_service_found(self, client):
        row = {
            "service_name": "svc-a",
            "owner": "team-x",
            "lifecycle": "production",
            "metadata": {"tags": ["go"]},
            "last_updated": "2025-01-01 00:00:00",
        }
        with patch("catalog_cli.db.get_service", return_value=row):
            resp = client.get("/api/services/svc-a")
            assert resp.status_code == 200
            assert resp.json()["owner"] == "team-x"

    def test_get_tags(self, client):
        with patch("catalog_cli.db.get_tags", return_value=["python", "fastapi"]):
            resp = client.get("/api/services/svc-a/tags")
            assert resp.json() == ["python", "fastapi"]

    def test_get_diagram_not_found(self, client):
        with patch("catalog_cli.db.get_raw_content", return_value=None):
            resp = client.get("/api/services/svc-a/diagram")
            assert resp.status_code == 404

    def test_ingest_rejects_non_yaml(self, client):
        resp = client.post(
            "/api/ingest",
            files={"file": ("readme.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    def test_ask_with_mocked_genai(self, client):
        fake_vector = [0.0] * 4096
        with (
            patch("catalog_cli.genai.embed", return_value=fake_vector),
            patch("catalog_cli.db.vector_search", return_value=["raw content here"]),
            patch("catalog_cli.genai.generate", return_value="The answer."),
        ):
            resp = client.post(
                "/api/ask",
                json={"question": "What services use Kafka?"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["answer"] == "The answer."
            assert body["context_count"] == 1


# ── Config ──────────────────────────────────────────────────────────────────


class TestConfig:
    def test_defaults_are_sensible(self):
        from catalog_cli import config

        assert config.DB_HOST == "localhost"
        assert config.DB_PORT == 5432
        assert config.EMBEDDING_DIM == 4096
        assert config.RAG_TOP_K == 5

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CATALOG_RAG_TOP_K", "10")
        monkeypatch.setenv("CATALOG_DB_PORT", "5433")
        # Reimport to pick up new env
        import importlib
        from catalog_cli import config

        importlib.reload(config)
        assert config.RAG_TOP_K == 10
        assert config.DB_PORT == 5433
        # Reset
        monkeypatch.delenv("CATALOG_RAG_TOP_K")
        monkeypatch.delenv("CATALOG_DB_PORT")
        importlib.reload(config)
