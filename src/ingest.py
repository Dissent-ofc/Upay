"""
One-time (or re-run-on-new-PDF) pipeline:
    PDFs organized as data/raw_pdfs/<Board>/<Grade>/<Subject>/<chapter>.pdf
        -> extract text per page
        -> clean + chunk with overlap
        -> embed each chunk
        -> upsert into ONE shared Chroma collection, tagged with
           board/grade/subject/chapter/page metadata

Folder convention (this drives the metadata automatically — no manual
tagging needed per file):

    data/raw_pdfs/
    ├── CBSE/
    │   ├── Class10/
    │   │   ├── Science/
    │   │   │   ├── ch06_life_processes.pdf
    │   │   │   └── ch10_light.pdf
    │   │   └── Math/
    │   │       └── ch01_real_numbers.pdf
    │   └── Class9/
    │       └── Science/...
    └── ICSE/
        └── Class10/
            └── Physics/...

The filename (minus extension) becomes the "chapter" label, e.g.
"ch06_life_processes". Rename files to something readable — it shows up
directly in citations and the "available chapters" sidebar panel.

Run directly:  python -m src.ingest
"""

import re
import uuid

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from src import config


def find_pdfs_with_metadata():
    """
    Walk RAW_PDF_DIR expecting the <Board>/<Grade>/<Subject>/*.pdf layout.
    Yields (pdf_path, board, grade, subject) for every PDF found.
    Skips (with a warning) any PDF that isn't exactly 3 folders deep, so a
    misplaced file doesn't silently get wrong or missing metadata.
    """
    for pdf_path in sorted(config.RAW_PDF_DIR.rglob("*.pdf")):
        rel = pdf_path.relative_to(config.RAW_PDF_DIR)
        parts = rel.parts  # e.g. ("CBSE", "Class10", "Science", "ch06_....pdf")

        if len(parts) != 4:
            print(
                f"  Skipping {rel} — expected <Board>/<Grade>/<Subject>/file.pdf "
                f"(found {len(parts) - 1} folder level(s) instead of 3)."
            )
            continue

        board, grade, subject, _filename = parts
        yield pdf_path, board, grade, subject


def extract_pages(pdf_path):
    """Yield (page_number, raw_text) for every page in a PDF."""
    reader = PdfReader(str(pdf_path))
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        yield i + 1, text


def clean_text(text: str) -> str:
    """Light cleanup: collapse whitespace, drop stray page-number artifacts."""
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def chunk_text(text: str, chunk_size: int, overlap: int):
    """
    Naive word-based chunking (good enough for a hackathon demo; swap for a
    tokenizer-aware splitter if answer quality suffers on long chunks).
    """
    words = text.split(" ")
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        start += chunk_size - overlap
    return chunks


def build_index():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    config.RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)

    pdf_entries = list(find_pdfs_with_metadata())
    if not pdf_entries:
        print(
            f"No PDFs found under {config.RAW_PDF_DIR} in the expected "
            f"<Board>/<Grade>/<Subject>/file.pdf layout. Add some and re-run."
        )
        return

    print(f"Loading embedding model: {config.EMBEDDING_MODEL} ...")
    embedder = SentenceTransformer(config.EMBEDDING_MODEL)

    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    collection = client.get_or_create_collection(name=config.COLLECTION_NAME)

    total_chunks = 0

    for pdf_path, board, grade, subject in pdf_entries:
        chapter_name = pdf_path.stem  # filename (no extension) -> chapter label
        print(f"\nProcessing {board}/{grade}/{subject}/{pdf_path.name} ...")

        ids, docs, metadatas = [], [], []

        for page_num, raw_text in extract_pages(pdf_path):
            cleaned = clean_text(raw_text)
            if not cleaned:
                continue

            chunks = chunk_text(
                cleaned,
                chunk_size=config.CHUNK_SIZE_TOKENS,
                overlap=config.CHUNK_OVERLAP_TOKENS,
            )

            for chunk in chunks:
                if len(chunk.strip()) < 30:
                    continue  # skip near-empty noise chunks
                chunk_id = str(uuid.uuid4())
                ids.append(chunk_id)
                docs.append(chunk)
                metadatas.append(
                    {
                        "board": board,
                        "grade": grade,
                        "subject": subject,
                        "chapter": chapter_name,
                        "page": page_num,
                        "source_file": pdf_path.name,
                    }
                )

        if not docs:
            print(f"  No usable text extracted from {pdf_path.name} (scanned/image PDF?).")
            continue

        print(f"  Embedding {len(docs)} chunks ...")
        embeddings = embedder.encode(docs, show_progress_bar=False).tolist()

        collection.upsert(
            ids=ids,
            documents=docs,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        total_chunks += len(docs)
        print(f"  Indexed {len(docs)} chunks from {pdf_path.name}.")

    print(f"\nDone. Total chunks indexed this run: {total_chunks}")
    print(f"Collection '{config.COLLECTION_NAME}' now has {collection.count()} chunks total.")


def ingest_single_pdf(pdf_path, board: str, grade: str, subject: str) -> int:
    """
    Ingest a single PDF directly into ChromaDB. Useful for on-demand teacher/student uploads.
    Returns the number of chunks indexed.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    embedder = SentenceTransformer(config.EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    collection = client.get_or_create_collection(name=config.COLLECTION_NAME)

    chapter_name = pdf_path.stem
    ids, docs, metadatas = [], [], []

    for page_num, raw_text in extract_pages(pdf_path):
        cleaned = clean_text(raw_text)
        if not cleaned:
            continue
        chunks = chunk_text(
            cleaned,
            chunk_size=config.CHUNK_SIZE_TOKENS,
            overlap=config.CHUNK_OVERLAP_TOKENS,
        )
        for chunk in chunks:
            if len(chunk.strip()) < 30:
                continue
            chunk_id = str(uuid.uuid4())
            ids.append(chunk_id)
            docs.append(chunk)
            metadatas.append(
                {
                    "board": board,
                    "grade": grade,
                    "subject": subject,
                    "chapter": chapter_name,
                    "page": page_num,
                    "source_file": pdf_path.name,
                }
            )

    if not docs:
        return 0

    embeddings = embedder.encode(docs, show_progress_bar=False).tolist()
    collection.upsert(
        ids=ids,
        documents=docs,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    return len(docs)


if __name__ == "__main__":
    build_index()

