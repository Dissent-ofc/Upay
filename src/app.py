"""
Upay — Grounded AI Tutor & Pedagogical Intelligence Platform
Complete multilingual localized UI, adaptive practice evaluation, and teacher diagnostic dashboard.
"""

import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import config
from src.doubt_agent import answer_doubt
from src.gap_tracker import (
    compute_gaps_for_student,
    compute_teacher_dashboard,
    flag_question,
    get_flagged_questions,
    get_student_practice_history,
    log_interaction,
    log_practice_attempt,
    mark_topic_resolved,
    unflag_question,
)
from src.ingest import ingest_single_pdf
from src.practice_gen import evaluate_student_answer, generate_practice, generate_remedial_worksheet
from src.retriever import list_available_filters

# --- Page Setup ---
st.set_page_config(
    page_title="Upay | Grounded AI Tutor",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Internationalization (i18n) Dictionary ---
I18N = {
    "English": {
        "brand_name": "UPAY",
        "brand_tagline": "AI for Equitable Education Access",
        "student_portal": "Student Learning Portal",
        "teacher_portal": "Teacher Diagnostic Hub",
        "settings_header": "Language & Pedagogy",
        "lang_label": "Interface & Explanation Language",
        "style_label": "Explanation Style",
        "style_standard": "Standard Grounded",
        "style_step": "Step-by-Step Breakdown",
        "style_analogy": "Real-World Analogy",
        "syllabus_header": "Curriculum Scope",
        "board_label": "Board",
        "grade_label": "Grade / Class",
        "subject_label": "Subject",
        "all_option": "All Available",
        "hero_title": "Grounded Doubt Resolution",
        "hero_desc": "Step-by-step explanations anchored directly in verified open textbooks with exact citations.",
        "active_scope": "Active Scope",
        "student_id_label": "Student Name or ID",
        "topic_label": "Topic / Concept (Optional)",
        "topic_placeholder": "e.g. Sublimation, Gravitation, Trigonometry",
        "doubt_box_label": "Enter your doubt or question:",
        "doubt_box_placeholder": "Ask any concept or problem from your textbook...",
        "btn_resolve": "Resolve Doubt",
        "btn_simpler": "Explain Simpler (With Analogies)",
        "explanation_header": "Grounded Explanation",
        "sources_header": "VERIFIED TEXTBOOK CITATIONS",
        "btn_flag": "Flag for Revision",
        "btn_flagged_success": "Question flagged for your revision list.",
        "btn_generate_practice": "Generate Practice Problems",
        "practice_header": "Interactive Adaptive Practice",
        "submit_answer_label": "Submit your solution for AI evaluation:",
        "submit_answer_placeholder": "Write your detailed step-by-step answer or calculation here...",
        "btn_evaluate": "Evaluate My Answer",
        "eval_mastery": "Mastery Achieved! Concept understood.",
        "eval_progress": "Good Progress! Review the feedback below.",
        "eval_needs_work": "Needs Work. Review the key misconception and model answer.",
        "feedback_label": "Detailed Feedback",
        "misconception_label": "Identified Misconception",
        "model_sol_label": "View Grounded Model Solution",
        "tab_flagged": "Flagged Revision List",
        "tab_gaps": "Auto-Detected Concept Gaps",
        "no_flagged": "No flagged questions yet. Flag doubts to review them later.",
        "no_gaps": "No concept gaps detected. Keep learning and testing your understanding.",
        "btn_unflag": "Mark Resolved & Remove",
        "btn_mastered": "Mark as Mastered",
        "times_asked": "queries logged",
        "teacher_title": "Educator & Teacher Hub",
        "teacher_desc": "Class-wide learning diagnostics, risk hierarchy, and automated remedial worksheets.",
        "tab_diagnostics": "Student Struggle Diagnostics",
        "tab_remedial": "Remedial Worksheets",
        "tab_ingest": "Curriculum Ingestion",
        "metric_students": "Active Students",
        "metric_doubts": "Doubts Resolved",
        "metric_gaps": "Active Concept Gaps",
        "metric_quizzes": "Practice Quizzes Completed",
        "risk_critical": "[Critical Intervention Required]",
        "risk_moderate": "[Needs Guidance]",
        "risk_ontrack": "[On Track]",
        "struggling_with": "Identified Concept Struggles:",
        "no_student_gaps": "Student is performing well with no active gaps.",
        "last_active": "Last Active",
        "remedial_title": "Generate Targeted Remedial Worksheets",
        "remedial_desc": "Synthesize custom classroom worksheets addressing the exact topics your students are struggling with.",
        "remedial_select_label": "Select concepts to include:",
        "btn_generate_worksheet": "Generate Remedial Worksheet",
        "btn_download_worksheet": "Download Worksheet (Markdown)",
        "ingest_title": "On-Demand Curriculum Ingestion",
        "ingest_desc": "Upload textbook PDFs for any board or class. Chunks and embeddings are indexed into ChromaDB in real-time.",
        "upload_label": "Select Textbook PDF",
        "btn_ingest": "Index and Ingest PDF",
        "ingest_success": "Successfully indexed {count} sections into {board}/{grade}/{subject}.",
    },
    "Hindi": {
        "brand_name": "उपाय",
        "brand_tagline": "समान और सुलभ शिक्षा के लिए एआई",
        "student_portal": "विद्यार्थी अध्ययन पोर्टल",
        "teacher_portal": "अध्यापक डैशबोर्ड",
        "settings_header": "भाषा एवं शिक्षण शैली",
        "lang_label": "इंटरफ़ेस और स्पष्टीकरण भाषा",
        "style_label": "समझाने की शैली",
        "style_standard": "प्रामाणिक पाठ्यपुस्तक शैली",
        "style_step": "चरण-दर-चरण (Step-by-Step)",
        "style_analogy": "सरल व्यावहारिक उदाहरण",
        "syllabus_header": "पाठ्यक्रम चयन",
        "board_label": "शिक्षा बोर्ड",
        "grade_label": "कक्षा",
        "subject_label": "विषय",
        "all_option": "सभी उपलब्ध",
        "hero_title": "संदेह निवारण एवं मार्गदर्शन",
        "hero_desc": "पाठ्यपुस्तकों पर आधारित सटीक, चरण-दर-चरण समाधान एवं संदर्भ सहित उत्तर।",
        "active_scope": "चयनित पाठ्यक्रम",
        "student_id_label": "विद्यार्थी का नाम / अनुक्रमांक",
        "topic_label": "विषय / अध्याय (वैकल्पिक)",
        "topic_placeholder": "उदा. ऊर्ध्वपातन (Sublimation), गुरुत्वाकर्षण",
        "doubt_box_label": "अपना संदेह या प्रश्न यहाँ लिखें:",
        "doubt_box_placeholder": "अपनी पाठ्यपुस्तक से संबंधित कोई भी प्रश्न या समस्या पूछें...",
        "btn_resolve": "संदेह का समाधान करें",
        "btn_simpler": "और सरल भाषा में समझाइए",
        "explanation_header": "पाठ्यपुस्तक आधारित समाधान",
        "sources_header": "प्रमाणित पाठ्यपुस्तक संदर्भ",
        "btn_flag": "पुनरावृत्ति सूची में जोड़ें",
        "btn_flagged_success": "प्रश्न पुनरावृत्ति सूची में सुरक्षित कर लिया गया है।",
        "btn_generate_practice": "अभ्यास प्रश्न तैयार करें",
        "practice_header": "अनुकूली अभ्यास एवं मूल्यांकन",
        "submit_answer_label": "मूल्यांकन के लिए अपना उत्तर लिखें:",
        "submit_answer_placeholder": "यहाँ अपना विस्तृत उत्तर या हल लिखें...",
        "btn_evaluate": "मेरे उत्तर की जांच करें",
        "eval_mastery": "उत्कृष्ट! आपने यह अवधारणा पूरी तरह समझ ली है।",
        "eval_progress": "अच्छा प्रयास! नीचे दिए गए सुझाव पढ़ें।",
        "eval_needs_work": "अधिक अभ्यास की आवश्यकता है। सही उत्तर और व्याख्या देखें।",
        "feedback_label": "मूल्यांकन एवं प्रतिक्रिया",
        "misconception_label": "पहचानी गई वैचारिक त्रुटि",
        "model_sol_label": "आदर्श पाठ्यपुस्तक समाधान देखें",
        "tab_flagged": "पुनरावृत्ति हेतु चिन्हित प्रश्न",
        "tab_gaps": "स्वतः चिन्हित कमजोर विषय",
        "no_flagged": "पुनरावृत्ति सूची में कोई प्रश्न नहीं है।",
        "no_gaps": "कोई कमजोर विषय चिन्हित नहीं है। अपना अध्ययन जारी रखें।",
        "btn_unflag": "समाधान हुआ / हटाएं",
        "btn_mastered": "अवधारणा स्पष्ट हुई",
        "times_asked": "बार पूछा गया",
        "teacher_title": "अध्यापक एवं शिक्षक केंद्र",
        "teacher_desc": "कक्षा-स्तरीय प्रगति विश्लेषण, कमजोर विषयों की पहचान और उपचारात्मक शिक्षण कार्यपत्रक।",
        "tab_diagnostics": "विद्यार्थी प्रगति एवं कमियां",
        "tab_remedial": "उपचारात्मक कार्यपत्रक (Remedial Worksheet)",
        "tab_ingest": "नया पाठ्यक्रम जोड़ें",
        "metric_students": "सक्रिय विद्यार्थी",
        "metric_doubts": "हल किए गए संदेह",
        "metric_gaps": "सक्रिय कमजोर विषय",
        "metric_quizzes": "पूर्ण किए गए अभ्यास",
        "risk_critical": "[विशेष ध्यान देने योग्य]",
        "risk_moderate": "[मार्गदर्शन आवश्यक]",
        "risk_ontrack": "[संतोषजनक प्रगति]",
        "struggling_with": "कमजोर अवधारणाएं:",
        "no_student_gaps": "विद्यार्थी की प्रगति उत्कृष्ट है।",
        "last_active": "अंतिम सक्रियता",
        "remedial_title": "उपचारात्मक कार्यपत्रक बनाएं",
        "remedial_desc": "विद्यार्थियों के कमजोर विषयों के आधार पर उपचारात्मक कक्षा कार्यपत्रक तैयार करें।",
        "remedial_select_label": "कार्यपत्रक के लिए विषय चुनें:",
        "btn_generate_worksheet": "कार्यपत्रक तैयार करें",
        "btn_download_worksheet": "कार्यपत्रक डाउनलोड करें (Markdown)",
        "ingest_title": "नया पाठ्यपुस्तक PDF जोड़ें",
        "ingest_desc": "किसी भी बोर्ड या कक्षा की पाठ्यपुस्तक अपलोड करें। प्रणाली इसे स्वतः अनुक्रमित कर लेगी।",
        "upload_label": "पाठ्यपुस्तक PDF चुनें",
        "btn_ingest": "PDF अनुक्रमित करें",
        "ingest_success": "{count} खंड सफलतापूर्वक {board}/{grade}/{subject} में जोड़े गए।",
    },
    "Hinglish": {
        "brand_name": "UPAY",
        "brand_tagline": "AI for Equitable Education Access",
        "student_portal": "Student Learning Portal",
        "teacher_portal": "Teacher Diagnostic Hub",
        "settings_header": "Language & Style",
        "lang_label": "Explanation Language",
        "style_label": "Explanation Style",
        "style_standard": "Standard Grounded",
        "style_step": "Step-by-Step Breakdown",
        "style_analogy": "Real-World Analogy",
        "syllabus_header": "Curriculum Scope",
        "board_label": "Board",
        "grade_label": "Class / Grade",
        "subject_label": "Subject",
        "all_option": "All Available",
        "hero_title": "Grounded Doubt Clearing",
        "hero_desc": "Textbook verified step-by-step explanations with exact citations. No guesswork.",
        "active_scope": "Active Scope",
        "student_id_label": "Student Name / ID",
        "topic_label": "Topic / Chapter (Optional)",
        "topic_placeholder": "e.g. Sublimation, Gravitation, Electricity",
        "doubt_box_label": "Apna doubt yahan likhein:",
        "doubt_box_placeholder": "Apne textbook ka koi bhi question ya concept puchiye...",
        "btn_resolve": "Doubt Clear Karein",
        "btn_simpler": "Aur Simple Language Mein Samjhaiye",
        "explanation_header": "Textbook Verified Solution",
        "sources_header": "VERIFIED TEXTBOOK CITATIONS",
        "btn_flag": "Revision List Mein Add Karein",
        "btn_flagged_success": "Question revision list mein save ho gaya.",
        "btn_generate_practice": "Practice Questions Banayein",
        "practice_header": "Interactive Adaptive Practice",
        "submit_answer_label": "Evaluation ke liye apna answer likhein:",
        "submit_answer_placeholder": "Apna step-by-step calculation ya explanation likhein...",
        "btn_evaluate": "Mera Answer Check Karein",
        "eval_mastery": "Bahut Badhiya! Concept acche se clear ho gaya.",
        "eval_progress": "Good Attempt! Neeche diye feedback ko check karein.",
        "eval_needs_work": "Thoda aur practice chahiye. Model solution check karein.",
        "feedback_label": "Detailed Feedback",
        "misconception_label": "Identified Misconception",
        "model_sol_label": "Model Solution Dekhein",
        "tab_flagged": "Flagged Revision List",
        "tab_gaps": "Weak Concepts Tracker",
        "no_flagged": "Abhi koi flagged questions nahi hain.",
        "no_gaps": "Koi weak concept detect nahi hua. Practice continue rakhein.",
        "btn_unflag": "Clear Ho Gaya / Remove",
        "btn_mastered": "Samajh Aa Gaya",
        "times_asked": "baar pucha gaya",
        "teacher_title": "Teacher & Educator Hub",
        "teacher_desc": "Class analytics, weak topic diagnostics aur 1-click remedial worksheets.",
        "tab_diagnostics": "Student Progress Diagnostics",
        "tab_remedial": "Remedial Worksheets",
        "tab_ingest": "Curriculum Ingestion",
        "metric_students": "Active Students",
        "metric_doubts": "Doubts Resolved",
        "metric_gaps": "Active Concept Gaps",
        "metric_quizzes": "Practice Quizzes Done",
        "risk_critical": "[Critical Attention Needed]",
        "risk_moderate": "[Needs Guidance]",
        "risk_ontrack": "[On Track]",
        "struggling_with": "Struggling with concepts:",
        "no_student_gaps": "Student ki progress acchi hai.",
        "last_active": "Last Active",
        "remedial_title": "Classroom Remedial Worksheet Generator",
        "remedial_desc": "Class ke weak topics ke basis par tailored remedial worksheet create karein.",
        "remedial_select_label": "Topics select karein:",
        "btn_generate_worksheet": "Remedial Worksheet Generate Karein",
        "btn_download_worksheet": "Worksheet Download Karein (Markdown)",
        "ingest_title": "New Curriculum PDF Ingest Karein",
        "ingest_desc": "Kisi bhi board ya class ka textbook PDF upload karein.",
        "upload_label": "Textbook PDF Select Karein",
        "btn_ingest": "Ingest & Index PDF",
        "ingest_success": "Successfully {count} sections index ho gaye {board}/{grade}/{subject} mein.",
    },
}

# --- Minimalist, Professional Design System ---
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-main: #0B0F17;
    --card-surface: #111827;
    --border-color: #1F2937;
    --accent-indigo: #6366F1;
    --accent-blue: #38BDF8;
    --text-primary: #F3F4F6;
    --text-secondary: #9CA3AF;
}

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: var(--text-primary);
}

