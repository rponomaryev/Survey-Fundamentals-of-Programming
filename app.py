from flask import Flask, render_template, request, jsonify, session, send_file
import json
import csv
import os
import re
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "srs_survey_secret_2024"   # needed for server-side session

MAX_SCORE: int           = 60
REVERSE_QUESTIONS: tuple = (4, 9)          # 1-based question IDs
QUESTIONS_FILE: str      = "questions.json"
VALID_FORMATS: list      = ["json", "csv", "txt"]
ANSWER_OPTIONS: dict     = {0: "Never", 1: "Rarely", 2: "Sometimes", 3: "Often", 4: "Always"}

#QUESTIONS (fallback)

HARDCODED_QUESTIONS: list = [
    {"id": 1,  "question": "How often do you review study material after your first learning session?",                     "reverse": False},
    {"id": 2,  "question": "How often do you revisit the same material after increasing time intervals (e.g., 1 day, 3 days, 1 week)?", "reverse": False},
    {"id": 3,  "question": "How often do you use spaced repetition techniques (planned review schedule)?",                  "reverse": False},
    {"id": 4,  "question": "How often do you forget information shortly after studying it?",                                "reverse": True},
    {"id": 5,  "question": "How often do you use flashcards for reviewing information?",                                    "reverse": False},
    {"id": 6,  "question": "How often do you test yourself instead of just rereading notes?",                               "reverse": False},
    {"id": 7,  "question": "How often do you schedule your study sessions in advance?",                                     "reverse": False},
    {"id": 8,  "question": "How often do you feel that repeated reviews improve your memory?",                              "reverse": False},
    {"id": 9,  "question": "How often do you rely on cramming instead of spaced learning?",                                 "reverse": True},
    {"id": 10, "question": "How often do you remember information weeks after learning it?",                                "reverse": False},
    {"id": 11, "question": "How often do you use apps for spaced repetition?",                                              "reverse": False},
    {"id": 12, "question": "How often do you review difficult topics more frequently than easy ones?",                      "reverse": False},
    {"id": 13, "question": "How often do you track your learning progress over time?",                                      "reverse": False},
    {"id": 14, "question": "How often do you feel confident recalling information without notes?",                          "reverse": False},
    {"id": 15, "question": "How often do you adjust your review schedule based on your memory performance?",                "reverse": False},
]

# LEVELS + FAMOUS FIGURES

