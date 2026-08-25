import json
import re
from src.llm_client import ask_llm
from src.retriever import retrieve

SYSTEM_PROMPT = """You are a tutor creating targeted practice questions.

Rules:
- Base every question ONLY on the textbook excerpts provided.
- Generate questions that specifically target the student's weak topic.
- Vary difficulty: start easier, build up.
- For each question, provide a clear worked solution.
- Format as a numbered list: Question, then Solution, for each item.
- Keep solutions complete but efficient — thorough enough to teach the step,
  without padding. Finish every question and solution you start.
"""

EVALUATE_PROMPT = """You are an encouraging and fair academic evaluator for school students.
You will receive:
1. Grounded textbook context
2. A practice question
3. The student's submitted answer

Your task:
- Evaluate whether the student's answer is conceptually correct, partially correct, or incorrect.
- Give a constructive, friendly explanation highlighting what they got right and where their misconception is.
- Provide the textbook-grounded ideal solution.
- Output valid JSON in the exact format:
{
  "is_correct": true/false,
  "score": 0 to 100,
  "feedback": "constructive feedback in the requested language",
  "key_misconception": "brief description of misconception or 'None'",
  "model_answer": "correct model answer grounded in the textbook"
}
"""

def _get_lang_prompt(language: str) -> str:
    if language == "Hindi":
        return "\nGenerate all content in Hindi (हिन्दी).\n"
    elif language == "Hinglish":
        return "\nGenerate all content in natural Hinglish (conversational Hindi in Roman script mixed with English).\n"
    return ""


def generate_practice(
    topic: str,
    num_questions: int = 3,
    language: str = "English",
    board=None,
    grade=None,
    subject=None,
):
    """
    Returns a dict: {questions_text, sources}
    """
    chunks = retrieve(topic, board=board, grade=grade, subject=subject)
    context = "\n\n---\n\n".join(
        f"[Source: {c['chapter']}, page {c['page']}]\n{c['text']}" for c in chunks
    ) or "No relevant textbook content found."

    sys_prompt = SYSTEM_PROMPT + _get_lang_prompt(language)

    user_prompt = f"""Textbook excerpts on the topic "{topic}":

{context}

Generate {num_questions} practice questions (with worked solutions) that
specifically help a student who is struggling with "{topic}".
"""

    max_tokens = 700 * num_questions
    questions_text = ask_llm(sys_prompt, user_prompt, max_tokens=max_tokens)
    sources = [{"chapter": c["chapter"], "page": c["page"]} for c in chunks]

    return {
        "questions_text": questions_text,
        "sources": sources,
    }


def evaluate_student_answer(
    question: str,
    student_answer: str,
    topic: str,
    language: str = "English",
    board=None,
    grade=None,
    subject=None,
):
    """
    Evaluates a student's answer against the textbook knowledge base.
    Returns: dict { is_correct: bool, score: int, feedback: str, key_misconception: str, model_answer: str }
    """
    chunks = retrieve(topic, board=board, grade=grade, subject=subject)
    context = "\n\n---\n\n".join(
        f"[Source: {c['chapter']}, page {c['page']}]\n{c['text']}" for c in chunks
    ) or "No relevant textbook content found."

    sys_prompt = EVALUATE_PROMPT + _get_lang_prompt(language)
    user_prompt = f"""Textbook context:
{context}

Practice Question:
{question}

Student's Answer:
{student_answer}

Evaluate the student's answer and return strictly JSON.
"""

    raw_response = ask_llm(sys_prompt, user_prompt, max_tokens=1000)

    # Try parsing JSON safely
    try:
        json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return {
                "is_correct": bool(data.get("is_correct", False)),
                "score": int(data.get("score", 0)),
                "feedback": data.get("feedback", raw_response),
                "key_misconception": data.get("key_misconception", "None"),
                "model_answer": data.get("model_answer", ""),
            }
    except Exception:
        pass

    return {
        "is_correct": "correct" in raw_response.lower() and "incorrect" not in raw_response.lower(),
        "score": 75 if "correct" in raw_response.lower() else 30,
        "feedback": raw_response,
        "key_misconception": "Concept gap identified",
        "model_answer": "",
    }


def generate_remedial_worksheet(topics: list, board=None, grade=None, subject=None, language: str = "English"):
    """
    Generates a printable remedial worksheet for a teacher based on the class's top struggle topics.
    """
    topic_str = ", ".join(topics)
    chunks = retrieve(topic_str, board=board, grade=grade, subject=subject, top_k=6)
    context = "\n\n---\n\n".join(
        f"[Source: {c['chapter']}, page {c['page']}]\n{c['text']}" for c in chunks
    )

    sys_prompt = f"""You are a master pedagogical curriculum designer.
Create a structured Remedial Classroom Worksheet for a teacher addressing the most common concept gaps: {topic_str}.
Include:
1. Core Concept Breakdown (simplified explanations for confused students)
2. Common Pitfalls / Misconceptions to address in class
3. 3 Guided Classroom Practice Problems with step-by-step solutions
{_get_lang_prompt(language)}
"""

    user_prompt = f"Textbook Context:\n{context}\n\nGenerate the complete Remedial Worksheet."
    return ask_llm(sys_prompt, user_prompt, max_tokens=2000)

