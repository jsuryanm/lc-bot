from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_classic.embeddings import CacheBackedEmbeddings
# stores or temporarily caches the embeddings and stores in key-val store, 
# where text is hashed and hash is used as key in cache  
 
from langchain_classic.storage import LocalFileStore # local key-val store
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.core.config import get_settings 

settings = get_settings()

def chat_model(model: str) -> BaseChatModel:
    return init_chat_model(model=model)

def embeddings(
    settings = settings, 
    *,
    cache: bool = False,
) -> Embeddings:
    """Dense embeddings. With `cache=True`, unchanged text is never embedded twice."""
    embeddings = init_embeddings(
        settings.embeddings_model,
        key_encoder="sha256"
    )

    if not cache: 
        return embeddings

    store = LocalFileStore(settings.embedding_cache_dir)

    return CacheBackedEmbeddings.from_bytes_store(
        embeddings,
        store,
        namespace=settings.embeddings_model,
        key_encoder='sha256'
    )