LEVELS: list = [
    {
        "name": "Critical Learning Inefficiency",
        "emoji": "🔴",
        "range": [0, 15],
        "color": "#ef4444",
        "bg_gradient": "linear-gradient(135deg,#fef2f2,#fee2e2)",
        "border": "#fca5a5",
        "interpretation": (
            "Your study habits show very limited use of spaced repetition and memory "
            "consolidation strategies. Information retention is likely poor, and forgetting "
            "occurs rapidly after initial learning. This pattern significantly limits "
            "long-term academic performance."
        ),
        "recommendation": (
            "Start by introducing a simple daily review routine. Use free tools such as "
            "Anki or Quizlet to create flashcard decks. Review material 24 hours, 3 days, "
            "and 1 week after first exposure. Even 10 minutes of daily spaced review can "
            "dramatically improve retention."
        ),
        "figure": {
            "name": "The Fresh Starter",
            "icon": "🌱",
            "description": (
                "Every expert was once a beginner. You are at the starting line - "
                "the most important step is recognising the gap and committing to change."
            ),
            "quotes": [
                "The secret of getting ahead is getting started. - Mark Twain",
                "An investment in knowledge pays the best interest. - Benjamin Franklin",
            ],
        },
    },
    {
        "name": "Basic Learning Strategy",
        "emoji": "🟠",
        "range": [16, 30],
        "color": "#f97316",
        "bg_gradient": "linear-gradient(135deg,#fff7ed,#ffedd5)",
        "border": "#fdba74",
        "interpretation": (
            "You apply some memory-enhancing techniques occasionally, but your practice "
            "is inconsistent. You may rely on passive re-reading more than active recall. "
            "Memory gains are present but are not yet sustainable over longer periods."
        ),
        "recommendation": (
            "Build a consistent weekly study schedule. Replace re-reading sessions with "
            "self-testing (flashcards, practice questions). Try setting phone reminders "
            "for scheduled reviews. Aim to review each topic at least three times with "
            "increasing intervals."
        ),
        "figure": {
            "name": "Richard Feynman",
            "icon": "⚛️",
            "description": (
                "Nobel laureate physicist Richard Feynman was famous for learning through "
                "curiosity and relentless questioning. He believed true understanding came "
                "only from being able to teach a concept simply — a principle at the heart "
                "of active recall."
            ),
            "quotes": [
                "Study hard what interests you the most in the most undisciplined, irreverent and original manner possible. - Feynman",
                "The first principle is that you must not fool yourself - and you are the easiest person to fool. - Feynman",
            ],
        },
    },
    {
        "name": "Developing Spaced Repetition User",
        "emoji": "🟡",
        "range": [31, 45],
        "color": "#eab308",
        "bg_gradient": "linear-gradient(135deg,#fefce8,#fef9c3)",
        "border": "#fde047",
        "interpretation": (
            "You have a reasonable understanding of spaced repetition and actively use "
            "some of its principles. Memory retention is noticeably better than average, "
            "though there is still room to improve consistency and depth of practice."
        ),
        "recommendation": (
            "Refine your review schedule by tracking forgetting patterns. Prioritise "
            "difficult material with more frequent reviews and reduce time on mastered "
            "topics. Explore the Leitner system or algorithm-based SRS apps to optimise "
            "your intervals further."
        ),
        "figure": {
            "name": "Elon Musk",
            "icon": "🚀",
            "description": (
                "Elon Musk is known for teaching himself rocket science and advanced "
                "engineering through iterative, first-principles learning. He repeatedly "
                "revisits and reconstructs knowledge from the ground up - a hallmark of "
                "developing spaced repetition mastery."
            ),
            "quotes": [
                "I think it's very important to have a feedback loop, where you're constantly thinking about what you've done and how you could be doing it better. — Musk",
                "The key to knowledge is understanding the fundamentals, not memorising facts. - Elon Musk",
            ],
        },
    },
    {
        "name": "Advanced Memory Optimization",
        "emoji": "🟢",
        "range": [46, 60],
        "color": "#22c55e",
        "bg_gradient": "linear-gradient(135deg,#f0fdf4,#dcfce7)",
        "border": "#86efac",
        "interpretation": (
            "You consistently apply spaced repetition principles at a high level. Your "
            "long-term memory retention is strong, and you make deliberate, data-driven "
            "decisions about your study schedule. You represent best practices in "
            "self-directed learning and cognitive performance."
        ),
        "recommendation": (
            "Continue your excellent habits. Consider exploring interleaved practice and "
            "elaborative interrogation to add further depth to your learning. You may also "
            "benefit from sharing your strategies with peers or exploring advanced memory "
            "techniques such as the method of loci."
        ),
        "figure": {
            "name": "Albert Einstein",
            "icon": "🧠",
            "description": (
                "Albert Einstein exemplified deep, deliberate thinking and the power of "
                "mental models built through years of focused review and reflection. He "
                "famously revisited the same ideas from multiple angles - a perfect "
                "embodiment of advanced memory optimization."
            ),
            "quotes": [
                "Imagination is more important than knowledge. Knowledge is limited. Imagination encircles the world. - Einstein",
                "If you can't explain it simply, you don't understand it well enough. - Einstein",
            ],
        },
    },
]

# HELPER FUNCTIONS

def load_questions() -> list:
    """Load from questions.json, fallback to hardcoded."""
    if os.path.exists(QUESTIONS_FILE):
        try:
            with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return HARDCODED_QUESTIONS


def reverse_score(s: int) -> int:
    return 4 - s


def calculate_score(questions: list, raw: list) -> tuple:
    """Returns (adjusted_answers, total_score)."""
    adjusted: list = []
    total: int = 0
    for i, q in enumerate(questions):
        adj = reverse_score(raw[i]) if q.get("reverse") else raw[i]
        adjusted.append(adj)
        total += adj
    return adjusted, total


