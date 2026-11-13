import argparse
import logging
import subprocess
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.documents import Document 
from langchain_core.embeddings import Embeddings 
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.core.logging import logger,setup_logging
from app.rag.mdx import load_page, Page, page_url
from app.rag.store import (
    COLLECTION_PREFIX,
    active_collection, 
    build_clients,
    create_collection,
    hybrid_store,
    list_versions,
    promote
)

setup_logging()

ROOTS = ("oss", "langsmith")  # folders under src/ that hold documentation pages
SKIP_FOLDERS = {"deepagents", "contributing", "openwiki", "images"}  # out of scope for v1
KEEP_VERSIONS = 3  # newest collections kept for rollback
BATCH = 128


HEADERS = MarkdownHeaderTextSplitter(
    [("#", "h1"), ("##", "h2"), ("###", "h3")], strip_headers=False
)

SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def find_pages(repo: Path) -> list[Path]:
    """Finds and returns all MDX files under the specified source directories, excluding skipped folders."""
    src = repo / "src"
    found = (
        p for root in ROOTS
        for p in (src/root).rglob("*.mdx")
    )
    return sorted(p 
                  for p in found 
                  if not SKIP_FOLDERS & set(p.relative_to(src).parts))

def repo_info(repo: Path) -> tuple[str, str]:
    """(commit sha, license name). The license is read from the repo, not assumed."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sha = "unknown"
    license_file = repo / "LICENSE"
    first_line = license_file.read_text().splitlines()[0].strip() if license_file.exists() else ""
    if first_line != "MIT License":
        logger.warning(
            "LICENSE is %r, not 'MIT License'. Check it before using this index.", first_line
        )
    return sha, "MIT" if first_line == "MIT License" else "unknown"

def to_documents(
    page: Page,
    languages: set[str],
    commit: str,
    license_name: str
) -> list[Document]:
    """Chunk one page. Chunks keep their heading path so a hit is easy to cite."""
    docs: list[Document] = []
    retrieved_at = datetime.now(UTC).isoformat(timespec='seconds')

    for segment_language, text in page.segments:
        language = (
            segment_language if segment_language != "all"

        )

