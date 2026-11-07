---
paths:
  - "app/rag/**/*.py"
---

# RAG rules

- Search through the Qdrant alias (`QDRANT_ALIAS`), never a concrete `docs_*` collection. Only `promote()` repoints it.
- Changing chunk size/overlap (2000/200), the embedding model, or vector dims means a full re-index into a new `docs_*` collection.
- Chunk metadata keys `language`, `product`, `page_path` are payload-indexed (`metadata.<key>`). Add new filterable keys to `INDEXED_FIELDS` in `store.py`.
- Use `embeddings(cache=True)` during ingestion so unchanged text is not re-embedded.
