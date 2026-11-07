import asyncio 
from functools import lru_cache

from langchain_core.documents import Document 
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore, RetrievalMode

from qdrant_client import QdrantClient, models

from app.core.config import get_settings 
from app.core.models import embeddings as make_embeddings 

DENSE, SPARSE = "dense", "sparse"
COLLECTION_PREFIX = "docs_"
INDEXED_FIELDS = ('language','product','page_path')

def create_collection(
    client: QdrantClient,
    name: str, 
    dim: int
) -> None:
    """A collection with one dense and one sparse (BM25) vector per chunk."""
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
                models.FieldCondition(
                    key="metadata.page_path",
                    match=models.MatchValue(value=page_path)
                )
            ]
        )