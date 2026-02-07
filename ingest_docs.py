#!/usr/bin/env python3
"""CLI script to ingest documentation into ChromaDB.

Usage:
    python ingest_docs.py              # Ingest all libraries
    python ingest_docs.py --library fastapi  # Ingest only FastAPI
    python ingest_docs.py --clear      # Clear and re-ingest everything
    python ingest_docs.py --stats      # Show collection stats
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.db.chromadb import ChromaDBHandler
from src.services.ingest import IngestService


def main():
    parser = argparse.ArgumentParser(
        description="Ingest technical documentation into ChromaDB"
    )
    parser.add_argument(
        "--library",
        choices=["langchain", "fastapi", "python", "all"],
        default="all",
        help="Which library to ingest (default: all)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing collection before ingesting",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show collection statistics and exit",
    )
    parser.add_argument(
        "--raw-path",
        default="raw/docs",
        help="Path to raw documentation (default: raw/docs)",
    )
    parser.add_argument(
        "--db-path",
        default="./data",
        help="Path to ChromaDB data (default: ./data)",
    )

    args = parser.parse_args()

    async def run():
        # Initialize database and ingest service
        db = ChromaDBHandler(path=args.db_path)
        ingest_service = IngestService(db, raw_docs_path=args.raw_path)

        if args.stats:
            count = db.count("technical_docs")
            print(f"Collection 'technical_docs' has {count} documents")
            return 0

        if args.clear:
            print("Clearing and re-ingesting all documentation...")
            results = await ingest_service.clear_and_reingest()
        elif args.library == "all":
            print("Ingesting documentation for all libraries...")
            results = await ingest_service.ingest_all()
        else:
            print(f"Ingesting {args.library} documentation...")
            count = await ingest_service.ingest_library(args.library)
            results = {args.library: count}

        # Print summary
        print("\n" + "=" * 50)
        print("Ingest Complete")
        print("=" * 50)
        total = 0
        for library, count in results.items():
            print(f"  {library:12} : {count:5} chunks")
            total += count
        print("-" * 50)
        print(f"  {'Total':12} : {total:5} chunks")

        # Verify in database
        db_count = db.count("technical_docs")
        print(f"\nDatabase verification: {db_count} total documents in collection")

        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