def get_level(score: int) -> dict:
    for lvl in LEVELS:
        lo, hi = lvl["range"]
        if lo <= score <= hi:
            return lvl
    return LEVELS[-1]


def validate_name(name: str) -> tuple:
    name = name.strip()
    if not name:
        return False, "Name cannot be empty."
    bad = [c for c in name if not (c.isalpha() or c in (" ", "-", "'"))]
    if bad:
        return False, f"Invalid characters: {set(bad)}. Only letters, spaces, hyphens, apostrophes."
    if len(name) < 2:
        return False, "Name must be at least 2 characters."
    return True, ""


def validate_dob(dob: str) -> tuple:
    try:
        d = datetime.strptime(dob.strip(), "%d/%m/%Y")
        if d > datetime.today():
            return False, "Date of birth cannot be in the future."
        if d.year < 1900:
            return False, "Date of birth cannot be before 1900."
        return True, ""
    except ValueError:
        return False, "Invalid date. Use DD/MM/YYYY (e.g. 15/03/2000)."


def validate_student_id(sid: str) -> tuple:
    sid = sid.strip()
    if not sid:
        return False, "Student ID cannot be empty."
    if not sid.isdigit():
        return False, "Student ID must contain digits only."
    if not (4 <= len(sid) <= 12):
        return False, "Student ID must be 4–12 digits."
    return True, ""


def analyse_weak_areas(questions: list, adjusted: list) -> list:
    """
    AI-like rule engine: returns list of weak area dicts
    for any question scored 0 or 1 after adjustment.
    """
    weak: list = []
    categories = {
        1:  "Review frequency",
        2:  "Interval spacing",
        3:  "Technique adoption",
        4:  "Forgetting rate",
        5:  "Flashcard usage",
        6:  "Active self-testing",
        7:  "Session scheduling",
        8:  "Belief in repetition",
        9:  "Cramming avoidance",
        10: "Long-term recall",
        11: "App / tool usage",
        12: "Difficulty prioritisation",
        13: "Progress tracking",
        14: "Recall confidence",
        15: "Adaptive scheduling",
    }
    advice = {
        1:  "Try reviewing material within 24 hours of first learning it.",
        2:  "Extend your gaps deliberately: 1 day → 3 days → 1 week → 1 month.",
        3:  "Pick one SRS technique (e.g. Leitner box) and apply it for 2 weeks.",
        4:  "Your forgetting rate is high. Daily micro-reviews of 5–10 cards can help.",
        5:  "Create 5 flashcards per study topic. Even paper cards beat passive reading.",
        6:  "Close your notes and write down everything you remember after studying.",
        7:  "Block out study slots in your calendar at least 3 days ahead.",
        8:  "Track a topic you've reviewed 3 times and notice how recall improves.",
        9:  "Replace last-minute cramming with two 20-minute sessions spaced 2 days apart.",
        10: "Test yourself on material from 2 weeks ago. Surprise yourself with what sticks.",
        11: "Try Anki (free) for 10 minutes a day — it calculates optimal intervals for you.",
        12: "Spend 60% of review time on topics you find hardest.",
        13: "Keep a simple study log: date, topic, score. Review it weekly.",
        14: "Practice retrieval without notes at least once per study session.",
        15: "After each review, rate your recall (1–5). Shorten intervals for low scores.",
    }
    for i, q in enumerate(questions):
        if adjusted[i] <= 1:
            qid = q["id"]
            weak.append({
                "q_num":    qid,
                "category": categories.get(qid, f"Question {qid}"),
                "score":    adjusted[i],
                "advice":   advice.get(qid, "Focus on improving this area."),
            })
    return weak


def build_result(user: dict, questions: list,
                 raw: list, adjusted: list, total: int) -> dict:
    level = get_level(total)
    answers_detail = [
        {
            "question_id":    i + 1,
            "question":       q["question"],
            "reverse":        q.get("reverse", False),
            "raw_answer":     raw[i],
            "raw_label":      ANSWER_OPTIONS[raw[i]],
            "adjusted_score": adjusted[i],
        }
        for i, q in enumerate(questions)
    ]
    return {
        "name":           user["name"],
        "dob":            user["dob"],
        "student_id":     user["student_id"],
        "timestamp":      datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "answers":        answers_detail,
        "total_score":    total,
        "max_score":      MAX_SCORE,
        "level":          level["name"],
        "interpretation": level["interpretation"],
        "recommendation": level["recommendation"],
    }

