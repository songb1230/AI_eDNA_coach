"""
AI-Guided Lab-Skill Coaching System (AI-GLCS)
FastAPI Backend - powered by local Ollama models
"""

import os
import json
import sqlite3
import uuid
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# App & Ollama Setup
# ─────────────────────────────────────────────

app = FastAPI(title="AI-GLCS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

SYSTEM_PROMPT = """You are an expert lab-skills coach specializing in wet lab biology and chemistry procedures.

Your role:
1. PROCEDURE GUIDE — Walk users through protocols step by step. Be precise, safety-first, and thorough.
2. ASSESSMENT — Generate targeted quiz questions and evaluate answers with detailed explanations.
3. ERROR DETECTION — Analyze described actions to identify mistakes, safety risks, and improvements.

Style guidelines:
- Adapt language to the user's skill level (beginner / intermediate / advanced)
- Always mention PPE and safety precautions when relevant
- Use metric units exclusively
- Be encouraging but scientifically precise
- For step-by-step guides, number each step and include expected observations

Domains covered:
- Wet lab / biology: PCR, gel electrophoresis, cell culture, Western blot, micropipetting, ELISA
- Chemistry: titration, TLC, recrystallization, UV-Vis spectroscopy, solution preparation, reflux
"""

# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "glcs.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                learner_name TEXT,
                skill_level TEXT DEFAULT 'beginner'
            );

            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                module TEXT NOT NULL,
                action TEXT NOT NULL,
                score REAL,
                notes TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                context TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        """)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


init_db()

# ─────────────────────────────────────────────
# Lab Procedures Catalog
# ─────────────────────────────────────────────

PROCEDURES = {
    "wet_lab": [
        {
            "id": "pcr",
            "name": "Polymerase Chain Reaction (PCR)",
            "difficulty": "intermediate",
            "duration": "3–4 hours",
            "description": "Amplify a specific DNA sequence using thermal cycling.",
            "key_steps": ["DNA extraction/template prep", "Master mix preparation", "Primer design check",
                          "Thermal cycler programming", "Agarose gel verification"],
            "safety": ["Handle ethidium bromide with nitrile gloves", "UV exposure — use face shield"],
        },
        {
            "id": "gel_electrophoresis",
            "name": "Agarose Gel Electrophoresis",
            "difficulty": "beginner",
            "duration": "1–2 hours",
            "description": "Separate DNA/RNA fragments by size through an agarose matrix.",
            "key_steps": ["Gel preparation (0.8–2% agarose)", "Buffer preparation (TAE/TBE)", "Sample loading",
                          "Running conditions (80–120 V)", "Staining and imaging"],
            "safety": ["EtBr is mutagenic — use SYBR Safe as alternative", "Electrical hazard"],
        },
        {
            "id": "cell_culture",
            "name": "Mammalian Cell Culture & Passaging",
            "difficulty": "intermediate",
            "duration": "30–45 min",
            "description": "Maintain and subculture adherent mammalian cell lines.",
            "key_steps": ["Biosafety cabinet preparation", "Media aspiration", "PBS wash", "Trypsinization",
                          "Neutralization & counting", "Re-seeding at target density"],
            "safety": ["BSL-2 precautions", "Sterile technique at all times"],
        },
        {
            "id": "western_blot",
            "name": "Western Blot",
            "difficulty": "advanced",
            "duration": "2 days",
            "description": "Detect specific proteins in a sample using antibody-based detection.",
            "key_steps": ["Protein extraction & quantification", "SDS-PAGE gel preparation & running",
                          "Transfer to membrane", "Blocking", "Primary antibody incubation",
                          "Secondary antibody & detection"],
            "safety": ["Acrylamide is a neurotoxin", "Methanol in transfer buffer — ventilation required"],
        },
        {
            "id": "elisa",
            "name": "ELISA (Enzyme-Linked Immunosorbent Assay)",
            "difficulty": "intermediate",
            "duration": "4–6 hours",
            "description": "Quantify proteins, antibodies, or antigens using antibody binding.",
            "key_steps": ["Plate coating with capture antibody", "Blocking", "Sample/standard addition",
                          "Detection antibody", "Enzyme substrate addition", "Absorbance reading"],
            "safety": ["Dispose of biological samples per BSL protocols"],
        },
    ],
    "chemistry": [
        {
            "id": "acid_base_titration",
            "name": "Acid-Base Titration",
            "difficulty": "beginner",
            "duration": "1–2 hours",
            "description": "Determine the concentration of an acid or base using a standardized solution.",
            "key_steps": ["Burette preparation & filling", "Indicator selection", "Sample preparation",
                          "Titration to endpoint", "Data recording & calculation"],
            "safety": ["Strong acids/bases cause burns — neutralize spills immediately"],
        },
        {
            "id": "tlc",
            "name": "Thin Layer Chromatography (TLC)",
            "difficulty": "beginner",
            "duration": "30–60 min",
            "description": "Separate and identify compounds based on polarity.",
            "key_steps": ["TLC plate preparation", "Solvent system selection", "Spotting samples",
                          "Chamber saturation", "Development & drying", "Visualization (UV/stain)"],
            "safety": ["Organic solvents — work in fume hood", "UV exposure — wear protective eyewear"],
        },
        {
            "id": "recrystallization",
            "name": "Recrystallization",
            "difficulty": "intermediate",
            "duration": "2–3 hours",
            "description": "Purify a solid compound by dissolving in hot solvent and recrystallizing.",
            "key_steps": ["Solvent selection", "Dissolution at elevated temperature", "Hot filtration (if needed)",
                          "Controlled cooling", "Crystal collection & washing", "Drying & yield calculation"],
            "safety": ["Hot glassware — use heat-resistant gloves", "Flammable solvents — no open flames"],
        },
        {
            "id": "uv_vis",
            "name": "UV-Vis Spectroscopy",
            "difficulty": "beginner",
            "duration": "1 hour",
            "description": "Measure absorbance/transmittance of solutions to determine concentration.",
            "key_steps": ["Instrument warm-up", "Blank preparation & baseline correction",
                          "Sample preparation & cuvette filling", "Wavelength scan or fixed λ measurement",
                          "Beer-Lambert law calculation"],
            "safety": ["UV radiation — do not look directly at lamp"],
        },
        {
            "id": "solution_prep",
            "name": "Solution Preparation (Molarity & Dilution)",
            "difficulty": "beginner",
            "duration": "30–60 min",
            "description": "Prepare solutions of known concentration from solids or stock solutions.",
            "key_steps": ["Molar mass calculation", "Mass/volume calculation", "Weighing & dissolving",
                          "Quantitative transfer to volumetric flask", "Making to volume", "Labeling"],
            "safety": ["Concentrated acids — add acid to water, never reverse"],
        },
    ],
}

ALL_PROCEDURES = {p["id"]: {**p, "domain": domain}
                  for domain, procs in PROCEDURES.items()
                  for p in procs}

# ─────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────


class SessionCreate(BaseModel):
    learner_name: str = "Learner"
    skill_level: str = "beginner"  # beginner | intermediate | advanced


class ProcedureChat(BaseModel):
    session_id: str
    procedure_id: str
    message: str
    history: List[dict] = []  # [{role: "user"|"assistant", content: "..."}]


class AssessmentRequest(BaseModel):
    session_id: str
    procedure_id: str
    num_questions: int = 5
    skill_level: str = "beginner"


class AssessmentAnswer(BaseModel):
    session_id: str
    procedure_id: str
    question: str
    user_answer: str
    skill_level: str = "beginner"


class ErrorCheckRequest(BaseModel):
    session_id: str
    procedure_id: str
    described_actions: str
    skill_level: str = "beginner"


class ProgressUpdate(BaseModel):
    session_id: str
    module: str
    action: str
    score: Optional[float] = None
    notes: Optional[str] = None


# ─────────────────────────────────────────────
# Helper: Ollama API call
# ─────────────────────────────────────────────


def call_llm(messages: list, system_extra: str = "") -> str:
    system = SYSTEM_PROMPT
    if system_extra:
        system += f"\n\n{system_extra}"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {
            "num_predict": 1024,
        },
    }
    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=503,
            detail=(
                f"Ollama returned HTTP {exc.code} for model '{OLLAMA_MODEL}'. "
                f"Try: ollama pull {OLLAMA_MODEL}. Details: {detail}"
            ),
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not reach Ollama at {OLLAMA_BASE_URL}. "
                "Start Ollama and pull the configured model, then try again."
            ),
        ) from exc

    content = data.get("message", {}).get("content")
    if not content:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response.")
    return content


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────


@app.get("/")
def root():
    return {"status": "AI-GLCS API running", "version": "1.0.0"}


# ── Session Management ──


@app.post("/api/session/create")
def create_session(body: SessionCreate):
    session_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, created_at, learner_name, skill_level) VALUES (?, ?, ?, ?)",
            (session_id, datetime.utcnow().isoformat(), body.learner_name, body.skill_level),
        )
    return {"session_id": session_id, "learner_name": body.learner_name, "skill_level": body.skill_level}


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        return dict(row)


# ── Procedures Catalog ──


@app.get("/api/procedures")
def list_procedures(domain: Optional[str] = None):
    if domain:
        procs = PROCEDURES.get(domain, [])
        return {"domain": domain, "procedures": procs}
    return {"procedures": PROCEDURES}


@app.get("/api/procedures/{procedure_id}")
def get_procedure(procedure_id: str):
    proc = ALL_PROCEDURES.get(procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return proc


# ── Procedure Coach (Conversational) ──


@app.post("/api/procedure/chat")
def procedure_chat(body: ProcedureChat):
    proc = ALL_PROCEDURES.get(body.procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procedure not found")

    # Retrieve session skill level
    with get_db() as conn:
        session = conn.execute(
            "SELECT skill_level, learner_name FROM sessions WHERE session_id = ?", (body.session_id,)
        ).fetchone()
    skill_level = session["skill_level"] if session else "beginner"
    learner_name = session["learner_name"] if session else "Learner"

    context = f"""
