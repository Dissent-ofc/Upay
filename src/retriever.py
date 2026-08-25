"""
Thin wrapper around Chroma so the rest of the app never touches the vector
store directly. If you swap vector DBs later, this is the only file that changes.

Supports filtering by board/grade/subject so retrieval stays precise even
as the knowledge base grows to cover many boards and subjects at once.
"""

import chromadb
from sentence_transformers import SentenceTransformer

from src import config

try:
    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _get_cached_client():
        return chromadb.PersistentClient(path=str(config.CHROMA_DIR))

    @st.cache_resource(show_spinner=False)
    def _get_cached_embedder():
        return SentenceTransformer(config.EMBEDDING_MODEL)

except Exception:
    _raw_client = None
    _raw_embedder = None

    def _get_cached_client():
        global _raw_client
        if _raw_client is None:
            _raw_client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        return _raw_client

    def _get_cached_embedder():
        global _raw_embedder
        if _raw_embedder is None:
            _raw_embedder = SentenceTransformer(config.EMBEDDING_MODEL)
        return _raw_embedder


def _get_embedder():
    return _get_cached_embedder()


def _get_collection():
    client = _get_cached_client()
    return client.get_or_create_collection(name=config.COLLECTION_NAME)




def _build_where_filter(board=None, grade=None, subject=None):
    """
    Build a Chroma `where` filter from whichever of board/grade/subject are
    given. Chroma requires the $and wrapper once there's more than one
    condition; a single condition is passed as-is.
    """
    conditions = []
    if board:
        conditions.append({"board": board})
    if grade:
        conditions.append({"grade": grade})
    if subject:
        conditions.append({"subject": subject})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def retrieve(query: str, top_k: int = None, k: int = None, board=None, grade=None, subject=None):
    """
    Return a list of dicts: [{text, board, grade, subject, chapter, page,
    source_file, distance}, ...] sorted by relevance (closest first).
    """
    top_k = k or top_k or config.TOP_K
    embedder = _get_embedder()
    collection = _get_collection()

    if collection.count() == 0:
        return []

    query_embedding = embedder.encode([query]).tolist()
    where_filter = _build_where_filter(board, grade, subject)

    query_kwargs = {
        "query_embeddings": query_embedding,
        "n_results": min(top_k, collection.count()),
    }
    if where_filter:
        query_kwargs["where"] = where_filter

    results = collection.query(**query_kwargs)

    hits = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        hits.append(
            {
                "text": doc,
                "board": meta.get("board", "unknown"),
                "grade": meta.get("grade", "unknown"),
                "subject": meta.get("subject", "unknown"),
                "chapter": meta.get("chapter", "unknown"),
                "page": meta.get("page", "?"),
                "source_file": meta.get("source_file", "unknown"),
                "distance": dist,
            }
        )
    return hits


def list_indexed_sources(board=None, grade=None, subject=None):
    """
    Returns a summary of what's in the knowledge base, optionally narrowed
    by board/grade/subject:
    [{board, grade, subject, chapter, source_file, chunk_count,
      page_min, page_max}, ...]
    sorted by board, then grade, then subject, then chapter.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    where_filter = _build_where_filter(board, grade, subject)
    get_kwargs = {"include": ["metadatas"]}
    if where_filter:
        get_kwargs["where"] = where_filter

    all_items = collection.get(**get_kwargs)
    metadatas = all_items.get("metadatas", [])

    by_key = {}
    for meta in metadatas:
        b = meta.get("board", "unknown")
        g = meta.get("grade", "unknown")
        s = meta.get("subject", "unknown")
        chapter = meta.get("chapter", "unknown")
        page = meta.get("page")
        source_file = meta.get("source_file", "unknown")

        key = (b, g, s, chapter)
        if key not in by_key:
            by_key[key] = {
                "board": b,
                "grade": g,
                "subject": s,
                "chapter": chapter,
                "source_file": source_file,
                "chunk_count": 0,
                "page_min": page,
                "page_max": page,
            }

        entry = by_key[key]
        entry["chunk_count"] += 1
        if isinstance(page, int):
            if entry["page_min"] is None or page < entry["page_min"]:
                entry["page_min"] = page
            if entry["page_max"] is None or page > entry["page_max"]:
                entry["page_max"] = page

    sources = sorted(
        by_key.values(), key=lambda s: (s["board"], s["grade"], s["subject"], s["chapter"])
    )
    return sources


def list_available_filters():
    """
    Returns the distinct boards, grades, and subjects currently indexed:
    {"boards": [...], "grades": [...], "subjects": [...]}
    Used to populate the UI dropdowns so students only ever pick
    combinations that actually exist in the knowledge base.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return {"boards": [], "grades": [], "subjects": []}

    all_items = collection.get(include=["metadatas"])
    metadatas = all_items.get("metadatas", [])

    boards = sorted({m.get("board", "unknown") for m in metadatas})
    grades = sorted({m.get("grade", "unknown") for m in metadatas})
    subjects = sorted({m.get("subject", "unknown") for m in metadatas})

    return {"boards": boards, "grades": grades, "subjects": subjects}