/* Hero Header */
.saas-header {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 24px;
    border-top: 3px solid #6366F1;
}

.saas-title {
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #FFFFFF;
    margin: 0;
}

.saas-subtitle {
    font-size: 0.95rem;
    color: #9CA3AF;
    margin-top: 6px;
    line-height: 1.5;
}

.saas-badge {
    display: inline-block;
    background: #1F2937;
    border: 1px solid #374151;
    color: #A5B4FC;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}

/* Citations Callout */
.citations-wrapper {
    background: #0D131F;
    border: 1px solid #1E293B;
    border-left: 3px solid #38BDF8;
    border-radius: 6px;
    padding: 14px 18px;
    margin-top: 16px;
}

.citation-chip {
    display: inline-block;
    background: #1E293B;
    border: 1px solid #334155;
    color: #E2E8F0;
    padding: 3px 9px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-family: 'JetBrains Mono', monospace;
    margin-right: 6px;
    margin-top: 4px;
}

/* Metric Cards */
.saas-metric {
    background: #111827;
    border: 1px solid #1F2937;
    border-radius: 10px;
    padding: 18px 20px;
    text-align: left;
}

.saas-metric-val {
    font-size: 2rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.02em;
}

.saas-metric-label {
    font-size: 0.82rem;
    color: #9CA3AF;
    font-weight: 500;
    margin-top: 2px;
}

/* Clean Button Styling */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.9rem;
    padding: 8px 18px;
    transition: all 0.15s ease-in-out;
}

