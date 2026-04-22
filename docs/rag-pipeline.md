# RAG Requirements Gathering Pipeline

How the service catalog turns a plain-English question into a grounded,
architecture-aware answer — without hallucinating services that don't exist.

There are two separate phases:
data goes **in** once (ingestion), then you **query** it many times (RAG).

---

## Phase 1 — Ingestion

How service knowledge gets stored as searchable vectors.

```mermaid
flowchart TD
    subgraph INPUT ["📂 Input"]
        YAML["catalog-info.yaml\n(Backstage format)\n─────────────────\nservice name · owner · lifecycle\ntags · dependsOn · providesApis\nmermaid diagram · description"]
    end

    subgraph CLI ["🖥️  catalog-cli ingest ./services/"]
        PARSE["parse_catalog_yaml()\n─────────────────\nExtracts structured fields\ninto typed columns.\nPreserves full raw YAML text\nfor embedding + retrieval."]
    end

    subgraph EMBED_MODEL ["🤖  Embedding Model — nomic-embed-text (137M params)\n     Ollama  ·  POST localhost:11434/api/embeddings"]
        EMBED["Reads the entire raw YAML\nas a single input string.\nComputes the semantic meaning\nof the whole document —\nnot just keywords."]
        VEC["Output: 768-dim float vector\n[ 0.032, −0.14, 0.87, … × 768 ]\n─────────────────\nEach service becomes a unique\npoint in 768-dimensional space.\nSimilar concerns → nearby points."]
    end

    subgraph DB ["🐘  PostgreSQL 16  +  pgvector extension"]
        UPSERT["INSERT … ON CONFLICT UPDATE\n─────────────────\nIdempotent upsert — safe to re-run.\nUpdates embedding if YAML changes."]
        ROW["service_catalog (one row per service)\n──────────────────────────────\nservice_name  VARCHAR  UNIQUE\nowner         VARCHAR\nlifecycle     VARCHAR\nmetadata      JSONB  (tags, deps, apis)\nraw_content   TEXT   (full YAML)\nembedding     VECTOR(768)"]
        HNSW["HNSW Index on embedding column\n─────────────────\nHierarchical Navigable Small World.\nPre-builds a graph of nearby vectors.\nEnables sub-millisecond cosine\nsimilarity search at query time —\neven across millions of rows."]
    end

    YAML -->|"1 · file or directory walk"| PARSE
    PARSE -->|"2 · raw_content string\nsent to embedding model"| EMBED
    EMBED --> VEC
    VEC -->|"3 · vector + structured fields\nbundled together"| UPSERT
    PARSE --> UPSERT
    UPSERT --> ROW
    ROW -.->|"index auto-updates\non every insert/update"| HNSW
```

### What the embedding model actually does

The embedding model (`nomic-embed-text`) converts the *meaning* of your entire
YAML description into a single array of 768 numbers.
This is not keyword indexing — it understands semantics.

A service that talks about *"fragile items, warehouse zones, handling rules"*
will produce a vector that is geometrically close to a question that asks about
*"adding a fragile item type to the order system"*, even if none of those exact
words appear in the question.

---

## Phase 2 — RAG Query

What happens when a user asks a requirements-gathering question.

> **Example question used:**
> *"We want to add a new 'fragile' item type to the order system.
> What services are affected and what changes are needed in each one?"*

```mermaid
sequenceDiagram
    actor User
    participant CLI  as 🖥️ catalog-cli ask<br/>─────────────<br/>catalog_cli/main.py<br/>catalog_cli/server.py
    participant Embed as 🤖 nomic-embed-text<br/>─────────────<br/>Ollama :11434<br/>/api/embeddings
    participant PG   as 🐘 pgvector<br/>─────────────<br/>PostgreSQL :5432<br/>HNSW index
    participant LLM  as 🧠 llama3.1:8b-instruct<br/>─────────────<br/>Ollama :11434<br/>/api/generate

    User->>CLI: Plain-English question

    rect rgb(220, 235, 255)
        Note over CLI,Embed: STEP 1 — Embed the question  (deterministic · ~50 ms · 0 tokens billed)
        CLI->>Embed: POST /api/embeddings<br/>{ model: "nomic-embed-text",<br/>  prompt: "…fragile item type…" }
        Note over Embed: Converts question text<br/>into the same 768-dim<br/>vector space used at ingestion.
        Embed-->>CLI: { "embedding": [0.021, −0.13, …] }<br/>768-dim query vector
    end

    rect rgb(220, 255, 220)
        Note over CLI,PG: STEP 2 — Semantic vector search  (deterministic · ~5 ms · 0 tokens billed)
        CLI->>PG: SELECT raw_content<br/>FROM service_catalog<br/>ORDER BY embedding <=> query_vec<br/>LIMIT 3
        Note over PG: HNSW index computes cosine distance<br/>between the query vector and every<br/>stored service embedding.<br/>Lower distance = more semantically similar.<br/>No keyword matching — pure geometry.
        PG-->>CLI: Ranked results (cosine distance):<br/>[1] order-service          ← closest<br/>[2] notification-service<br/>[3] inventory-service<br/>✗  payment-processing-service  ← ranked 4th, excluded
        Note over CLI: payment-processing-service was excluded<br/>because its embedding (payments, Stripe,<br/>credit cards) is geometrically far from<br/>"fragile items + order handling".
    end

    rect rgb(255, 245, 220)
        Note over CLI: STEP 3 — Build the RAG prompt  (no model · pure string assembly)
        CLI->>CLI: prompt =<br/>  system instructions<br/>  + order-service raw YAML<br/>  + notification-service raw YAML<br/>  + inventory-service raw YAML<br/>  + original question
        Note over CLI: The LLM will only ever see<br/>what is in these 3 YAMLs.<br/>It cannot invent services or<br/>migrations that aren't described here.
    end

    rect rgb(255, 220, 220)
        Note over CLI,LLM: STEP 4 — Generate the answer  (generative · ~60–300 s on CPU · local tokens only)
        CLI->>LLM: POST /api/generate<br/>{ model: "llama3.1:8b-instruct-q5_1",<br/>  prompt: …assembled above…,<br/>  stream: true }
        Note over LLM: Reads ONLY the injected catalog context.<br/>Reasons over what it finds there.<br/>Streams answer token by token.
        LLM-->>User: "1. order-service — DB migration on order_lines,<br/>   update OrderValidator (special_handling=true),<br/>   add handling_instructions to orders-created Kafka event<br/>2. inventory-service — add 'fragile' to item_class enum,<br/>   expose GET /products?item_class=fragile filter<br/>3. notification-service — new fragile_order_confirmation templates,<br/>   consume handling_instructions from Kafka event<br/>Recommended order: inventory-service → order-service → notification-service"
    end
```

