# Financial PDF Ingestion CLI - Usage Guide

**Last Updated**: 2026-03-16  
**Version**: 1.0.0

## Overview

The `ingest_pdf.py` CLI tool is a command-line interface for ingesting financial PDF documents into PostgreSQL with pgvector embeddings, enabling semantic search and Retrieval Augmented Generation (RAG).

```
PDF Files
    ↓
[ingest_pdf.py] → Parse & Chunk
    ↓
[Embeddings] → Generate (Ollama/OpenAI)
    ↓
[PostgreSQL + pgvector] → Store & Index
```

---

## Prerequisites

### System Requirements
- Python 3.8+
- PostgreSQL 17.9+ with pgvector extension
- Ollama (for local embeddings) OR OpenAI API key

### Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Start PostgreSQL with pgvector**:
```bash
docker-compose up -d
```

3. **Verify database connection**:
```bash
psql -h localhost -U postgres -d postgres
SELECT extname FROM pg_extension WHERE extname='vector';
```

4. **Run initialization script** (if not done automatically):
```bash
docker-compose exec db psql -U postgres -f /docker-entrypoint-initdb.d/01-vectors.sql
```

---

## Quick Start

### 1. Ingest a Single PDF

```bash
./ingest_pdf.py ingest path/to/document.pdf
```

**Output**:
```
📄 Ingesting: document.pdf
   Size: 2.45 MB
   Embeddings model: ollama
✓ Doc ID: 1 | 45 chunks from 10 pages

📊 Ingestion Summary
   Documents ingested: 1
   Total pages: 10
   Total chunks: 45
   ✓ Success!
```

### 2. List All Ingested Documents

```bash
./ingest_pdf.py list
```

**Output**:
```
ID    Title                                    Pages    Chunks   Created
─────────────────────────────────────────────────────────────────────────
1     annual-report-2024                       10       45       2024-03-11 14:30:15
2     quarterly-statement-q1                   12       60       2024-03-11 14:32:22
```

### 3. Delete a Document

```bash
./ingest_pdf.py delete 1
```

**Interactive confirmation**:
```
⚠️  Delete document 1? (yes/no): yes
✓ Document 1 deleted successfully.
```

---

## Command Reference

### `ingest` - Ingest PDF Files

**Syntax**:
```bash
./ingest_pdf.py ingest PDF_PATH [PDF_PATH ...] [OPTIONS]
```

**Arguments**:
- `PDF_PATH` - Path(s) to PDF file(s) to ingest (required)
  - Can be a single file: `documents/report.pdf`
  - Can use wildcards: `documents/*.pdf`
  - Can specify multiple: `doc1.pdf doc2.pdf doc3.pdf`

**Options**:
```
--title TITLE              Document title (overrides filename)
--embeddings MODEL         Embeddings provider: 'ollama' or 'openai' (default: ollama)
--db-host HOST            Database host (default: localhost)
--db-port PORT            Database port (default: 5432)
--db-user USER            Database user (default: postgres)
--db-password PASSWORD    Database password (default: postgres)
--db-name NAME            Database name (default: postgres)
--verbose                 Print detailed output
--help                    Show help message
```

**Examples**:

```bash
# Basic ingestion
./ingest_pdf.py ingest report.pdf

# With custom title
./ingest_pdf.py ingest report.pdf --title "Annual Report 2024"

# Using OpenAI embeddings
./ingest_pdf.py ingest report.pdf --embeddings openai

# Multiple files with wildcard
./ingest_pdf.py ingest documents/*.pdf

# Custom database
./ingest_pdf.py ingest report.pdf \
  --db-host db.company.com \
  --db-port 5432 \
  --db-user admin \
  --db-password secret

# Verbose output
./ingest_pdf.py ingest report.pdf --verbose
```

---

### `list` - List Ingested Documents

**Syntax**:
```bash
./ingest_pdf.py list [OPTIONS]
```

**Options**:
```
--format FORMAT           Output format: 'table' or 'json' (default: table)
--embeddings MODEL        Embeddings provider (default: ollama)
--db-host HOST           Database host
--db-port PORT           Database port
--db-user USER           Database user
--db-password PASSWORD   Database password
--db-name NAME           Database name
--help                   Show help message
```

**Examples**:

```bash
# List in table format (default)
./ingest_pdf.py list

# List in JSON format
./ingest_pdf.py list --format json

# Output:
# {
#   "id": 1,
#   "title": "Annual Report 2024",
#   "source_file": "/path/to/report.pdf",
#   "metadata": {
#     "page_count": 10,
#     "chunk_count": 45
#   },
#   "created_at": "2024-03-11T14:30:15"
# }
```

