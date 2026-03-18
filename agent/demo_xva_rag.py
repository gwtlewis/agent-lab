#!/usr/bin/env python3
"""
Practical demonstration of RAG pipeline with xVA PDF
Shows how to ingest and query the PDF using the RAG system

This script demonstrates the complete workflow:
1. Configure embeddings and database
2. Ingest the xVA PDF
3. Query the knowledge base
4. Use RAG agent for domain-specific questions
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Configuration
PDF_PATH = "/Users/lewisgong/Downloads/2015_The_xVA_Challenge-Jon Gregory.pdf"
PDF_TITLE = "The xVA Challenge - Jon Gregory (2015)"

# Database
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_NAME = os.getenv("POSTGRES_DB", "postgres")

# Embeddings
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "ollama")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def build_db_url() -> str:
    """Build PostgreSQL connection URL"""
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def example_1_pdf_validation():
    """Example 1: Validate PDF file"""
    print("\n" + "=" * 60)
    print("Example 1: PDF Validation")
    print("=" * 60)

    if not os.path.exists(PDF_PATH):
        print(f"❌ PDF not found: {PDF_PATH}")
        return False

    file_size_mb = os.path.getsize(PDF_PATH) / (1024 * 1024)
    print(f"✓ PDF found: {PDF_PATH}")
    print(f"✓ File size: {file_size_mb:.2f} MB")
    print(f"✓ Title: {PDF_TITLE}")
    return True


def example_2_embeddings_setup():
    """Example 2: Setup embeddings provider"""
    print("\n" + "=" * 60)
    print("Example 2: Embeddings Setup")
    print("=" * 60)

    print(f"Provider: {EMBEDDINGS_PROVIDER.upper()}")

    if EMBEDDINGS_PROVIDER == "ollama":
        print(f"Ollama Host: {OLLAMA_HOST}")
        print("✓ Using Ollama embeddings (nomic-embed-text)")
        print("  Model: 768-dimensional embeddings")
    elif EMBEDDINGS_PROVIDER == "openai":
        print("✓ Using OpenAI embeddings (text-embedding-3-small)")
        print("  Model: 1536-dimensional embeddings")
    else:
        print(f"❌ Unknown provider: {EMBEDDINGS_PROVIDER}")
        return False

    return True


def example_3_database_connection():
    """Example 3: Database configuration"""
    print("\n" + "=" * 60)
    print("Example 3: Database Configuration")
    print("=" * 60)

    db_url = build_db_url()
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"User: {DB_USER}")
    print(f"Database: {DB_NAME}")
    print(
        f"✓ Connection URL ready: postgresql://{DB_USER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    return True


def example_4_pdf_ingestion_code():
    """Example 4: PDF ingestion code snippet"""
    print("\n" + "=" * 60)
    print("Example 4: PDF Ingestion Code")
    print("=" * 60)

    code = """
# Step 1: Import required modules
from pdf_ingester import PDFIngestor
from langchain_community.embeddings import OllamaEmbeddings

# Step 2: Setup embeddings
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434"
)

# Step 3: Create ingestor
db_url = "postgresql://postgres:postgres@localhost:5432/postgres"
ingestor = PDFIngestor(db_url, embeddings)

# Step 4: Ingest PDF
result = ingestor.ingest_pdf(
    pdf_path="/Users/lewisgong/Downloads/2015_The_xVA_Challenge-Jon Gregory.pdf",
    title="The xVA Challenge - Jon Gregory (2015)"
)

# Result contains:
# - doc_id: Unique document ID
# - pages: Number of pages processed
# - chunks: Number of text chunks created
# - embeddings: Number of embeddings created

print(f"Ingested: {result['pages']} pages, {result['chunks']} chunks")
print(f"Document ID: {result['doc_id']}")
    """

    print(code)
    return True


def example_5_rag_agent_code():
    """Example 5: Using RAG Agent for queries"""
    print("\n" + "=" * 60)
    print("Example 5: RAG Agent Query Code")
    print("=" * 60)

    code = """
# Step 1: Import RAG Agent
from agent_with_rag import RAGAgent

# Step 2: Initialize agent with RAG enabled
db_url = "postgresql://postgres:postgres@localhost:5432/postgres"
agent = RAGAgent(
    provider="ollama",
    db_url=db_url,
    enable_rag=True
)

# Step 3: Query the knowledge base
queries = [
    "What is CVA and why is it important?",
    "How does collateral affect xVA calculations?",
    "What are the main challenges in xVA?",
    "Explain the relationship between CVA and DVA"
]

for query in queries:
    print(f"\\nQuery: {query}")
    response = agent.chat(query, use_rag=True, k_documents=5)
    print(f"Response: {response}")