---

## Key decisions and why they happen where they do

| Decision | Made by | Mechanism | Cost |
|---|---|---|---|
| Which services are relevant to the question? | **pgvector HNSW** | Cosine similarity between query vector and each row's embedding | 0 tokens · ~5 ms |
| Should payment-processing-service be included? | **pgvector HNSW** | Its vector is geometrically far from the query — ranked 4th, outside top-K | 0 tokens · automatic |
| What migrations are needed in order-service? | **llama3.1:8b** | Reads the injected order-service YAML and reasons over it | Local tokens only |
| Can the LLM invent a service that isn't in the catalog? | **RAG architecture** | Prompt is bounded by what pgvector returned — unknown services are invisible | Structurally impossible |
| Is the answer grounded in real catalog data? | **RAG architecture** | Every claim the LLM makes is traceable to one of the top-K YAML chunks | Yes, by design |

---

## Token cost breakdown

```
Step 1 — embed question:    local model, ~50 ms       → $0.00
Step 2 — vector search:     SQL query, ~5 ms          → $0.00
Step 3 — build prompt:      string concat             → $0.00
Step 4 — LLM generation:    local model, runs on CPU  → $0.00

Total external API cost:    $0.00
```

This is the "AI-first, zero external cost" design.
Deterministic commands (`list`, `get`, `tags`, `deps`, `diagram`) hit Postgres
directly and never touch a model at all.
Only `ask` runs inference, and both models run entirely on your machine via Ollama.

---

## Component map

```mermaid
flowchart LR
    subgraph LOCAL ["Your Machine"]
        subgraph OLLAMA ["Ollama  :11434"]
            NE["nomic-embed-text\n137M params · 274 MB\nEmbedding only"]
            LL["llama3.1:8b-instruct-q5_1\n8B params · 6.1 GB\nGeneration only"]
        end
        subgraph DOCKER ["Docker"]
            PG["PostgreSQL 16\n+ pgvector extension\nport 5432"]
        end
        subgraph APP ["catalog-cli / FastAPI"]
            C1["genai.embed()"]
            C2["db.vector_search()"]
            C3["genai.generate_stream()"]
        end
    end

    C1 <-->|"POST /api/embeddings"| NE
    C2 <-->|"SELECT … ORDER BY embedding <=> vec"| PG
    C3 <-->|"POST /api/generate stream=true"| LL
```

---

## Files involved in the pipeline

| File | Role in the pipeline |
|---|---|
| [`catalog_cli/genai.py`](../catalog_cli/genai.py) | Ollama client — `embed()` calls nomic-embed-text, `generate_stream()` calls llama3.1 |
| [`catalog_cli/db.py`](../catalog_cli/db.py) | `vector_search()` runs the pgvector cosine query, `upsert_service()` stores embeddings |
| [`catalog_cli/ingest.py`](../catalog_cli/ingest.py) | Parses YAML, calls `genai.embed()`, calls `db.upsert_service()` |
| [`catalog_cli/main.py`](../catalog_cli/main.py) | `ask` command — orchestrates embed → search → prompt → generate |
| [`catalog_cli/server.py`](../catalog_cli/server.py) | `POST /api/ask` — same pipeline over HTTP |
| [`catalog_cli/config.py`](../catalog_cli/config.py) | `OLLAMA_EMBED_MODEL`, `OLLAMA_GENERATE_MODEL`, `EMBEDDING_DIM`, `RAG_TOP_K` |
| [`init.sql`](../init.sql) / [`db/init.sql`](../db/init.sql) | Creates `VECTOR(768)` column and HNSW index on container start |
| [`services/*/catalog-info.yaml`](../services/) | Source data — parsed and embedded during ingestion |