---

### `delete` - Delete Document

**Syntax**:
```bash
./ingest_pdf.py delete DOC_ID [OPTIONS]
```

**Arguments**:
- `DOC_ID` - Document ID to delete (required)

**Options**:
```
--force                   Skip confirmation prompt
--embeddings MODEL        Embeddings provider
--db-host HOST           Database host
--db-port PORT           Database port
--db-user USER           Database user
--db-password PASSWORD   Database password
--db-name NAME           Database name
--help                   Show help message
```

**Examples**:

```bash
# Interactive deletion (with confirmation)
./ingest_pdf.py delete 1

# Force delete without confirmation
./ingest_pdf.py delete 1 --force

# Delete from remote database
./ingest_pdf.py delete 1 --db-host db.example.com --force
```

---

## Environment Variables

### Configuration Files

Create a `.env` file in the `agent/` directory:

```bash
# Database Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres

# Embeddings Model
EMBEDDINGS_PROVIDER=ollama

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434

# OpenAI Configuration (optional)
OPENAI_API_KEY=sk-your-api-key-here
```

### Precedence

Command-line arguments override environment variables:

```bash
# Use environment variable for embeddings (if set)
./ingest_pdf.py ingest document.pdf

# Command-line overrides environment variable
./ingest_pdf.py ingest document.pdf --embeddings openai
```

---

## Advanced Usage

### Batch Ingestion

Ingest all PDFs in a directory:

```bash
./ingest_pdf.py ingest financial_reports/*.pdf
```

Track ingestion progress:

```bash
for pdf in financial_reports/*.pdf; do
    echo "Processing $pdf..."
    ./ingest_pdf.py ingest "$pdf" --verbose
done
```

### Using Different Embeddings Models

**Ollama (default - local)**:
```bash
# Uses: nomic-embed-text (local)
./ingest_pdf.py ingest report.pdf --embeddings ollama
```

**OpenAI (remote)**:
```bash
# Uses: text-embedding-3-small
export OPENAI_API_KEY=sk-...
./ingest_pdf.py ingest report.pdf --embeddings openai
```

### Remote Database Ingestion

```bash
./ingest_pdf.py ingest document.pdf \
  --db-host prod-db.example.com \
  --db-port 5432 \
  --db-user etl_user \
  --db-password secure_password \
  --db-name financial_db
```

### Export Documents (via list)

```bash
# Export to JSON file
./ingest_pdf.py list --format json > documents.json

# Process with jq
./ingest_pdf.py list --format json | jq '.[] | {id, title}'
```

---

## Troubleshooting

### Connection Errors

```
Error: Failed to connect to database: connection refused
```

**Solution**:
```bash
# Check database is running
docker-compose ps

# Start if not running
docker-compose up -d

# Verify connection
psql -h localhost -U postgres -d postgres -c "SELECT 1"
```

### Ollama Not Found

```
Error: Could not connect to Ollama server at http://localhost:11434
```

**Solution**:
```bash
# Start Ollama
ollama serve

# In another terminal, pull the embedding model
ollama pull nomic-embed-text

# Test connection
curl http://localhost:11434/api/tags
```

### OpenAI API Error

```
Error: OPENAI_API_KEY not configured in .env
```

**Solution**:
```bash
# Set API key
export OPENAI_API_KEY=sk-...

# Or add to .env
echo "OPENAI_API_KEY=sk-..." >> agent/.env
```

### PDF Parsing Error

```
Error: No content extracted from PDF: report.pdf
```

**Solutions**:
1. Verify PDF is not corrupted: `file report.pdf`
2. Try with Verbose mode: `./ingest_pdf.py ingest report.pdf --verbose`
3. Check PDF is text-based (not image-only)

### Embedding Generation Timeout

```
Error: Embedding generation timed out
```

**Solutions**:
1. Increase timeout in `pdf_ingester.py`
2. Use faster embeddings model
3. Reduce chunk size in configuration
4. Try with fewer documents first

---

## Performance Optimization

### Parallel Ingestion

```bash
# Process multiple files in parallel (using GNU Parallel)
cat file_list.txt | parallel -j 4 './ingest_pdf.py ingest {}'

# Or with xargs
ls documents/*.pdf | xargs -P 4 -I {} ./ingest_pdf.py ingest {}
```

### Chunk Size Tuning

Edit `pdf_ingester.py`:

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # Increase for longer chunks
    chunk_overlap=200,    # Increase for more overlap
)
```

- **Smaller chunks** (500): Better for precise retrieval, more embeddings
- **Larger chunks** (2000): Faster processing, more context per chunk

### Database Optimization

```bash
# Analyze query performance
./ingest_pdf.py list --verbose