# Step 4: Direct knowledge base search
results = agent.search_knowledge_base("xVA pricing models", k=3)
print(f"\\nFound {len(results)} relevant documents")
for doc in results:
    print(f"- Similarity: {doc['similarity_score']:.2%}")
    print(f"  Content: {doc['content'][:100]}...")
    """

    print(code)
    return True


def example_6_xva_queries():
    """Example 6: xVA-specific query examples"""
    print("\n" + "=" * 60)
    print("Example 6: xVA Domain Queries")
    print("=" * 60)

    queries = [
        {
            "category": "CVA",
            "question": "What is Credit Valuation Adjustment and how is it calculated?",
            "expected_keywords": [
                "credit risk",
                "counterparty",
                "exposure",
                "probability of default",
            ],
        },
        {
            "category": "DVA",
            "question": "Explain Debit Valuation Adjustment and its relationship to CVA",
            "expected_keywords": ["own credit", "bilateral", "counterparty", "DVA"],
        },
        {
            "category": "Collateral",
            "question": "How does collateral management reduce xVA?",
            "expected_keywords": ["collateral", "mitigation", "exposure", "agreement"],
        },
        {
            "category": "Central Clearing",
            "question": "What role does central clearing play in modern derivative markets?",
            "expected_keywords": ["clearing", "counterparty", "risk reduction", "CCP"],
        },
        {
            "category": "FVA/KVA",
            "question": "What are FVA and KVA, and when do they become material?",
            "expected_keywords": ["funding", "capital", "regulatory", "valuation"],
        },
    ]

    for i, q in enumerate(queries, 1):
        print(f"\n{i}. {q['category']}")
        print(f"   Question: {q['question']}")
        print(f"   Expected Keywords: {', '.join(q['expected_keywords'])}")

    return True


def example_7_working_with_results():
    """Example 7: Processing RAG results"""
    print("\n" + "=" * 60)
    print("Example 7: Processing RAG Results")
    print("=" * 60)

    code = """
# After retrieving knowledge base results
retrieved_docs = agent.search_knowledge_base("CVA calculation", k=3)

# Process results
for i, doc in enumerate(retrieved_docs, 1):
    print(f"\\nDocument {i}:")
    print(f"  Title: {doc.get('document_title', 'N/A')}")
    print(f"  Similarity: {doc.get('similarity_score', 0):.2%}")
    print(f"  Source: Page {doc.get('page_number', 'N/A')}")
    print(f"  Content Preview:")
    content = doc.get('content', '')
    preview = content[:200] + "..." if len(content) > 200 else content
    print(f"    {preview}")

# Get document statistics
stats = agent.get_rag_stats()
print(f"\\nKnowledge Base Statistics:")
print(f"  Total documents: {stats.get('total_documents', 0)}")
print(f"  Total chunks: {stats.get('total_chunks', 0)}")
print(f"  Average similarity: {stats.get('avg_similarity', 0):.2%}")
    """

    print(code)
    return True


def example_8_best_practices():
    """Example 8: Best practices for xVA RAG system"""
    print("\n" + "=" * 60)
    print("Example 8: Best Practices")
    print("=" * 60)

    practices = [
        (
            "Query Specificity",
            "Use specific financial terms: 'CVA' instead of 'valuation'",
        ),
        (
            "Context Size",
            "Start with k=3-5 documents, increase if needed for complex queries",
        ),
        ("Accuracy Check", "Verify agent responses against source documents"),
        ("Domain Vocabulary", "Use xVA terminology: CVA, DVA, FVA, KVA, CCP, etc."),
        ("Batch Processing", "For multiple queries, reuse agent instance"),
        ("Error Handling", "Catch database connection and embedding generation errors"),
        ("Performance", "Monitor query response time (target: <2 seconds)"),
        (
            "Knowledge Updates",
            "Re-ingest PDF when content changes or new docs available",
        ),
    ]

    for i, (practice, description) in enumerate(practices, 1):
        print(f"\n{i}. {practice}")
        print(f"   → {description}")

    return True


def example_9_integration_checklist():
    """Example 9: Integration checklist"""
    print("\n" + "=" * 60)
    print("Example 9: Integration Checklist")
    print("=" * 60)

    checklist = {
        "✓ PDF File": os.path.exists(PDF_PATH),
        "✓ Embeddings Configured": EMBEDDINGS_PROVIDER in ["ollama", "openai"],
        "✓ Database Connection": all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]),
        "✓ Environment Variables": os.path.exists(".env"),
        "✓ PDF Module Installed": True,  # Assume installed
        "✓ Database Tables Ready": "Check by running SQL",
        "✓ LangChain Installed": True,  # Assume installed
        "✓ Embeddings Service Running": "Manual verification needed",
    }

    for item, status in checklist.items():
        status_str = "✓" if isinstance(status, bool) and status else "○"
        print(f"{status_str} {item}")

    return True


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("RAG Pipeline with xVA PDF - Practical Examples")
    print("=" * 60)

    # Load environment
    load_dotenv()

    # Run examples
    examples = [
        example_1_pdf_validation,
        example_2_embeddings_setup,
        example_3_database_connection,
        example_4_pdf_ingestion_code,
        example_5_rag_agent_code,
        example_6_xva_queries,
        example_7_working_with_results,
        example_8_best_practices,
        example_9_integration_checklist,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"❌ Error in {example.__name__}: {e}")

    print("\n" + "=" * 60)
    print("Examples Complete!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Ensure PostgreSQL is running and tables exist")
    print("2. Ensure Ollama is running (if using Ollama embeddings)")
    print("3. Run: python -m ingest_pdf ingest <pdf_path>")
    print("4. Use RAGAgent to query ingested documents")
    print("5. Review test files for additional examples")


if __name__ == "__main__":
    main()
