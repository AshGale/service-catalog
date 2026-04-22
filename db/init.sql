-- Runs once on first container start via docker-entrypoint-initdb.d.
-- For subsequent schema changes, use: catalog-cli init-db

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS service_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(255) UNIQUE NOT NULL,
    owner VARCHAR(255),
    lifecycle VARCHAR(50),
    metadata JSONB,
    raw_content TEXT,
    -- 1536 dims fits within pgvector's HNSW limit of 2000; update if your model differs
    embedding VECTOR(1536),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS service_catalog_embedding_idx
    ON service_catalog USING hnsw (embedding vector_cosine_ops);