# Rebuild indexes if needed
docker-compose exec db psql -U postgres <<EOF
REINDEX TABLE document_chunks;
REINDEX TABLE financial_docs;
EOF
```

---

## Integration with Agent

Use the ingested documents in your RAG agent:

```python
from agent_with_rag import RAGAgent

# Initialize agent with RAG
agent = RAGAgent(
    provider="ollama",
    db_url="postgresql://postgres:postgres@localhost:5432/postgres",
    enable_rag=True
)

# Query with financial knowledge
response = agent.chat("What was the company's revenue growth?")

# Search knowledge base directly
results = agent.search_knowledge_base("revenue", k=5)
```

---

## API Reference

### PDFIngestor Class

```python
from pdf_ingester import PDFIngestor

# Initialize
ingestor = PDFIngestor(db_url, embeddings)

# Ingest PDF
result = ingestor.ingest_pdf(pdf_path, title="Custom Title")
# Returns: {doc_id, title, pages, chunks, status}

# List documents
docs = ingestor.list_documents()

# Delete document
success = ingestor.delete_document(doc_id)
```

### Return Values

**Ingestion Result**:
```python
{
    "doc_id": 1,
    "title": "Annual Report 2024",
    "pages": 10,
    "chunks": 45,
    "status": "success"
}
```

**Document Listing**:
```python
[
    {
        "id": 1,
        "title": "Annual Report 2024",
        "source_file": "/path/to/report.pdf",
        "metadata": {
            "page_count": 10,
            "chunk_count": 45,
            "file_name": "report.pdf"
        },
        "created_at": "2024-03-11T14:30:15"
    }
]
```

---

## Common Workflows

### Workflow 1: Ingest → Query → Use in Agent

```bash
# 1. Ingest financial documents
./ingest_pdf.py ingest documents/annual_report_2024.pdf
./ingest_pdf.py ingest documents/quarterly_q1.pdf

# 2. Verify ingestion
./ingest_pdf.py list

# 3. Use in agent
python3 -c "
from agent_with_rag import RAGAgent
agent = RAGAgent(enable_rag=True)
print(agent.chat('What was the revenue?'))
"
```

### Workflow 2: Batch Processing with Error Tracking

```bash
#!/bin/bash
LOG_FILE="ingestion.log"

for pdf in documents/*.pdf; do
    echo "Processing $pdf..." | tee -a $LOG_FILE
    if ./ingest_pdf.py ingest "$pdf" >> $LOG_FILE 2>&1; then
        echo "✓ Success" | tee -a $LOG_FILE
    else
        echo "✗ Failed" | tee -a $LOG_FILE
    fi
done
```

### Workflow 3: Cleanup and Re-Index

```bash
#!/bin/bash
# List all document IDs
./ingest_pdf.py list --format json | jq '.[] | .id' | while read id; do
    echo "Deleting document $id..."
    ./ingest_pdf.py delete $id --force
done

# Re-ingest fresh documents
./ingest_pdf.py ingest documents/*.pdf
```

---

## Best Practices

1. **Test first**: Ingest a small sample PDF before batch operations
2. **Monitor resources**: Check CPU/memory during ingestion
3. **Use appropriate titles**: Makes documents easier to find later
4. **Verify embeddings**: Test with `./ingest_pdf.py list` after ingestion
5. **Backup database**: Before large deletions or migrations
6. **Document your process**: Keep script for reproducibility

---

## Support & Debugging

### Enable Verbose Mode

```bash
./ingest_pdf.py ingest document.pdf --verbose
```

### View Raw SQL Logs

```bash
docker-compose logs db | grep "SELECT\|INSERT"
```

### Test Embeddings Connection

```bash
python3 -c "
from ingest_pdf import get_embeddings_instance
embeddings = get_embeddings_instance('ollama')
print(embeddings.embed_query('test'))
"
```

### Database Health Check

```bash
docker-compose exec db psql -U postgres <<EOF
SELECT count(*) as total_docs FROM financial_docs;
SELECT count(*) as total_chunks FROM document_chunks;
SELECT count(*) as indexed_chunks FROM document_chunks WHERE embedding IS NOT NULL;
EOF
```

---

## Contributing

To contribute improvements:

1. File an issue in the project repository
2. Submit a pull request with:
   - Updated code
   - New/updated tests (`test_ingest_pdf.py`)
   - Documentation updates

---

**For more information, see**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [AGENT.md](AGENT.md) - Agent configuration
- [README.md](README.md) - Project overview
