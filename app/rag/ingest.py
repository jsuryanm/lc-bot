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