.stButton > button[kind="primary"] {
    background: #6366F1;
    border: 1px solid #4F46E5;
    color: #FFFFFF;
}

.stButton > button[kind="primary"]:hover {
    background: #4F46E5;
    border-color: #4338CA;
}

/* Inputs & Textareas */
.stTextArea textarea, .stTextInput input, .stSelectbox [data-baseweb="select"] {
    border-radius: 8px !important;
    border-color: #1F2937 !important;
}

/* Sidebar Styling */
.sidebar-header-box {
    padding: 10px 0 16px 0;
    border-bottom: 1px solid #1F2937;
    margin-bottom: 16px;
}

.sidebar-title {
    font-size: 1.3rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.01em;
}

.sidebar-sub {
    font-size: 0.78rem;
    color: #6B7280;
    margin-top: 2px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_citations_ui(sources, t):
    if not sources:
        return
    chips = ""
    for s in sources:
        chips += f"<span class='citation-chip'>{s.get('board','?')} {s.get('grade','?')} · {s['chapter']} (p.{s['page']})</span>"

    st.markdown(
        f"""
        <div class="citations-wrapper">
            <div style="font-size: 0.75rem; font-weight: 700; color: #38BDF8; letter-spacing: 0.05em; margin-bottom: 6px;">
                {t['sources_header']}
            </div>
            <div>{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_board_grade_subject_picker(t):
    filters = list_available_filters()
    all_opt = t["all_option"]

    if not filters["boards"]:
        st.sidebar.warning("No curriculum content indexed yet. Use the Curriculum Ingestion tab to add textbooks.")
        return None, None, None

    col_b, col_g = st.sidebar.columns(2)
    board_choice = col_b.selectbox(t["board_label"], [all_opt] + filters["boards"], index=0)
    grade_choice = col_g.selectbox(t["grade_label"], [all_opt] + filters["grades"], index=0)
    subject_choice = st.sidebar.selectbox(t["subject_label"], [all_opt] + filters["subjects"], index=0)

    board = None if board_choice == all_opt else board_choice
    grade = None if grade_choice == all_opt else grade_choice
    subject = None if subject_choice == all_opt else subject_choice
    return board, grade, subject


def student_view(board, grade, subject, lang_key: str, style_choice: str, t: dict):
    # Header Banner
    scope_display = " · ".join(x for x in [board, grade, subject] if x) or t["all_option"]

    st.markdown(
        f"""
        <div class="saas-header">
            <div class="saas-title">{t['hero_title']}</div>
            <div class="saas-subtitle">{t['hero_desc']}</div>
            <div style="margin-top: 14px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                <span class="saas-badge">{t['active_scope']}: {scope_display}</span>
                <span class="saas-badge">{lang_key}</span>
                <span class="saas-badge">{style_choice}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_id, col_topic = st.columns([1, 1])
    student_id = col_id.text_input(t["student_id_label"], value="demo_student")
    topic_tag = col_topic.text_input(t["topic_label"], value="", placeholder=t["topic_placeholder"])

    st.markdown(f"##### {t['doubt_box_label']}")
    question = st.text_area(
        "Question Input",
        height=110,
        placeholder=t["doubt_box_placeholder"],
        label_visibility="collapsed",
    )

    col_btn1, col_btn2 = st.columns([1, 1])
    ask_clicked = col_btn1.button(t["btn_resolve"], type="primary", use_container_width=True)
    confused_clicked = col_btn2.button(t["btn_simpler"], use_container_width=True)

    if "last_question" not in st.session_state:
        st.session_state.last_question = None

    if ask_clicked and question.strip():
        st.session_state.last_question = question
        with st.spinner("Searching verified open textbooks & formulating grounded answer..."):
            result = answer_doubt(
                question,
                simpler=False,
                language=lang_key,
                style=style_choice,
                board=board,
                grade=grade,
                subject=subject,
            )
        st.session_state.last_result = result
        log_interaction(
            student_id=student_id,
            topic=topic_tag or question[:40],
            question=question,
            needed_simpler=False,
        )

    if confused_clicked and st.session_state.last_question:
        with st.spinner("Re-explaining using intuitive analogies and shorter steps..."):
            result = answer_doubt(
                st.session_state.last_question,
                simpler=True,
                language=lang_key,
                style="Real-World Analogy",
                board=board,
                grade=grade,
                subject=subject,
            )
        st.session_state.last_result = result
        log_interaction(
            student_id=student_id,
            topic=topic_tag or st.session_state.last_question[:40],
            question=st.session_state.last_question,
            needed_simpler=True,
        )

    if st.session_state.get("last_result"):
        result = st.session_state.last_result
        st.markdown(f"#### {t['explanation_header']}")
        st.markdown(result["answer"])
        render_citations_ui(result["sources"], t)

        st.markdown("<br>", unsafe_allow_html=True)
        c_flag, c_prac = st.columns([1, 2])
        if c_flag.button(t["btn_flag"], key="flag_btn"):
            flag_question(
                student_id=student_id,
                topic=topic_tag or st.session_state.last_question[:40],
                question=st.session_state.last_question,
                answer=result["answer"],
            )
            st.success(t["btn_flagged_success"])

        if c_prac.button(t["btn_generate_practice"], key="gen_prac_btn"):
            with st.spinner("Generating targeted practice questions..."):
                active_topic = topic_tag or st.session_state.last_question[:40]
                practice_data = generate_practice(
                    active_topic,
                    num_questions=2,
                    language=lang_key,
                    board=board,
                    grade=grade,
                    subject=subject,
                )
                st.session_state[f"active_practice_{active_topic}"] = practice_data
                st.rerun()

    # Active Interactive Practice Area
    active_keys = [k for k in st.session_state.keys() if k.startswith("active_practice_")]
    if active_keys:
        st.markdown("---")
        st.markdown(f"### {t['practice_header']}")
        for key in active_keys:
            topic = key.replace("active_practice_", "")
            practice = st.session_state[key]
            with st.container():
                st.markdown(f"##### Topic: **{topic}**")
                st.markdown(practice["questions_text"])
                render_citations_ui(practice["sources"], t)

                st.markdown(f"**{t['submit_answer_label']}**")
                student_sub_answer = st.text_area(
                    f"Answer input for {topic}",
                    key=f"ans_input_{topic}",
                    placeholder=t["submit_answer_placeholder"],
                    label_visibility="collapsed",
                )

                if st.button(t["btn_evaluate"], key=f"eval_btn_{topic}", type="primary"):
                    if not student_sub_answer.strip():
                        st.warning("Please write your answer before submitting.")
                    else:
                        with st.spinner("Evaluating response against textbook principles..."):
                            eval_res = evaluate_student_answer(
                                question=practice["questions_text"],
                                student_answer=student_sub_answer,
                                topic=topic,
                                language=lang_key,
                                board=board,
                                grade=grade,
                                subject=subject,
                            )

                            log_practice_attempt(
                                student_id=student_id,
                                topic=topic,
                                question=practice["questions_text"][:80],
                                student_answer=student_sub_answer,
                                score=eval_res["score"],
                                is_correct=eval_res["is_correct"],
                                feedback=eval_res["feedback"],
                            )

                            score = eval_res["score"]
                            if score >= 80:
                                st.success(f"{t['eval_mastery']} (Score: {score}/100)")
                            elif score >= 50:
                                st.info(f"{t['eval_progress']} (Score: {score}/100)")
                            else:
                                st.warning(f"{t['eval_needs_work']} (Score: {score}/100)")

                            st.markdown(f"**{t['feedback_label']}:** {eval_res['feedback']}")
                            if eval_res.get("key_misconception") and eval_res["key_misconception"] != "None":
                                st.markdown(f"**{t['misconception_label']}:** `{eval_res['key_misconception']}`")
                            if eval_res.get("model_answer"):
                                with st.expander(t["model_sol_label"]):
                                    st.markdown(eval_res["model_answer"])

    st.markdown("---")

    # Tabs for Revision and Gaps
    tab_flagged, tab_gaps = st.tabs([t["tab_flagged"], t["tab_gaps"]])

    with tab_flagged:
        flagged = get_flagged_questions(student_id)
        if not flagged:
            st.info(t["no_flagged"])
        else:
            for item in flagged:
                with st.expander(f"[{item['topic']}] {item['question']}"):
                    st.markdown(f"**Question:** {item['question']}")
                    st.markdown(f"**Answer:** {item['answer']}")
                    col_a, col_b = st.columns(2)
                    if col_a.button(t["btn_generate_practice"], key=f"flag_prac_{item['question_id']}"):
                        st.session_state[f"active_practice_{item['topic']}"] = generate_practice(
                            item["topic"], num_questions=2, language=lang_key, board=board, grade=grade, subject=subject
                        )
                        st.rerun()
                    if col_b.button(t["btn_unflag"], key=f"unflag_{item['question_id']}"):
                        unflag_question(student_id, item["question_id"])
                        st.rerun()

    with tab_gaps:
        gaps = compute_gaps_for_student(student_id)
        if not gaps:
            st.info(t["no_gaps"])
        else:
            for gap in gaps:
                score_str = f" · Avg Score: {gap['avg_practice_score']:.0f}%" if gap.get("avg_practice_score") else ""
                with st.expander(f"[{gap['topic']}] ({gap['count']} {t['times_asked']}{score_str})"):
                    col_a, col_b = st.columns(2)
                    if col_a.button(f"{t['btn_generate_practice']}: {gap['topic']}", key=f"gap_prac_{gap['topic']}"):
                        st.session_state[f"active_practice_{gap['topic']}"] = generate_practice(
                            gap["topic"], num_questions=2, language=lang_key, board=board, grade=grade, subject=subject
                        )
                        st.rerun()
                    if col_b.button(f"{t['btn_mastered']}: {gap['topic']}", key=f"resolve_{gap['topic']}"):
                        mark_topic_resolved(student_id, gap["topic"])
                        st.rerun()


def teacher_view(board, grade, subject, lang_key: str, t: dict):
    st.markdown(
        f"""
        <div class="saas-header">
            <div class="saas-title">{t['teacher_title']}</div>
            <div class="saas-subtitle">{t['teacher_desc']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_diag, tab_rem, tab_ing = st.tabs([t["tab_diagnostics"], t["tab_remedial"], t["tab_ingest"]])
    dashboard = compute_teacher_dashboard()

    with tab_diag:
        if not dashboard:
            st.info("No student activity recorded yet.")
        else:
            total_students = len(dashboard)
            total_gaps = sum(len(d["flagged_topics"]) for d in dashboard)
            total_doubts = sum(d["total_questions"] for d in dashboard)
            total_quizzes = sum(d.get("total_practice_attempts", 0) for d in dashboard)

            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f"<div class='saas-metric'><div class='saas-metric-val'>{total_students}</div><div class='saas-metric-label'>{t['metric_students']}</div></div>", unsafe_allow_html=True)
            m2.markdown(f"<div class='saas-metric'><div class='saas-metric-val'>{total_doubts}</div><div class='saas-metric-label'>{t['metric_doubts']}</div></div>", unsafe_allow_html=True)
            m3.markdown(f"<div class='saas-metric'><div class='saas-metric-val' style='color:#F87171;'>{total_gaps}</div><div class='saas-metric-label'>{t['metric_gaps']}</div></div>", unsafe_allow_html=True)
            m4.markdown(f"<div class='saas-metric'><div class='saas-metric-val' style='color:#34D399;'>{total_quizzes}</div><div class='saas-metric-label'>{t['metric_quizzes']}</div></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            for row in dashboard:
                flag_count = len(row["flagged_topics"])
                risk_tag = t["risk_critical"] if flag_count >= 2 else (t["risk_moderate"] if flag_count == 1 else t["risk_ontrack"])
                with st.expander(f"{risk_tag} {row['student_id']} — {flag_count} struggle topic(s), {row['total_questions']} doubts logged"):
                    if row["flagged_topics"]:
                        st.markdown(f"**{t['struggling_with']}**")
                        for tp in row["flagged_topics"]:
                            st.markdown(f"- `{tp}`")
                    else:
                        st.markdown(t["no_student_gaps"])
                    st.caption(f"{t['last_active']}: {row['last_active']}")

    with tab_rem:
        st.markdown(f"#### {t['remedial_title']}")
        st.markdown(t["remedial_desc"])

        all_struggles = []
        for d in dashboard:
            all_struggles.extend(d["flagged_topics"])
        unique_struggles = list(set(all_struggles)) or ["Chemical Reactions", "Gravitation", "Trigonometry", "Electricity"]

        selected_topics = st.multiselect(
            t["remedial_select_label"],
            options=unique_struggles,
            default=unique_struggles[:2] if unique_struggles else None,
        )

        if st.button(t["btn_generate_worksheet"], type="primary"):
            if not selected_topics:
                st.warning("Please select at least one concept.")
            else:
                with st.spinner("Generating pedagogical remedial worksheet from textbook excerpts..."):
                    worksheet_text = generate_remedial_worksheet(
                        topics=selected_topics,
                        board=board,
                        grade=grade,
                        subject=subject,
                        language=lang_key,
                    )
                    st.markdown("#### Generated Remedial Worksheet")
                    st.markdown(worksheet_text)
                    st.download_button(
                        label=t["btn_download_worksheet"],
                        data=worksheet_text,
                        file_name=f"Remedial_Worksheet_{'_'.join(selected_topics)}.md",
                        mime="text/markdown",
                    )

    with tab_ing:
        st.markdown(f"#### {t['ingest_title']}")
        st.markdown(t["ingest_desc"])

        col_b, col_g, col_s = st.columns(3)
        up_board = col_b.text_input(t["board_label"], value="CBSE", placeholder="e.g. CBSE, ICSE, Maharashtra")
        up_grade = col_g.text_input(t["grade_label"], value="Class10", placeholder="e.g. Class9, Class10, Class11")
        up_subject = col_s.text_input(t["subject_label"], value="Science", placeholder="e.g. Science, Math, Physics")

        uploaded_file = st.file_uploader(t["upload_label"], type=["pdf"])

        if uploaded_file is not None:
            if st.button(t["btn_ingest"], type="primary"):
                with st.spinner("Extracting text, chunking, and embedding into ChromaDB..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp_path = Path(tmp.name)

                    dest_dir = config.RAW_PDF_DIR / up_board / up_grade / up_subject
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    clean_filename = uploaded_file.name.replace(" ", "_")
                    dest_path = dest_dir / clean_filename
                    dest_path.write_bytes(tmp_path.read_bytes())

                    chunks_indexed = ingest_single_pdf(
                        dest_path, board=up_board, grade=up_grade, subject=up_subject
                    )
                    success_msg = t["ingest_success"].format(
                        count=chunks_indexed, board=up_board, grade=up_grade, subject=up_subject
                    )
                    st.success(success_msg)
                    st.rerun()


def main():
    # Sidebar Language Selection FIRST so whole UI translates immediately
    language_choice = st.sidebar.selectbox(
        "Interface Language / भाषा",
        ["English", "Hindi (हिन्दी)", "Hinglish"],
        index=0,
    )
    lang_key = "Hindi" if "Hindi" in language_choice and "Hinglish" not in language_choice else ("Hinglish" if "Hinglish" in language_choice else "English")
    t = I18N[lang_key]

    # Sidebar Header with Clean Branding
    st.sidebar.markdown(
        f"""
        <div class="sidebar-header-box">
            <div class="sidebar-title">{t['brand_name']}</div>
            <div class="sidebar-sub">{t['brand_tagline']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    view_options = [t["student_portal"], t["teacher_portal"]]
    view = st.sidebar.radio("Navigation", view_options, index=0)
    st.sidebar.markdown("---")

    st.sidebar.markdown(f"**{t['settings_header']}**")
    style_options = [t["style_standard"], t["style_step"], t["style_analogy"]]
    style_choice = st.sidebar.selectbox(t["style_label"], style_options, index=0)
    style_clean = "Step-by-Step" if style_choice == t["style_step"] else ("Real-World Analogy" if style_choice == t["style_analogy"] else "Standard")

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{t['syllabus_header']}**")
    board, grade, subject = render_board_grade_subject_picker(t)

    if view == t["student_portal"]:
        student_view(board, grade, subject, lang_key=lang_key, style_choice=style_clean, t=t)
    else:
        teacher_view(board, grade, subject, lang_key=lang_key, t=t)


if __name__ == "__main__":
    main()
