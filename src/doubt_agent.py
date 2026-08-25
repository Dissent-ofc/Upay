"""
Core Grounded Doubt-Solving Agent.

Flow:
    student question -> retrieve top-k textbook chunks -> LLM answers
    ONLY from those chunks, with citations -> if student says "still
    confused", re-explain simpler using the same grounded chunks.
"""

from src.llm_client import ask_llm
from src.retriever import retrieve

BASE_SYSTEM_PROMPT = """You are a patient, encouraging tutor for school students.

Rules:
- Answer ONLY using the textbook excerpts provided below. Do not use outside knowledge.
- If the excerpts don't contain enough information to answer, say so honestly
  rather than guessing.
- Explain step by step, in simple language appropriate for a school student.
- At the end, cite which chapter/page the explanation came from.
- Keep the explanation focused and not overly long.
"""

SIMPLER_INSTRUCTION = """
The student said they are STILL CONFUSED by your previous explanation.
Re-explain the same concept using:
- Shorter sentences
- ONE simple real-world analogy (introduce it briefly, don't over-develop it)
- Clear numbered steps
Still ground your answer only in the excerpts provided.
Keep the full explanation complete but concise — finish your thought,
don't trail off, and don't pad with extra examples beyond what's needed.
"""


def _format_context(chunks):
    if not chunks:
        return "No relevant textbook content was found."
    parts = []
    for c in chunks:
        parts.append(
            f"[Source: {c['chapter']}, page {c['page']}]\n{c['text']}"
        )
    return "\n\n---\n\n".join(parts)


def _get_language_instruction(language: str) -> str:
    if language == "Hindi":
        return "\n- Explain entirely in clean, student-friendly Hindi (हिन्दी). Keep technical scientific terms clear, providing their English equivalent in parentheses if helpful.\n"
    elif language == "Hinglish":
        return "\n- Explain in conversational Hinglish (Hindi written in Roman script mixed naturally with English), making it extremely natural and relatable for an Indian student.\n"
    elif language == "Simple English":
        return "\n- Explain in very simple, beginner-friendly English with short sentences and easy vocabulary.\n"
    return "\n- Explain in clear, natural English appropriate for a school student.\n"


def _get_style_instruction(style: str) -> str:
    if style == "Step-by-Step":
        return "\n- Structure your entire answer into clear, numbered step-by-step points.\n"
    elif style == "Real-World Analogy":
        return "\n- Start with a vivid, relatable real-world analogy before breaking down the theoretical concept.\n"
    return ""


def answer_doubt(
    question: str,
    simpler: bool = False,
    language: str = "English",
    style: str = "Standard",
    board=None,
    grade=None,
    subject=None,
):
    """
    Returns a dict: {answer, sources, retrieved_chunks}
    `simpler=True` triggers the re-explanation mode.
    `language`: "English", "Hindi", "Hinglish", "Simple English"
    `style`: "Standard", "Step-by-Step", "Real-World Analogy"
    """
    chunks = retrieve(question, board=board, grade=grade, subject=subject)
    context = _format_context(chunks)

    system_prompt = BASE_SYSTEM_PROMPT
    system_prompt += _get_language_instruction(language)
    system_prompt += _get_style_instruction(style)

    max_tokens = 1200
    if simpler:
        system_prompt += SIMPLER_INSTRUCTION
        max_tokens = 1800

    user_prompt = f"""Textbook excerpts:

{context}

Student's question: {question}
"""

    answer_text = ask_llm(system_prompt, user_prompt, max_tokens=max_tokens)

    sources = [
        {
            "board": c["board"],
            "grade": c["grade"],
            "subject": c["subject"],
            "chapter": c["chapter"],
            "page": c["page"],
        }
        for c in chunks
    ]

    return {
        "answer": answer_text,
        "sources": sources,
        "retrieved_chunks": chunks,
    }

