"""Scraper service for downloading documentation from GitHub repos."""

import asyncio
import os
from pathlib import Path

import httpx

LIBRARY_SOURCES = [
    {
        "library": "langchain",
        "owner": "langchain-ai",
        "repo": "docs",
        "docs_path": "reference/python/docs",
        "branch": "main",
        "extensions": [".md", ".mdx"],
    },
    {
        "library": "fastapi",
        "owner": "fastapi",
        "repo": "fastapi",
        "docs_path": "docs/en/docs",
        "branch": "master",
        "extensions": [".md"],
    },
    {
        "library": "python",
        "owner": "python",
        "repo": "cpython",
        "docs_path": "Doc/tutorial",
        "branch": "main",
        "extensions": [".rst"],
    },
]


class DocsScraper:
    """Downloads documentation from GitHub repos."""

    def __init__(self, output_dir: str = "raw/docs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.github_token = os.getenv("GITHUB_TOKEN")

    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers

    async def fetch_github_tree(
        self, owner: str, repo: str, branch: str = "main"
    ) -> list[dict]:
        """Fetch the full file tree of a GitHub repo using the Git Trees API.

        Uses: GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
        Returns list of file entries with path, type, size.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

        return [item for item in data.get("tree", []) if item.get("type") == "blob"]

    async def download_file(
        self, owner: str, repo: str, branch: str, file_path: str
    ) -> str:
        """Download a single raw file from GitHub.

        Uses: https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}
        Returns the file content as string.
        """
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.text

    async def fetch_library_docs(
        self,
        library: str,
        owner: str,
        repo: str,
        docs_path: str,
        branch: str = "main",
        extensions: list[str] | None = None,
        force: bool = False,
    ) -> int:
        """Download all docs for a library.

        1. Fetch the repo tree
        2. Filter files that start with docs_path and match extensions
        3. Download each file
        4. Save to raw/docs/{library}/ preserving directory structure
        5. Return count of files downloaded
        """
        if extensions is None:
            extensions = [".md"]

        # Create library output directory
        lib_output = self.output_dir / library
        lib_output.mkdir(parents=True, exist_ok=True)

        print(f"Fetching tree for {library}...")
        tree = await self.fetch_github_tree(owner, repo, branch)

        # Filter files by path and extension
        docs_files = [
            item
            for item in tree
            if item.get("path", "").startswith(docs_path)
            and any(item.get("path", "").endswith(ext) for ext in extensions)
            and item.get("size", 0) < 500_000  # Skip files > 500KB
        ]

        total = len(docs_files)
        downloaded = 0
        skipped = 0

        print(f"Downloading {library}: 0/{total} files")

        for idx, item in enumerate(docs_files, 1):
            file_path = item["path"]
            relative_path = file_path[len(docs_path) :].lstrip("/")
            output_file = lib_output / relative_path

            # Check if file already exists
            if output_file.exists() and not force:
                skipped += 1
                print(f"Downloading {library}: {idx}/{total} files (skipped)")
                continue

            try:
                content = await self.download_file(owner, repo, branch, file_path)

                # Create parent directories
                output_file.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                output_file.write_text(content, encoding="utf-8")
                downloaded += 1

                print(f"Downloading {library}: {idx}/{total} files")

            except Exception as e:
                print(f"Error downloading {file_path}: {e}")

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        print(f"\n{library} complete: {downloaded} downloaded, {skipped} skipped")
        return downloaded

    async def fetch_all(self, force: bool = False) -> dict[str, int]:
        """Download docs for all three libraries.

        Returns dict with counts: {"langchain": 150, "fastapi": 80, "python": 30}
        """
        results = {}

        for source in LIBRARY_SOURCES:
            count = await self.fetch_library_docs(
                library=source["library"],
                owner=source["owner"],
                repo=source["repo"],
                docs_path=source["docs_path"],
                branch=source["branch"],
                extensions=source["extensions"],
                force=force,
            )
            results[source["library"]] = count

        return results


async def main():
    """CLI entry point for testing the scraper."""
    scraper = DocsScraper()
    results = await scraper.fetch_all()

    print("\n" + "=" * 50)
    print("Download Summary")
    print("=" * 50)
    for library, count in results.items():
        print(f"{library}: {count} files")
    print(f"Total: {sum(results.values())} files")


if __name__ == "__main__":
    asyncio.run(main())