Procedure: {proc['name']}
Domain: {proc['domain'].replace('_', ' ').title()}
Difficulty: {proc['difficulty']}
Key steps: {', '.join(proc['key_steps'])}
Safety notes: {', '.join(proc['safety'])}
Learner: {learner_name} (skill level: {skill_level})

You are now coaching this learner through this procedure. Answer their questions, guide them step by step,
and proactively point out safety considerations. Tailor your explanations to their skill level.
"""
    messages = list(body.history) + [{"role": "user", "content": body.message}]
    reply = call_llm(messages, system_extra=context)

    # Save to chat history
    with get_db() as conn:
        ts = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO chat_history (session_id, context, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (body.session_id, body.procedure_id, "user", body.message, ts),
        )
        conn.execute(
            "INSERT INTO chat_history (session_id, context, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (body.session_id, body.procedure_id, "assistant", reply, ts),
        )
        conn.execute(
            "INSERT INTO progress (session_id, module, action, timestamp) VALUES (?, ?, ?, ?)",
            (body.session_id, proc["name"], "procedure_interaction", ts),
        )

    return {"reply": reply, "procedure": proc["name"]}


# ── Assessment ──


@app.post("/api/assessment/generate")
def generate_assessment(body: AssessmentRequest):
    proc = ALL_PROCEDURES.get(body.procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procedure not found")

    prompt = f"""Generate exactly {body.num_questions} assessment questions for: {proc['name']}.

