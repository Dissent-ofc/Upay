"""
Logs every student interaction to an append-only JSONL file (stand-in for a
real DB in the hackathon demo), and computes two kinds of signals from it:

1. Manually flagged questions — the student explicitly clicks "Flag this
   question" on an answer. This is the primary, demo-visible mechanism.
2. Auto-detected topic gaps — a topic is flagged automatically once the
   student has asked about it (or needed a simpler re-explanation)
   GAP_THRESHOLD or more times. Kept as a secondary signal alongside manual
   flagging, not a replacement for it.

Upgrade path: replace the naive "topic = question text" bucketing with an
LLM-classified topic tag per question if time allows — the log schema
already supports adding a `topic` field without breaking anything.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone

from src import config


def _ensure_log_file():
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not config.INTERACTIONS_LOG.exists():
        config.INTERACTIONS_LOG.touch()


def log_interaction(student_id: str, topic: str, question: str, needed_simpler: bool):
    """Append one interaction record (a doubt asked or re-asked)."""
    _ensure_log_file()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_id": student_id,
        "topic": topic,
        "question": question,
        "needed_simpler": needed_simpler,
        "event": "doubt",
    }
    with open(config.INTERACTIONS_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def flag_question(student_id: str, topic: str, question: str, answer: str):
    """
    Explicitly flag a specific question (with its full text and the answer
    the student got) for later review/practice. This is a manual, on-demand
    action — distinct from the automatic topic-gap detection below.
    """
    _ensure_log_file()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_id": student_id,
        "topic": topic,
        "question": question,
        "answer": answer,
        "event": "flagged",
    }
    with open(config.INTERACTIONS_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def unflag_question(student_id: str, question_id: str):
    """
    Mark a previously flagged question as no longer flagged. question_id is
    the flagged record's own timestamp, used as a stable identifier since
    these records don't have a separate ID field.
    """
    _ensure_log_file()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_id": student_id,
        "question_id": question_id,
        "event": "unflagged",
    }
    with open(config.INTERACTIONS_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def mark_topic_resolved(student_id: str, topic: str):
    """
    Append a 'resolved' marker for this student+topic. compute_gaps_for_student
    will exclude the topic from the flagged list as long as no new doubt on
    that topic has been logged after this marker — keeps the full history in
    the log (useful for the teacher view) instead of deleting past records.
    """
    _ensure_log_file()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_id": student_id,
        "topic": topic,
        "event": "resolved",
    }
    with open(config.INTERACTIONS_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_all_interactions():
    _ensure_log_file()
    records = []
    with open(config.INTERACTIONS_LOG, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_flagged_questions(student_id: str):
    """
    Returns the student's currently flagged questions with full text:
    [{question_id, topic, question, answer, flagged_at}, ...]
    sorted most-recently-flagged first. A question stops appearing once
    it's been unflagged (via unflag_question) after its flag event.
    """
    records = [r for r in load_all_interactions() if r["student_id"] == student_id]

    flagged_events = [r for r in records if r.get("event") == "flagged"]
    unflagged_ids = {
        r["question_id"] for r in records if r.get("event") == "unflagged"
    }

    flagged = [
        {
            "question_id": r["timestamp"],  # timestamp doubles as a stable ID
            "topic": r["topic"],
            "question": r["question"],
            "answer": r.get("answer", ""),
            "flagged_at": r["timestamp"],
        }
        for r in flagged_events
        if r["timestamp"] not in unflagged_ids
    ]

    flagged.sort(key=lambda f: f["flagged_at"], reverse=True)
    return flagged


def log_practice_attempt(
    student_id: str,
    topic: str,
    question: str,
    student_answer: str,
    score: int,
    is_correct: bool,
    feedback: str,
):
    """
    Append an evaluation record for an interactive practice attempt.
    """
    _ensure_log_file()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_id": student_id,
        "topic": topic,
        "question": question,
        "student_answer": student_answer,
        "score": score,
        "is_correct": is_correct,
        "feedback": feedback,
        "event": "practice_attempt",
    }
    with open(config.INTERACTIONS_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")

    # If the student achieves high mastery (>= 80%), auto-resolve the gap
    if score >= 80 and topic:
        mark_topic_resolved(student_id, topic)


def get_student_practice_history(student_id: str):
    """
    Returns list of practice attempts for this student.
    """
    records = [r for r in load_all_interactions() if r["student_id"] == student_id]
    attempts = [r for r in records if r.get("event") == "practice_attempt"]
    attempts.sort(key=lambda r: r["timestamp"], reverse=True)
    return attempts


def compute_gaps_for_student(student_id: str):
    """
    Returns list of dicts: [{topic, count, needed_simpler_count, avg_practice_score}, ...]
    for topics that meet or exceed GAP_THRESHOLD, sorted by count desc.
    """
    records = [r for r in load_all_interactions() if r["student_id"] == student_id]
    records.sort(key=lambda r: r["timestamp"])

    last_resolved_time = {}
    topic_counts = defaultdict(lambda: {"count": 0, "needed_simpler_count": 0, "practice_scores": []})

    for r in records:
        topic = r.get("topic")
        event = r.get("event", "doubt")
        if event == "resolved":
            last_resolved_time[topic] = r["timestamp"]
            topic_counts[topic] = {"count": 0, "needed_simpler_count": 0, "practice_scores": []}
        elif event == "doubt":
            topic_counts[topic]["count"] += 1
            if r.get("needed_simpler"):
                topic_counts[topic]["needed_simpler_count"] += 1
        elif event == "practice_attempt":
            topic_counts[topic]["practice_scores"].append(r.get("score", 0))

    gaps = []
    for topic, stats in topic_counts.items():
        if not topic:
            continue
        if stats["count"] >= config.GAP_THRESHOLD or stats["needed_simpler_count"] >= 1 or (stats["practice_scores"] and sum(stats["practice_scores"])/len(stats["practice_scores"]) < 60):
            avg_score = (sum(stats["practice_scores"]) / len(stats["practice_scores"])) if stats["practice_scores"] else None
            gaps.append({
                "topic": topic,
                "count": stats["count"],
                "needed_simpler_count": stats["needed_simpler_count"],
                "avg_practice_score": avg_score
            })

    gaps.sort(key=lambda g: g["count"], reverse=True)
    return gaps


def compute_teacher_dashboard():
    """
    Returns list of dicts, one per student, for the teacher-facing view:
    [{student_id, total_questions, flagged_topics, total_practice_attempts, last_active}, ...]
    """
    records = load_all_interactions()
    by_student = defaultdict(list)
    for r in records:
        by_student[r["student_id"]].append(r)

    dashboard = []
    for student_id, recs in by_student.items():
        gaps = compute_gaps_for_student(student_id)
        doubt_recs = [r for r in recs if r.get("event", "doubt") == "doubt"]
        practice_recs = [r for r in recs if r.get("event") == "practice_attempt"]
        last_active = max(r["timestamp"] for r in recs) if recs else None
        dashboard.append(
            {
                "student_id": student_id,
                "total_questions": len(doubt_recs),
                "total_practice_attempts": len(practice_recs),
                "flagged_topics": [g["topic"] for g in gaps],
                "last_active": last_active,
            }
        )

    # Students with more flagged topics surface first
    dashboard.sort(key=lambda d: len(d["flagged_topics"]), reverse=True)
    return dashboard