# EXPORT HELPERS

def to_json_bytes(r: dict) -> bytes:
    return json.dumps(r, ensure_ascii=False, indent=4).encode("utf-8")


def to_csv_bytes(r: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SPACED REPETITION SURVEY RESULTS"])
    w.writerow(["Field", "Value"])
    for k in ("name", "dob", "student_id", "timestamp"):
        w.writerow([k.replace("_", " ").title(), r[k]])
    w.writerow(["Total Score", f"{r['total_score']}/{r['max_score']}"])
    w.writerow(["Level", r["level"]])
    w.writerow(["Interpretation", r["interpretation"]])
    w.writerow(["Recommendation", r["recommendation"]])
    w.writerow([])
    w.writerow(["Q#", "Question", "Reverse", "Raw", "Label", "Adjusted"])
    for a in r["answers"]:
        w.writerow([a["question_id"], a["question"], a["reverse"],
                    a["raw_answer"], a["raw_label"], a["adjusted_score"]])
    return buf.getvalue().encode("utf-8")


def to_txt_bytes(r: dict) -> bytes:
    lines = [
        "SPACED REPETITION SURVEY RESULTS",
        "=" * 54,
        f"Name       : {r['name']}",
        f"DOB        : {r['dob']}",
        f"Student ID : {r['student_id']}",
        f"Timestamp  : {r['timestamp']}",
        "-" * 54,
        "ANSWERS:",
    ]
    for a in r["answers"]:
        rev = " [R]" if a["reverse"] else "    "
        lines.append(f"  Q{a['question_id']:2d}{rev} {a['raw_label']:10s} (adj={a['adjusted_score']})")
    lines += [
        "-" * 54,
        f"Total Score: {r['total_score']}/{r['max_score']}",
        f"Level      : {r['level']}",
        "",
        "Interpretation:",
        r["interpretation"],
        "",
        "Recommendation:",
        r["recommendation"],
    ]
    return "\n".join(lines).encode("utf-8")

# ROUTES

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/survey")
def survey():
    questions = load_questions()
    return render_template("survey.html", questions=questions,
                           answer_options=ANSWER_OPTIONS)


@app.route("/api/validate-user", methods=["POST"])
def api_validate_user():
    """Validate personal details and store in session."""
    data = request.get_json()
    errors: dict = {}

    ok, msg = validate_name(data.get("name", ""))
    if not ok:
        errors["name"] = msg

    ok, msg = validate_dob(data.get("dob", ""))
    if not ok:
        errors["dob"] = msg

    ok, msg = validate_student_id(data.get("student_id", ""))
    if not ok:
        errors["student_id"] = msg

    if errors:
        return jsonify({"ok": False, "errors": errors})

    session["user"] = {
        "name":       data["name"].strip(),
        "dob":        data["dob"].strip(),
        "student_id": data["student_id"].strip(),
    }
    return jsonify({"ok": True})


@app.route("/api/submit", methods=["POST"])
def api_submit():
    """Receive survey answers, calculate score, store result."""
    data = request.get_json()
    raw_answers = data.get("answers", [])     # list of ints [0-4], length 15
    questions   = load_questions()

    # Validate answer count and values
    if len(raw_answers) != len(questions):
        return jsonify({"ok": False, "error": "Incomplete answers."}), 400
    for v in raw_answers:
        if v not in range(5):
            return jsonify({"ok": False, "error": "Invalid answer value."}), 400

    user = session.get("user", {
        "name": data.get("name", "Anonymous"),
        "dob":  data.get("dob", "N/A"),
        "student_id": data.get("student_id", "0000"),
    })

    adjusted, total = calculate_score(questions, raw_answers)
    level           = get_level(total)
    weak_areas      = analyse_weak_areas(questions, adjusted)
    result          = build_result(user, questions, raw_answers, adjusted, total)

    # Build per-question chart data
    chart_data = {
        "labels":   [f"Q{q['id']}" for q in questions],
        "adjusted": adjusted,
        "raw":      raw_answers,
    }

    session["result"] = result

    return jsonify({
        "ok":        True,
        "result":    result,
        "level":     level,
        "weak":      weak_areas,
        "chart":     chart_data,
    })


@app.route("/result")
def result_page():
    result = session.get("result")
    if not result:
        return render_template("index.html")
    level      = get_level(result["total_score"])
    questions  = load_questions()
    adjusted   = [a["adjusted_score"] for a in result["answers"]]
    weak_areas = analyse_weak_areas(questions, adjusted)
    return render_template("result.html",
                           result=result,
                           level=level,
                           weak_areas=weak_areas)

# DOWNLOAD ROUTES

@app.route("/download/<fmt>")
def download(fmt: str):
    result = session.get("result")
    if not result or fmt not in VALID_FORMATS:
        return "No result available.", 404

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    sid  = result.get("student_id", "0000")
    name = f"results_{sid}_{ts}.{fmt}"

    if fmt == "json":
        return send_file(
            io.BytesIO(to_json_bytes(result)),
            mimetype="application/json",
            as_attachment=True,
            download_name=name,
        )
    elif fmt == "csv":
        return send_file(
            io.BytesIO(to_csv_bytes(result)),
            mimetype="text/csv",
            as_attachment=True,
            download_name=name,
        )
    else:
        return send_file(
            io.BytesIO(to_txt_bytes(result)),
            mimetype="text/plain",
            as_attachment=True,
            download_name=name,
        )

# UPLOAD / LOAD ROUTE

@app.route("/api/load-result", methods=["POST"])
def api_load_result():
    """Parse uploaded file and return result dict."""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded."}), 400

    f    = request.files["file"]
    name = f.filename.lower()
    raw  = f.read()

    try:
        if name.endswith(".json"):
            data = json.loads(raw.decode("utf-8"))
            return jsonify({"ok": True, "result": data,
                            "level": get_level(int(data.get("total_score", 0)))})

        elif name.endswith(".csv"):
            text   = raw.decode("utf-8")
            reader = csv.reader(io.StringIO(text))
            rows   = list(reader)
            d: dict = {}
            for row in rows:
                if len(row) == 2:
                    d[row[0].strip().lower().replace(" ", "_")] = row[1].strip()
            result = {
                "name":           d.get("name", "N/A"),
                "dob":            d.get("dob", "N/A"),
                "student_id":     d.get("student_id", "N/A"),
                "timestamp":      d.get("timestamp", "N/A"),
                "total_score":    int(d.get("total_score", "0").split("/")[0]),
                "max_score":      MAX_SCORE,
                "level":          d.get("level", "N/A"),
                "interpretation": d.get("interpretation", ""),
                "recommendation": d.get("recommendation", ""),
                "answers":        [],
            }
            return jsonify({"ok": True, "result": result,
                            "level": get_level(result["total_score"])})

        elif name.endswith(".txt"):
            text   = raw.decode("utf-8")
            result = {"answers": [], "max_score": MAX_SCORE}
            for line in text.splitlines():
                for key, field in [
                    ("Name       :", "name"),
                    ("DOB        :", "dob"),
                    ("Student ID :", "student_id"),
                    ("Timestamp  :", "timestamp"),
                    ("Level      :", "level"),
                ]:
                    if line.startswith(key):
                        result[field] = line[len(key):].strip()
                if line.startswith("Total Score:"):
                    val = line.split(":")[1].strip().split("/")[0]
                    result["total_score"] = int(val)
            result.setdefault("total_score", 0)
            lvl = get_level(result["total_score"])
            result.setdefault("interpretation", lvl["interpretation"])
            result.setdefault("recommendation", lvl["recommendation"])
            return jsonify({"ok": True, "result": result,
                            "level": lvl})
        else:
            return jsonify({"ok": False, "error": "Unsupported format."}), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ENTRY POINT

if __name__ == "__main__":
    app.run(debug=True, port=5000)