Skill level: {body.skill_level}
Key steps to cover: {json.dumps(proc['key_steps'])}
Safety aspects: {json.dumps(proc['safety'])}

Return ONLY a valid JSON array, no other text:
[
  {{
    "id": 1,
    "question": "...",
    "type": "multiple_choice" | "short_answer",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],  // only for multiple_choice
    "correct_answer": "...",
    "explanation": "...",
    "difficulty": "easy" | "medium" | "hard"
  }},
  ...
]

For multiple_choice questions, include 4 options. For short_answer, omit options.
Mix types: 60% multiple_choice, 40% short_answer. Ensure questions cover safety, theory, and technique."""

    raw = call_llm([{"role": "user", "content": prompt}])

    # Parse JSON from response
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        questions = json.loads(raw[start:end])
    except Exception:
        questions = [{"id": 1, "question": raw, "type": "short_answer", "difficulty": "medium"}]

    # Save progress event
    with get_db() as conn:
        conn.execute(
            "INSERT INTO progress (session_id, module, action, timestamp) VALUES (?, ?, ?, ?)",
            (body.session_id, proc["name"], "assessment_started", datetime.utcnow().isoformat()),
        )

    return {"procedure": proc["name"], "questions": questions, "num_questions": len(questions)}


@app.post("/api/assessment/evaluate")
def evaluate_answer(body: AssessmentAnswer):
    proc = ALL_PROCEDURES.get(body.procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procedure not found")

    prompt = f"""Evaluate this answer for: {proc['name']}

Question: {body.question}
Learner's answer: {body.user_answer}
Learner skill level: {body.skill_level}

