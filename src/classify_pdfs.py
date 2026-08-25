"""
Auto-classifies textbook PDFs by board/grade/subject/chapter using the LLM's
own knowledge of curricula, via structured output (JSON schema) — so you can
drop any PDF, named anything, into data/unsorted_pdfs/ and have it filed
into the data/raw_pdfs/<Board>/<Grade>/<Subject>/ structure automatically.

HOW IT WORKS:
    1. Extract the first couple of pages of text from the PDF (front
       matter / chapter opener reliably signals subject, level, and often
       the board).
    2. Send that text to Gemini with a JSON schema forcing a structured
       response: board, grade, subject, chapter_name, confidence.
    3. If confidence is high enough, move the PDF into the right folder.
       If not, leave it in a "needs_review" subfolder instead of silently
       filing it somewhere wrong — a bad guess here corrupts retrieval
       metadata for everyone who later searches that subject/grade.

This does NOT replace human review entirely — it's a triage step. Low-
confidence or ambiguous PDFs (e.g. a workbook with no clear subject
signal) are meant to be reviewed and moved by hand.

Run directly:  python -m src.classify_pdfs
"""

import json
import shutil

from google import genai
from google.genai import types
from pypdf import PdfReader

from src import config

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "board": {
            "type": "string",
            "description": (
                "The education board this textbook belongs to, e.g. 'CBSE', "
                "'ICSE', 'StateBoard_Maharashtra'. Use 'CBSE' for standard "
                "NCERT content unless there's a clear signal otherwise."
            ),
        },
        "grade": {
            "type": "string",
            "description": "e.g. 'Class9', 'Class10', 'Class12'. Use the 'ClassN' format.",
        },
        "subject": {
            "type": "string",
            "description": "e.g. 'Science', 'Math', 'Physics', 'Chemistry', 'Biology', 'SocialScience', 'English'.",
        },
        "chapter_name": {
            "type": "string",
            "description": (
                "A short, filename-safe chapter title, e.g. "
                "'ch06_life_processes'. Use lowercase, underscores, no spaces "
                "or special characters. Include a chapter number if visible."
            ),
        },
        "confidence": {
            "type": "number",
            "description": "0.0 to 1.0 — how confident you are in this classification overall.",
        },
        "reasoning": {
            "type": "string",
            "description": "One short sentence on what signals led to this classification.",
        },
    },
    "required": ["board", "grade", "subject", "chapter_name", "confidence", "reasoning"],
}

SYSTEM_PROMPT = """You are classifying a textbook chapter PDF by board, grade,
subject, and chapter name, based on a text sample from its opening pages.

Use your knowledge of Indian school curricula (CBSE/NCERT, ICSE, state
boards) to infer the classification from subject terminology, difficulty
level, and any visible branding or headers. If the text doesn't give you
enough to be confident, say so honestly with a low confidence score rather
than guessing — a wrong classification is worse than an honest "unsure".
"""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def extract_sample_text(pdf_path, num_pages: int) -> str:
    """Extract text from the first num_pages of a PDF, for classification."""
    reader = PdfReader(str(pdf_path))
    pages_text = []
    for i, page in enumerate(reader.pages[:num_pages]):
        text = page.extract_text() or ""
        if text.strip():
            pages_text.append(text)
    return "\n\n".join(pages_text)


def classify_pdf(pdf_path) -> dict:
    """
    Returns a dict matching CLASSIFICATION_SCHEMA's fields, or a dict with
    confidence=0.0 and an error note if extraction/classification failed.
    """
    sample_text = extract_sample_text(pdf_path, config.CLASSIFY_PAGES_TO_SAMPLE)

    if not sample_text.strip():
        return {
            "board": "unknown",
            "grade": "unknown",
            "subject": "unknown",
            "chapter_name": pdf_path.stem,
            "confidence": 0.0,
            "reasoning": "No extractable text found (likely a scanned/image-only PDF).",
        }

    client = _get_client()
    user_prompt = f"""Filename: {pdf_path.name}

Text sample from the first {config.CLASSIFY_PAGES_TO_SAMPLE} page(s):

{sample_text[:4000]}
"""

    try:
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=CLASSIFICATION_SCHEMA,
                max_output_tokens=1500,
            ),
        )
        result = json.loads(response.text)
        return result
    except Exception as e:
        return {
            "board": "unknown",
            "grade": "unknown",
            "subject": "unknown",
            "chapter_name": pdf_path.stem,
            "confidence": 0.0,
            "reasoning": f"Classification failed: {e}",
        }


def _sanitize_path_component(value: str) -> str:
    """Keep folder/file names filesystem-safe — strip anything that isn't
    alphanumeric, underscore, or hyphen."""
    safe = "".join(c for c in value if c.isalnum() or c in ("_", "-"))
    return safe or "unknown"


def classify_and_sort():
    config.RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    config.UNSORTED_PDF_DIR.mkdir(parents=True, exist_ok=True)
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    needs_review_dir = config.UNSORTED_PDF_DIR / "needs_review"
    needs_review_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(config.UNSORTED_PDF_DIR.glob("*.pdf"))  # top-level only, not needs_review/
    if not pdf_files:
        print(f"No PDFs found directly in {config.UNSORTED_PDF_DIR}. Drop some in and re-run.")
        return

    print(f"Found {len(pdf_files)} PDF(s) to classify.\n")

    filed, needs_review = 0, 0
    log_entries = []

    for pdf_path in pdf_files:
        print(f"Classifying {pdf_path.name} ...")
        result = classify_pdf(pdf_path)
        confidence = result.get("confidence", 0.0)

        print(
            f"  -> board={result.get('board')} grade={result.get('grade')} "
            f"subject={result.get('subject')} chapter={result.get('chapter_name')} "
            f"confidence={confidence:.2f}"
        )
        print(f"  Reasoning: {result.get('reasoning', '')}")

        log_entries.append({"file": pdf_path.name, **result})

        if confidence >= config.CLASSIFY_CONFIDENCE_THRESHOLD:
            board = _sanitize_path_component(result["board"])
            grade = _sanitize_path_component(result["grade"])
            subject = _sanitize_path_component(result["subject"])
            chapter_name = _sanitize_path_component(result["chapter_name"])

            dest_dir = config.RAW_PDF_DIR / board / grade / subject
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{chapter_name}.pdf"

            # Avoid silently overwriting a same-named file already filed there.
            if dest_path.exists():
                dest_path = dest_dir / f"{chapter_name}_{pdf_path.stem}.pdf"

            shutil.move(str(pdf_path), str(dest_path))
            print(f"  Filed -> {dest_path.relative_to(config.ROOT_DIR)}\n")
            filed += 1
        else:
            dest_path = needs_review_dir / pdf_path.name
            shutil.move(str(pdf_path), str(dest_path))
            print(
                f"  Confidence too low ({confidence:.2f} < "
                f"{config.CLASSIFY_CONFIDENCE_THRESHOLD}) — moved to "
                f"needs_review/ for manual sorting.\n"
            )
            needs_review += 1

    # Append this run's results to a persistent classification log for auditing.
    with open(config.CLASSIFICATION_LOG, "a") as f:
        for entry in log_entries:
            f.write(json.dumps(entry) + "\n")

    print(f"Done. Auto-filed: {filed}, Sent to review: {needs_review}")
    if needs_review > 0:
        print(
            f"Check {needs_review_dir.relative_to(config.ROOT_DIR)} and move those "
            f"files into data/raw_pdfs/<Board>/<Grade>/<Subject>/ manually."
        )
    if filed > 0:
        print("Next step: python -m src.ingest")


if __name__ == "__main__":
    classify_and_sort()
