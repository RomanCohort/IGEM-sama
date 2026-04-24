"""Document loading and chunking utilities for the knowledge base.

This module is the primary interface for ingesting team documents into
the RAG pipeline.  Supported formats: .md, .txt, .json.

Usage:
    from knowledge_base.loader import ingest_document, ingest_directory

    entries = ingest_document("wiki/project_overview.md", category="project")
    entries = ingest_directory("knowledge_base/docs/", category="general")
"""

import json
import re
from pathlib import Path
from typing import List

from loguru import logger

from knowledge_base.models import KnowledgeBaseEntry


def chunk_text(text: str, max_chars: int = 500, overlap: int = 50) -> List[str]:
    """Split *text* into overlapping chunks of at most *max_chars* characters.

    Prefers splitting at paragraph or sentence boundaries when possible.
    """
    if not text.strip():
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chars, text_len)

        # If we haven't reached the end, try to break at a paragraph or sentence.
        if end < text_len:
            # Prefer paragraph break
            para_break = text.rfind("\n\n", start, end)
            if para_break != -1 and para_break > start:
                end = para_break
            else:
                # Fall back to sentence break (。！？.!? followed by space or newline)
                sentence_break = -1
                for m in re.finditer(r'[。！？.!?\n]', text[start:end]):
                    sentence_break = start + m.end()
                if sentence_break > start:
                    end = sentence_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward, applying overlap
        start = end - overlap if end < text_len else end
        if start <= end - max_chars:  # prevent infinite loop
            start = end

    return chunks


def load_markdown(path: str | Path) -> str:
    """Read a Markdown file and return its text content."""
    return Path(path).read_text(encoding="utf-8")


def load_text(path: str | Path) -> str:
    """Read a plain-text file and return its content."""
    return Path(path).read_text(encoding="utf-8")


def load_json(path: str | Path) -> str:
    """Load a JSON file and concatenate all string values into one text."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    parts: List[str] = []

    def _extract(obj):
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _extract(v)
        elif isinstance(obj, list):
            for item in obj:
                _extract(item)

    _extract(data)
    return "\n".join(parts)


def ingest_document(
    path: str | Path,
    category: str = "general",
    source: str | None = None,
    max_chars: int = 500,
    overlap: int = 50,
    start_id: int = 0,
) -> List[KnowledgeBaseEntry]:
    """Load a single document, chunk it, and return KB entries.

    Args:
        path: File path (.md, .txt, or .json).
        category: Category tag for all chunks.
        source: Override source name (defaults to file name).
        max_chars: Max characters per chunk.
        overlap: Overlap between chunks.
        start_id: Starting ID for the entries (incremented per chunk).

    Returns:
        List of KnowledgeBaseEntry objects ready for insertion.
    """
    path = Path(path)
    if source is None:
        source = path.name

    suffix = path.suffix.lower()
    if suffix == ".md":
        text = load_markdown(path)
    elif suffix == ".json":
        text = load_json(path)
    elif suffix == ".txt":
        text = load_text(path)
    else:
        logger.warning(f"Unsupported file format: {suffix}, treating as plain text.")
        text = load_text(path)

    chunks = chunk_text(text, max_chars=max_chars, overlap=overlap)
    entries: List[KnowledgeBaseEntry] = []

    for i, chunk in enumerate(chunks):
        entries.append(KnowledgeBaseEntry(
            id=start_id + i,
            text=chunk,
            source=source,
            category=category,
        ))

    logger.info(f"Loaded {path.name}: {len(chunks)} chunks (category={category})")
    return entries


def ingest_directory(
    directory: str | Path,
    category: str = "general",
    max_chars: int = 500,
    overlap: int = 50,
) -> List[KnowledgeBaseEntry]:
    """Recursively load all supported documents from *directory*.

    Returns:
        Combined list of KnowledgeBaseEntry objects from all files.
    """
    directory = Path(directory)
    if not directory.is_dir():
        logger.warning(f"Directory not found: {directory}")
        return []

    all_entries: List[KnowledgeBaseEntry] = []
    supported = {".md", ".txt", ".json"}
    current_id = 0

    for file in sorted(directory.rglob("*")):
        if file.suffix.lower() in supported:
            entries = ingest_document(
                file, category=category, max_chars=max_chars, overlap=overlap,
                start_id=current_id,
            )
            all_entries.extend(entries)
            current_id += len(entries)

    logger.info(f"Total entries from {directory}: {len(all_entries)}")
    return all_entries
