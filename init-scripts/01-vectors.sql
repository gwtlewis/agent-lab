-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Financial documents table - stores document metadata and full embeddings
CREATE TABLE IF NOT EXISTS financial_docs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    source_file VARCHAR(255),
    content TEXT,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Document chunks table - stores individual text chunks with embeddings for retrieval
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES financial_docs(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster similarity search
-- Note: IVFFlat doesn't support >2000 dimensions, using basic indexes instead
CREATE INDEX IF NOT EXISTS idx_financial_docs_title 
ON financial_docs(title);

CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id 
ON document_chunks(doc_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO postgres;
