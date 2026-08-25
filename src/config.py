"""
Single place for every tunable. Change subject/model/chunking here —
nothing else in the codebase should hardcode these values.
"""

import os
from pathlib import Path

# --- Paths -------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_PDF_DIR = ROOT_DIR / "data" / "raw_pdfs"
UNSORTED_PDF_DIR = ROOT_DIR / "data" / "unsorted_pdfs"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
CHROMA_DIR = PROCESSED_DIR / "chroma_db"
LOGS_DIR = ROOT_DIR / "logs"
INTERACTIONS_LOG = LOGS_DIR / "interactions.jsonl"
CLASSIFICATION_LOG = LOGS_DIR / "classification_log.jsonl"

# --- Collection identity --------------------------------------
# ONE Chroma collection holds every board/grade/subject. Retrieval narrows
# down using metadata filters (board, grade, subject) rather than separate
# collections per subject — this scales to many boards/subjects without
# needing a new collection (and new code) for each one.
COLLECTION_NAME = "textbook_all"

# --- Chunking -------------------------------------------------------------
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 60

# --- Retrieval -------------------------------------------------------------
TOP_K = 4  # how many chunks to retrieve per query

# --- Embedding model ---------------------------------------------------
# Local sentence-transformers model -> no extra API cost/latency for embeddings.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- LLM ---------------------------------------------------------------
LLM_MODEL = "gemini-2.5-flash"  # fast + cheap, good for a hackathon demo loop
LLM_MAX_TOKENS = 1200

# --- Gap detection ---------------------------------------------------------
# A topic becomes a "flagged gap" once a student hits this many doubts/re-asks on it.
GAP_THRESHOLD = 2

# --- PDF auto-classification ---------------------------------------------
# How many pages of a PDF to extract and send to the LLM for classification.
# First 1-2 pages is usually enough (front matter or first chapter opener
# reliably signals subject/level); more pages = slower and costlier for
# no real accuracy gain in practice.
CLASSIFY_PAGES_TO_SAMPLE = 2

# Classifications below this confidence go to a "needs review" folder
# instead of being auto-filed, so a bad guess doesn't silently mistag
# a chunk's board/grade/subject metadata.
CLASSIFY_CONFIDENCE_THRESHOLD = 0.6

# --- API key ---------------------------------------------------------------
# Set this in your environment: export GEMINI_API_KEY=...
# (Get a free key at https://aistudio.google.com/apikey)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")