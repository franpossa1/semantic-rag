#!/usr/bin/env python3
"""CLI script to fetch technical documentation from GitHub.

Usage:
    python fetch_docs.py              # Download all libraries
    python fetch_docs.py --force      # Re-download all (overwrite existing)
    python fetch_docs.py --library fastapi  # Download only FastAPI docs
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.scraper import DocsScraper, LIBRARY_SOURCES


def main():
    parser = argparse.ArgumentParser(
        description="Download technical documentation from GitHub repos"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist",
    )
    parser.add_argument(
        "--library",
        choices=["langchain", "fastapi", "python", "all"],
        default="all",
        help="Which library to download (default: all)",
    )
    parser.add_argument(
        "--output",
        default="raw/docs",
        help="Output directory (default: raw/docs)",
    )

    args = parser.parse_args()

    async def run():
        scraper = DocsScraper(output_dir=args.output)

        if args.library == "all":
            print("Fetching documentation for all libraries...\n")
            results = await scraper.fetch_all(force=args.force)

            print("\n" + "=" * 50)
            print("Download Complete")
            print("=" * 50)
            total = 0
            for library, count in results.items():
                print(f"  {library:12} : {count:4} files")
                total += count
            print("-" * 50)
            print(f"  {'Total':12} : {total:4} files")
            print(f"\nSaved to: {Path(args.output).absolute()}")
        else:
            source = next(
                (s for s in LIBRARY_SOURCES if s["library"] == args.library), None
            )
            if not source:
                print(f"Unknown library: {args.library}")
                return 1

            print(f"📚 Fetching {args.library} documentation...\n")
            count = await scraper.fetch_library_docs(
                library=source["library"],
                owner=source["owner"],
                repo=source["repo"],
                docs_path=source["docs_path"],
                branch=source["branch"],
                extensions=source["extensions"],
                force=args.force,
            )

            print(f"\n✅ Downloaded {count} files to {Path(args.output).absolute()}")

        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