Respond with ONLY valid JSON (no other text):
{{
  "is_correct": true | false,
  "score": 0.0–1.0,
  "feedback": "2-3 sentence explanation of what was correct/incorrect",
  "correct_answer": "The complete correct answer",
  "follow_up_tip": "One actionable tip for improvement"
}}"""

    raw = call_llm([{"role": "user", "content": prompt}])

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        result = json.loads(raw[start:end])
    except Exception:
        result = {"is_correct": False, "score": 0.0, "feedback": raw, "correct_answer": "", "follow_up_tip": ""}

    # Save score to progress
    with get_db() as conn:
        conn.execute(
            "INSERT INTO progress (session_id, module, action, score, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (body.session_id, proc["name"], "assessment_answer",
             result.get("score", 0), body.question[:200], datetime.utcnow().isoformat()),
        )

    return result


# ── Error Detection ──


@app.post("/api/error-check")
def error_check(body: ErrorCheckRequest):
    proc = ALL_PROCEDURES.get(body.procedure_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Procedure not found")

    prompt = f"""Analyze this learner's described lab actions for errors and issues.

Procedure: {proc['name']}
Correct key steps: {json.dumps(proc['key_steps'])}
Safety requirements: {json.dumps(proc['safety'])}
Learner skill level: {body.skill_level}

Learner's description:
\"\"\"{body.described_actions}\"\"\"

Respond with ONLY valid JSON (no other text):
{{
  "overall_assessment": "brief 1-sentence summary",
  "safety_issues": ["list of safety problems found, empty if none"],
  "technique_errors": ["list of technique mistakes, empty if none"],
  "missing_steps": ["important steps not mentioned"],
  "positive_observations": ["things done correctly"],
  "severity": "critical" | "moderate" | "minor" | "none",
  "corrective_guidance": "detailed paragraph explaining how to improve",
  "score": 0–100
}}"""

    raw = call_llm([{"role": "user", "content": prompt}])

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        result = json.loads(raw[start:end])
    except Exception:
        result = {"overall_assessment": raw, "safety_issues": [], "technique_errors": [],
                  "missing_steps": [], "positive_observations": [], "severity": "unknown",
                  "corrective_guidance": "", "score": 0}

    # Save to progress
    with get_db() as conn:
        conn.execute(
            "INSERT INTO progress (session_id, module, action, score, timestamp) VALUES (?, ?, ?, ?, ?)",
            (body.session_id, proc["name"], "error_check", result.get("score", 0), datetime.utcnow().isoformat()),
        )

    return result


# ── Progress Tracking ──


@app.get("/api/progress/{session_id}")
def get_progress(session_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM progress WHERE session_id = ? ORDER BY timestamp DESC",
            (session_id,)
        ).fetchall()
        records = [dict(r) for r in rows]

    # Compute per-module stats
    modules: dict = {}
    for r in records:
        m = r["module"]
        if m not in modules:
            modules[m] = {"interactions": 0, "assessments": 0, "error_checks": 0,
                          "scores": [], "last_activity": r["timestamp"]}
        modules[m]["interactions"] += 1
        if r["action"] == "assessment_answer" and r["score"] is not None:
            modules[m]["assessments"] += 1
            modules[m]["scores"].append(r["score"])
        if r["action"] == "error_check" and r["score"] is not None:
            modules[m]["error_checks"] += 1
            modules[m]["scores"].append(r["score"] / 100)  # normalize to 0-1

    summary = []
    for name, data in modules.items():
        avg_score = (sum(data["scores"]) / len(data["scores"]) * 100) if data["scores"] else None
        summary.append({
            "module": name,
            "interactions": data["interactions"],
            "assessments": data["assessments"],
            "error_checks": data["error_checks"],
            "avg_score": round(avg_score, 1) if avg_score is not None else None,
            "last_activity": data["last_activity"],
        })

    total_interactions = len(records)
    all_scores = [r["score"] for r in records if r["score"] is not None]
    overall_avg = round(sum(all_scores) / len(all_scores) * 100, 1) if all_scores else 0

    return {
        "session_id": session_id,
        "total_interactions": total_interactions,
        "overall_avg_score": overall_avg,
        "modules_practiced": len(modules),
        "module_breakdown": summary,
        "recent_activity": records[:10],
    }


@app.post("/api/progress/update")
def update_progress(body: ProgressUpdate):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO progress (session_id, module, action, score, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (body.session_id, body.module, body.action, body.score, body.notes, datetime.utcnow().isoformat()),
        )
    return {"status": "recorded"}


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
