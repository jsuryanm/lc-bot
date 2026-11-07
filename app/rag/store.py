import asyncio 
from functools import lru_cache

from langchain_core.documents import Document 
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore, RetrievalMode

from qdrant_client import QdrantClient, models

from app.core.config import get_settings
from app.core.logging import logger, setup_logging
from app.core.models import embeddings as make_embeddings

setup_logging()

DENSE, SPARSE = "dense", "sparse"
COLLECTION_PREFIX = "docs_"
INDEXED_FIELDS = ('language','product','page_path')

settings = get_settings()

def create_collection(
    client: QdrantClient,
    name: str, 
    dim: int
) -> None:
    """A collection with one dense and one sparse (BM25) vector per chunk."""
    logger.info("Creating collection {} (dim={})", name, dim)
    client.create_collection(
        collection_name=name,
        vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={SPARSE: models.SparseVectorParams()}
    )

    for field in INDEXED_FIELDS:
        # creates metadata for each document/chunk for filtered search
        client.create_payload_index(
            name, 
            f"metadata.{field}",
            models.PayloadSchemaType.KEYWORD
        )

def hybrid_store(
    client: QdrantClient, 
    collection: str, 
    dense: Embeddings, 
    sparse
) -> QdrantVectorStore:
    """Creates a Qdrant vector store configured 
    for hybrid retrieval using dense and sparse embeddings."""
    return QdrantVectorStore(
        client=client, 
        collection_name=collection,
        embedding=dense, 
        sparse_embedding=sparse,
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name=DENSE,
        sparse_vector_name=SPARSE
    )

def promote(
    client: QdrantClient,
    collection: str,
    alias: str
) -> None:
    """Point `alias` at `collection` in one atomic step. Rollback is promote(old_collection)."""
    ops: list = []
    if alias in {a.alias_name for a in client.get_aliases().aliases}: 
        # get_aliases() retrieves all alternative names that point to an existing collection
        ops.append(models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=alias)))
        # creates an operation that deletes an existing alias from Qdrant
    
    ops.append(
        models.CreateAliasOperation(
            create_alias=models.CreateAlias(
                collection_name=collection,
                alias_name=alias
            )
        )
    )
    
    client.update_collection_aliases(change_aliases_operations=ops)
    logger.info("Alias {} now points at {}", alias, collection)

def active_collection(client: QdrantClient, alias: str) -> str | None:
    """Returns the collection name associated with given alias 
    or returns None if alias doesnt exist"""
    for a in client.get_aliases().aliases:
        if a.alias_name == alias:
            return a.collection_name
    return None 

def list_versions(client: QdrantClient) -> list[str]:
    """Returns a sorted list of collection names that match the defined collection prefix."""
    names = [c.name 
             for c in client.get_collections().collections]
    return sorted(n for n in names if n.startswith(COLLECTION_PREFIX))

def _language_filter(language: str) -> models.FieldCondition:
    """Applies payload based metadata filtering based on any language (e.g, python, javascript)"""
    return models.FieldCondition(
        key="metadata.language",
        match=models.MatchAny(
            any=[language, "all"]
        )
    )

class DocsIndex: 
    """what the agents see: search chunks, fetch a whole page"""

    def __init__(
        self,
        client: QdrantClient,
        collection: str, 
        dense: Embeddings,
        sparse
    ):
        self.client = client 
        self.collection = collection 
        self.store = hybrid_store(client, collection, dense, sparse)

    async def search(
        self, 
        query: str,
        * ,
        language: str, 
        product: str = 'any',
        k: int = 6
    ) -> list[Document]:
        """Performs hybrid vector search to retrieve chunks based on 
        query, language and optionally product"""
        must = [_language_filter(language)]
        if product != "any":
            must.append(
                models.FieldCondition(
                    key="metadata.product",
                    match=models.MatchValue(value=product)
                )
            )

        logger.debug("Search q={!r} language={} product={} k={}", query, language, product, k)
        return await asyncio.to_thread(
            self.store.similarity_search,
            query,
            k=k,
            filter=models.Filter(must=must)
        )

    async def page(
            self,
            page_path: str,
            *,
            language: str
    ) -> list[Document]:
        return asyncio.to_thread(self._page, page_path, language)

    def _page(
            self,
            page_path: str,
            language: str
    ) -> list[Document]:
        """Retrieves all chunks belonging to specific doc page 
        and arranges them in original order"""
        filter = models.Filter(
            must=[
                _language_filter(language),
                # builds precise metadata filter
                models.FieldCondition(
                    key="metadata.page_path",
                    match=models.MatchValue(value=page_path)
                )
            ]
        )

        points, _ = self.client.scroll(
            self.collection,
            scroll_filter=filter,
            limit=500,
            with_payload=True,
            with_vectors=False
        )

        docs = [
            Document(page_content=p.payload["page_content"],
                     metadata=p.payload["metadata"])
            for p in points
        ]

        return sorted(docs, key=lambda d: d.metadata["chunk_index"])

def build_clients(
        settings,
        *,
        cache_embeddings: bool = False,
) -> tuple[QdrantClient, Embeddings, object]:
    """Initializes and returns the Qdrant client, dense embedding model, and sparse embedding model."""
    from langchain_qdrant import FastEmbedSparse
    return (
        QdrantClient(url=settings.qdrant_url),
        make_embeddings(settings, cache=cache_embeddings),
        FastEmbedSparse(model_name="Qdrant/bm25")
    )

@lru_cache
def get_docs_index() -> DocsIndex:
    """The live index: the collection the alias currently points at."""
    settings = get_settings()
    logger.info("Opening docs index via alias {}", settings.qdrant_alias)
    client, dense, sparse = build_clients(settings)
    return DocsIndex(
        client,
        settings.qdrant_alias,
        dense,
        sparse
    )

def format_page(chunks: list[Document], limit: int = 12_000) -> str:
    """A whole page, rebuilt from its chunks. Overlap between chunks is left in, which is harmless."""
    if not chunks:
        return "Page not found. Use a page_path from a search result."
    text = "\n\n".join(c.page_content for c in chunks)
    return text if len(text) <= limit else text[:limit] + "\n\n[page truncated]"


def format_chunks(docs: list[Document]) -> str:
    """Text shown to a model. Includes the URL so the model can cite it."""
    if not docs:
        return "No matching documentation found."
    blocks = []
    for i, d in enumerate(docs, 1):
        m = d.metadata
        blocks.append(
            f"[{i}] {m['title']} > {m['heading']}\n"
            f"page_path: {m['page_path']}\npage_url: {m['page_url']}\n\n{d.page_content}"
        )
    return "\n\n---\n\n".join(blocks)
