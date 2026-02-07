"""Ingest service for processing documentation into vector database."""

import re
from pathlib import Path

from src.db.chromadb import ChromaDBHandler


class IngestService:
    """Processes raw docs into chunked, embedded documents in ChromaDB."""

    def __init__(self, db_handler: ChromaDBHandler, raw_docs_path: str = "raw/docs"):
        self.db = db_handler
        self.raw_docs_path = Path(raw_docs_path)

    def read_file(self, file_path: Path) -> str:
        """Read a file and return its content as string.

        Handle UTF-8 encoding. Skip binary files gracefully.
        For .mdx files: strip JSX components.
        For .rst files: basic RST-to-text cleanup.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IOError):
            print(f"Skipping binary or unreadable file: {file_path}")
            return ""

        ext = file_path.suffix.lower()

        if ext == ".mdx":
            content = self._clean_mdx(content)
        elif ext == ".rst":
            content = self._clean_rst(content)

        return content

    def _clean_mdx(self, content: str) -> str:
        """Clean MDX content by removing JSX components and imports."""
        # Remove JSX component tags (multiline)
        content = re.sub(r"<[A-Z][a-zA-Z]*[^>]*>.*?</[A-Z][a-zA-Z]*>", "", content, flags=re.DOTALL)
        # Remove self-closing JSX tags
        content = re.sub(r"<[A-Z][a-zA-Z]*[^/]*/>", "", content)
        # Remove import statements
        content = re.sub(r"^import\s+.*?from\s+['\"][^'\"]+['\"];?\s*$", "", content, flags=re.MULTILINE)
        # Remove export statements
        content = re.sub(r"^export\s+.*?;?\s*$", "", content, flags=re.MULTILINE)
        return content

    def _clean_rst(self, content: str) -> str:
        """Clean RST content by converting to markdown-like format."""
        # Remove RST directives (keep content inside)
        content = re.sub(r"\.\.\s+\w+::.*?\n", "", content)
        # Remove role markup :ref:`text` -> text
        content = re.sub(r":\w+:`([^`]+)`", r"\1", content)
        # Convert RST headers (underline style) to markdown
        lines = content.split("\n")
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Check for underline header pattern
            if i + 1 < len(lines) and lines[i + 1] and all(c == lines[i + 1][0] for c in lines[i + 1]):
                level = {"=": "#", "-": "##", "~": "###", "^": "####"}.get(lines[i + 1][0], "#")
                result.append(f"{level} {line}")
                i += 2
            else:
                result.append(line)
                i += 1
        return "\n".join(result)

    def chunk_markdown(
        self, content: str, source_file: str, library: str
    ) -> list[dict]:
        """Split markdown content into chunks based on headers.

        Strategy:
        1. Split by headers (##, ###). Keep # (h1) as the document title.
        2. Each chunk = one section (from one header to the next).
        3. If a section is too long (>4000 chars), split it further
           by paragraphs with overlap of 200 chars.
        4. If a section is too short (<100 chars), merge it with the next section.
        5. Preserve code blocks intact - never split in the middle of a ``` block.
        """
        chunks = []

        # Find document title (first H1) or use filename
        h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        document_title = h1_match.group(1) if h1_match else Path(source_file).stem

        # Split content by headers (##, ###)
        # Pattern: match headers and capture them
        header_pattern = r"^(#{2,3})\s+(.+)$"
        sections = []
        current_section = {"header": "intro", "content": ""}

        lines = content.split("\n")
        in_code_block = False

        for line in lines:
            # Track code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block

            # Check for header (only outside code blocks)
            if not in_code_block:
                match = re.match(header_pattern, line)
                if match:
                    # Save previous section
                    if current_section["content"].strip():
                        sections.append(current_section)
                    # Start new section
                    current_section = {"header": match.group(2), "content": ""}
                    continue

            current_section["content"] += line + "\n"

        # Add last section
        if current_section["content"].strip():
            sections.append(current_section)

        # Process sections into chunks
        chunk_index = 0
        i = 0
        while i < len(sections):
            section = sections[i]
            header = section["header"]
            content_text = section["content"].strip()

            # Skip empty sections
            if not content_text:
                i += 1
                continue

            # Check for code blocks
            has_code = "```" in content_text

            # If section is too long, split by paragraphs
            if len(content_text) > 4000:
                # Split by paragraphs (double newline)
                paragraphs = content_text.split("\n\n")
                current_chunk = ""

                for para in paragraphs:
                    if len(current_chunk) + len(para) > 4000 and current_chunk:
                        # Save current chunk
                        chunks.append(
                            {
                                "text": f"## {header}\n\n{current_chunk}".strip(),
                                "metadata": {
                                    "library": library,
                                    "source_file": source_file,
                                    "section": document_title,
                                    "subsection": header,
                                    "chunk_index": chunk_index,
                                    "char_count": len(current_chunk),
                                    "has_code": "```" in current_chunk,
                                },
                            }
                        )
                        chunk_index += 1
                        # Start new chunk with overlap
                        current_chunk = current_chunk[-200:] + "\n\n" + para
                    else:
                        current_chunk += para + "\n\n"

                # Add remaining content
                if current_chunk.strip():
                    chunks.append(
                        {
                            "text": f"## {header}\n\n{current_chunk}".strip(),
                            "metadata": {
                                "library": library,
                                "source_file": source_file,
                                "section": document_title,
                                "subsection": header,
                                "chunk_index": chunk_index,
                                "char_count": len(current_chunk),
                                "has_code": "```" in current_chunk,
                            },
                        }
                    )
                    chunk_index += 1
            else:
                # Section is a good size
                chunk_text = f"## {header}\n\n{content_text}" if header != "intro" else content_text

                # Check if we should merge with previous small chunk
                if chunks and chunks[-1]["metadata"]["char_count"] < 100:
                    prev_chunk = chunks.pop()
                    chunk_index -= 1
                    chunk_text = prev_chunk["text"] + "\n\n" + chunk_text

                chunks.append(
                    {
                        "text": chunk_text.strip(),
                        "metadata": {
                            "library": library,
                            "source_file": source_file,
                            "section": document_title,
                            "subsection": header if header != "intro" else "introduction",
                            "chunk_index": chunk_index,
                            "char_count": len(chunk_text),
                            "has_code": has_code,
                        },
                    }
                )
                chunk_index += 1

            i += 1

        # Add total_chunks to metadata
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = total_chunks

        return chunks

    def generate_chunk_id(self, library: str, source_file: str, chunk_index: int) -> str:
        """Generate a deterministic ID for a chunk.

        Format: "{library}::{source_file}::chunk_{chunk_index}"
        Example: "langchain::concepts/architecture.md::chunk_0"
        """
        return f"{library}::{source_file}::chunk_{chunk_index}"

    async def ingest_library(self, library: str) -> int:
        """Ingest all docs for a single library.

        1. List all files in raw/docs/{library}/ recursively
        2. For each file:
           a. Read content
           b. Chunk it
           c. Collect all chunks
        3. Batch insert into ChromaDB (batches of 100 chunks)
        4. Return total chunks ingested
        """
        lib_path = self.raw_docs_path / library
        if not lib_path.exists():
            print(f"Library path not found: {lib_path}")
            return 0

        # Find all supported files
        files = []
        for ext in ["*.md", "*.mdx", "*.rst"]:
            files.extend(lib_path.rglob(ext))

        print(f"Ingesting {library}: found {len(files)} files")

        all_chunks = []
        processed_files = 0

        for file_path in files:
            # Calculate relative path from library root
            rel_path = file_path.relative_to(lib_path).as_posix()

            content = self.read_file(file_path)
            if not content:
                continue

            chunks = self.chunk_markdown(content, rel_path, library)
            all_chunks.extend(chunks)
            processed_files += 1

            if processed_files % 10 == 0:
                print(f"  Processed {processed_files}/{len(files)} files...")

        print(f"  Total chunks to insert: {len(all_chunks)}")

        # Batch insert into ChromaDB
        if all_chunks:
            ids = []
            texts = []
            metadatas = []

            for chunk in all_chunks:
                chunk_id = self.generate_chunk_id(
                    library, chunk["metadata"]["source_file"], chunk["metadata"]["chunk_index"]
                )
                ids.append(chunk_id)
                texts.append(chunk["text"])
                metadatas.append(chunk["metadata"])

            # Insert in batches of 100
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                batch_end = min(i + batch_size, len(ids))
                self.db.add_documents_batch(
                    ids=ids[i:batch_end],
                    texts=texts[i:batch_end],
                    metadatas=metadatas[i:batch_end],
                )
                print(f"  Inserted batch {i//batch_size + 1}/{(len(ids) + batch_size - 1)//batch_size}")

        print(f"Ingested {library}: {len(all_chunks)} chunks from {processed_files} files")
        return len(all_chunks)

    async def ingest_all(self) -> dict[str, int]:
        """Ingest docs for all libraries.

        Returns: {"langchain": 500, "fastapi": 300, "python": 100}
        """
        results = {}
        libraries = ["langchain", "fastapi", "python"]

        for library in libraries:
            count = await self.ingest_library(library)
            results[library] = count

        return results

    async def clear_and_reingest(self) -> dict[str, int]:
        """Delete the collection and re-ingest everything from scratch."""
        print("Clearing existing collection...")
        self.db.delete_collection("technical_docs")
        print("Collection cleared. Re-ingesting...")
        return await self.ingest_all()
