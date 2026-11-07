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
from app.rag.mdx import load_page, Page, page_url
from app.rag.store import (
    COLLECTION_PREFIX,
    active_collection, 
    build_clients,
    create_collection,
    
)