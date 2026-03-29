#!/usr/bin/env python3
"""CLI tool for ingesting financial PDFs into pgvector"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from providers.llm_providers import get_provider  # noqa: E402
from rag.pdf_ingester import PDFIngestor  # noqa: E402


def get_embeddings_instance(provider: str = "ollama"):
    """Return a LangChain embeddings instance for the given provider.

    Args:
        provider: Provider name (``'ollama'`` or ``'openai'``).

    Returns:
        A LangChain embeddings object.

    Raises:
        ValueError: If the provider is unknown or not configured.
    """
    try:
        return get_provider(provider).get_embeddings()
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc


def build_db_url(host: str, port: int, user: str, password: str, db: str) -> str:
    """
    Build PostgreSQL connection string

    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        db: Database name

    Returns:
        Connection string
    """
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def ingest_single_pdf(pdf_path: str, args) -> dict:
    """
    Ingest a single PDF file

    Args:
        pdf_path: Path to PDF file
        args: Arguments namespace

    Returns:
        Ingestion result dictionary

    Raises:
        FileNotFoundError: If PDF doesn't exist
        Exception: If ingestion fails
    """
    # Validate file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError(f"File is not a PDF: {pdf_path}")

    # Get file size
    file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"\n📄 Ingesting: {Path(pdf_path).name}")
    print(f"   Size: {file_size_mb:.2f} MB")

    # Build database URL
    db_url = build_db_url(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        db=args.db_name,
    )

    # Get embeddings
    print(f"   Embeddings model: {args.embeddings}")
    embeddings = get_embeddings_instance(args.embeddings)

    # Create ingestor and ingest PDF
    ingestor = PDFIngestor(db_url, embeddings)

    # Extract title if not provided
    title = args.title or Path(pdf_path).stem

    # Ingest PDF
    result = ingestor.ingest_pdf(pdf_path, title=title)

    return result


def list_documents(args) -> list:
    """
    List all ingested documents

    Args:
        args: Arguments namespace

    Returns:
        List of documents
    """
    db_url = build_db_url(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        db=args.db_name,
    )

    embeddings = get_embeddings_instance(args.embeddings)
    ingestor = PDFIngestor(db_url, embeddings)

    documents = ingestor.list_documents()
    return documents


def delete_document(doc_id: int, args) -> bool:
    """
    Delete a document by ID

    Args:
        doc_id: Document ID to delete
        args: Arguments namespace

    Returns:
        True if deleted, False otherwise
    """
    db_url = build_db_url(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        db=args.db_name,
    )

    embeddings = get_embeddings_instance(args.embeddings)
    ingestor = PDFIngestor(db_url, embeddings)

    return ingestor.delete_document(doc_id)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Ingest financial PDFs into pgvector for RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest a single PDF
  %(prog)s ingest path/to/document.pdf
  
  # Ingest PDF with custom title
  %(prog)s ingest path/to/document.pdf --title "Q1 2024 Report"
  
  # Use OpenAI embeddings
  %(prog)s ingest path/to/document.pdf --embeddings openai
  
  # Ingest multiple PDFs
  %(prog)s ingest path/to/*.pdf
  
  # List all ingested documents
  %(prog)s list
  
  # Delete a document by ID
  %(prog)s delete 1
  
  # Use custom database settings
  %(prog)s ingest document.pdf --db-host db.example.com --db-port 5432
        """,
    )

    # Global database arguments
    parser.add_argument(
        "--db-host",
        default=os.getenv("POSTGRES_HOST", "localhost"),
        help="Database host (default: localhost)",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=int(os.getenv("POSTGRES_PORT", 5432)),
        help="Database port (default: 5432)",
    )
    parser.add_argument(
        "--db-user",
        default=os.getenv("POSTGRES_USER", "postgres"),
        help="Database user (default: postgres)",
    )
    parser.add_argument(
        "--db-password",
        default=os.getenv("POSTGRES_PASSWORD", "postgres"),
        help="Database password (default: postgres)",
    )
    parser.add_argument(
        "--db-name",
        default=os.getenv("POSTGRES_DB", "postgres"),
        help="Database name (default: postgres)",
    )
    parser.add_argument(
        "--embeddings",
        choices=["ollama", "openai"],
        default=os.getenv("EMBEDDINGS_PROVIDER", "ollama"),
        help="Embeddings model provider (default: ollama)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest PDF file(s)")
    ingest_parser.add_argument(
        "pdf_paths", nargs="+", help="Path(s) to PDF file(s) to ingest"
    )
    ingest_parser.add_argument(
        "--title", help="Document title (if not provided, filename will be used)"
    )
    ingest_parser.add_argument(
        "--verbose", action="store_true", help="Print detailed output"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List all ingested documents")
    list_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete ingested document")
    delete_parser.add_argument("doc_id", type=int, help="Document ID to delete")
    delete_parser.add_argument(
        "--force", action="store_true", help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "ingest":
            # Ingest PDFs
            results = []
            total_chunks = 0
            total_pages = 0

            for pdf_path in args.pdf_paths:
                try:
                    result = ingest_single_pdf(pdf_path, args)
                    results.append(result)
                    total_chunks += result["chunks"]
                    total_pages += result["pages"]
                    print(
                        f"   ✓ Doc ID: {result['doc_id']} | {result['chunks']} chunks from {result['pages']} pages"
                    )
                except Exception as e:
                    print(f"   ✗ Error: {e}", file=sys.stderr)

            # Summary
            if results:
                print(f"\n📊 Ingestion Summary")
                print(f"   Documents ingested: {len(results)}")
                print(f"   Total pages: {total_pages}")
                print(f"   Total chunks: {total_chunks}")
                print(f"   ✓ Success!")
            else:
                print("No PDFs were successfully ingested.", file=sys.stderr)
                sys.exit(1)

        elif args.command == "list":
            # List documents
            documents = list_documents(args)

            if not documents:
                print("No documents found in database.")
            elif args.format == "json":
                import json

                print(json.dumps(documents, indent=2, default=str))
            else:
                # Table format
                print(
                    f"\n{'ID':<5} {'Title':<40} {'Pages':<8} {'Chunks':<8} {'Created':<20}"
                )
                print("─" * 85)
                for doc in documents:
                    metadata = doc.get("metadata", {})
                    pages = metadata.get("page_count", "N/A")
                    chunks = metadata.get("chunk_count", "N/A")
                    created = str(doc.get("created_at", "N/A"))[:19]
                    title = doc.get("title", "Unknown")[:38]
                    print(
                        f"{doc['id']:<5} {title:<40} {str(pages):<8} {str(chunks):<8} {created:<20}"
                    )

        elif args.command == "delete":
            # Delete document
            doc_id = args.doc_id

            if not args.force:
                confirm = input(f"⚠️  Delete document {doc_id}? (yes/no): ")
                if confirm.lower() != "yes":
                    print("Cancelled.")
                    sys.exit(0)

            success = delete_document(doc_id, args)
            if success:
                print(f"✓ Document {doc_id} deleted successfully.")
            else:
                print(f"⚠️  Document {doc_id} not found.", file=sys.stderr)
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nCancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if args.verbose if hasattr(args, "verbose") else False:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
