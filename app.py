import os
import json
from datetime import datetime
from io import BytesIO

import bcrypt
import google.generativeai as genai
import markdown2
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, jsonify, send_file, abort
from flask_session import Session
from fpdf import FPDF
from PIL import Image
from supabase import create_client

from code_run import run_code

# Load environment variables from the local environment / .env.
# No API keys or database secrets belong in source control.
load_dotenv()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it locally or in your hosting provider's environment settings."
        )
    return value


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SECRET_KEY = required_env("SECRET_KEY")
SUPABASE_URL = required_env("SUPABASE_URL")
SUPABASE_KEY = required_env("SUPABASE_KEY")
GEMINI_API_KEYS = [
    key.strip()
    for key in os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")).split(",")
    if key.strip()
]

if not GEMINI_API_KEYS:
    raise RuntimeError(
        "Missing GEMINI_API_KEYS (or GEMINI_API_KEY). "
        "Provide one or more comma-separated Gemini API keys in your environment."
    )

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# -----------------------------------------------------------------------------
# Flask app
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_TYPE="filesystem",
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
)
Session(app)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def configure_gemini(api_key: str):
    """Configure Gemini for a single request without exposing the key to clients."""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=GEMINI_MODEL)


def generate_with_gemini(prompt: str):
    """Try configured Gemini keys in sequence, failing over on quota/auth errors."""
    last_error = None
    for api_key in GEMINI_API_KEYS:
        try:
            model = configure_gemini(api_key)
            return model.generate_content(
                prompt,
                generation_config={"response_mime_type": "text/plain"},
            )
        except Exception as exc:
            last_error = exc
            # Quota/rate-limit/auth failures can be handled by the next configured key.
            message = str(exc).lower()
            retryable = any(
                marker in message
                for marker in (
                    "quota",
                    "rate limit",
                    "resource exhausted",
                    "too many requests",
                    "invalid api key",
                    "permission denied",
                    "unauthenticated",
                )
            )
            if not retryable:
                raise

    raise RuntimeError(f"All configured Gemini API keys failed: {last_error}")


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return "Name, email and password are required.", 400

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        existing_user = (
            supabase.table("users").select("id").eq("email", email).execute()
        )
        if existing_user.data:
            return "User already exists!", 409

        supabase.table("users").insert(
            {"name": name, "email": email, "password": hashed_password}
        ).execute()
        return redirect("/login")

    return render_template("signup.html", current_year=datetime.now().year)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = supabase.table("users").select("*").eq("email", email).execute()
        if not user.data:
            return "Invalid credentials!", 401

        user_data = user.data[0]
        if bcrypt.checkpw(
            password.encode("utf-8"), user_data["password"].encode("utf-8")
        ):
            session.clear()
            session["user_id"] = user_data["id"]
            session["user_name"] = user_data["name"]
            return redirect("/")

        return "Invalid credentials!", 401

    return render_template("login.html", current_year=datetime.now().year)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -----------------------------------------------------------------------------
# Pages
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")
    return render_template(
        "index.html",
        user_name=session.get("user_name", "Student"),
        current_year=datetime.now().year,
        image_search_enabled=bool(GOOGLE_API_KEY and SEARCH_ENGINE_ID),
    )


@app.route("/answers")
def answers():
    if "user_id" not in session:
        return redirect("/login")

    response = (
        supabase.table("answers")
        .select("*")
        .eq("user_id", session["user_id"])
        .order("created_at", desc=True)
        .execute()
    )
    return render_template(
        "answers.html",
        user_name=session.get("user_name", "Student"),
        answers=response.data,
        current_year=datetime.now().year,
    )


# -----------------------------------------------------------------------------
# AI answer generation
# -----------------------------------------------------------------------------
@app.route("/api/generate-answer", methods=["POST"])
def generate_answer():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    style = data.get("style", "").strip()

    if not question:
        return jsonify({"error": "Missing question"}), 400

    ownership_keywords = [
        "who is the developer", "who made you", "who created you", "who is your creator",
        "who built you", "who is your developer", "owner of you", "owner of satyen78ai",
        "developer of satyen78ai", "developer name", "created satyen78ai", "built satyen78ai",
        "founder of satyen78ai", "satyen78ai creator", "satyen78ai developer",
        "who is behind satyen78ai", "who owns satyen78ai", "who developed satyen78ai",
        "who programmed satyen78ai", "maker of satyen78ai", "who is the founder of satyen78ai",
        "who made satyen78ai", "who coded satyen78ai", "satyen78ai owner",
        "who designed satyen78ai", "who launched satyen78ai", "engineer of satyen78ai",
        "developer info satyen78ai", "satyen78ai author", "satyen78ai inventor",
        "satyen78ai maker", "who runs satyen78ai", "satyen78ai team", "person behind satyen78ai",
        "who started satyen78ai", "lead developer satyen78ai", "lead engineer satyen78ai",
        "who's managing satyen78ai", "credits for satyen78ai", "who owns this app",
        "satyen78ai founder name", "who deployed satyen78ai", "satyen78ai credits",
        "who operates satyen78ai", "satyen78ai powered by", "satyen78ai maintained by",
    ]

    normalized_question = question.lower()
    if any(keyword in normalized_question for keyword in ownership_keywords):
        return jsonify({"answer": "**This project was developed by Satyendra Namdeo.**"})

    prompt = (
        f"Explain in {style or 'Easy'} style with examples and diagrams where needed:\n"
        f"{question}"
    )

    try:
        response = generate_with_gemini(prompt)
        return jsonify({"answer": response.text})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


# -----------------------------------------------------------------------------
# Optional image search proxy
# -----------------------------------------------------------------------------
@app.route("/api/search-images", methods=["GET"])
def search_images():
    if not GOOGLE_API_KEY or not SEARCH_ENGINE_ID:
        return jsonify({"items": [], "enabled": False})

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"items": [], "enabled": True})

    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "q": f"{query} diagram OR figure OR image",
                "cx": SEARCH_ENGINE_ID,
                "searchType": "image",
                "num": 3,
                "key": GOOGLE_API_KEY,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        items = [
            {
                "link": item.get("link"),
                "title": item.get("title", "Related image"),
                "contextLink": item.get("image", {}).get("contextLink"),
            }
            for item in payload.get("items", [])
            if item.get("link")
        ]
        return jsonify({"items": items, "enabled": True})
    except requests.RequestException:
        return jsonify({"items": [], "enabled": True})


# -----------------------------------------------------------------------------
# Answers / downloads
# -----------------------------------------------------------------------------
@app.route("/delete/<int:id>", methods=["POST"])
def delete_single_answer(id):
    if "user_id" not in session:
        return redirect("/login")

    try:
        (
            supabase.table("answers")
            .delete()
            .eq("user_id", session["user_id"])
            .eq("id", id)
            .execute()
        )
    except Exception as exc:
        return f"Error deleting answer: {exc}", 500

    return redirect("/answers")


@app.route("/api/save-answer", methods=["POST"])
def save_answer():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "User not logged in"}), 401
    if not question or not answer:
        return jsonify({"error": "Question and answer are required"}), 400

    try:
        supabase.table("answers").insert(
            {
                "user_id": user_id,
                "question": question,
                "answer": answer,
                "created_at": datetime.utcnow().isoformat(),
            }
        ).execute()
        return jsonify({"message": "Answer saved successfully."})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/download/combined/pdf", methods=["POST"])
def download_combined_pdf():
    if "user_id" not in session:
        return abort(401)

    try:
        ids = json.loads(request.form.get("ids", "[]"))
        if not isinstance(ids, list) or not all(isinstance(i, (int, str)) for i in ids):
            return "Invalid IDs format", 400
    except Exception:
        return "Invalid data", 400

    try:
        response = (
            supabase.table("answers")
            .select("*")
            .eq("user_id", session["user_id"])
            .in_("id", ids)
            .order("created_at", desc=True)
            .execute()
        )
        saved_answers = response.data
    except Exception as exc:
        return f"Error fetching answers: {exc}", 500

    if not saved_answers:
        return "No answers found", 404

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for ans in saved_answers:
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, f"Q: {ans['question']}")
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, ans["answer"])

        image_url = ans.get("image_url")
        if image_url:
            try:
                img_resp = requests.get(image_url, timeout=15)
                img_resp.raise_for_status()
                img = Image.open(BytesIO(img_resp.content)).convert("RGB")
                img_path = f"/tmp/temp_img_{ans['id']}.jpg"
                img.save(img_path, "JPEG")
                pdf.image(img_path, w=150)
            except Exception:
                pdf.multi_cell(0, 10, "[Related image could not be embedded]")

    pdf_data = pdf.output(dest="S").encode("latin1")
    return send_file(
        BytesIO(pdf_data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="answers.pdf",
    )


# -----------------------------------------------------------------------------
# Predicted questions
# -----------------------------------------------------------------------------
@app.route("/predict", methods=["GET", "POST"])
def predict():
    predicted_questions = None

    if request.method == "POST":
        unit = request.form.get("unit", "").strip()
        level = request.form.get("level", "").strip()

        prompt = f"""
You are an expert academic question generator.

Given the following unit-wise syllabus topics:

{unit}

For each topic, generate between 3 to 5 questions depending on complexity.
All questions should be of {level} level. Organize them by topic with clear headings,
use bulleted lists, and keep formatting clean. If applicable, include code blocks,
tables, or diagrams in markdown.

Only output the final set of questions in markdown.
"""

        try:
            response = generate_with_gemini(prompt)
            predicted_questions = markdown2.markdown(response.text.strip())
        except Exception as exc:
            predicted_questions = f"<p><strong>Error generating questions:</strong> {exc}</p>"

    return render_template(
        "predict.html",
        user_name=session.get("user_name", "Guest"),
        predicted_questions=predicted_questions,
        current_year=datetime.now().year,
    )


@app.route("/run", methods=["POST"])
def run():
    data = request.get_json(silent=True) or {}
    language = data.get("language", "")
    code = data.get("code", "")
    stdin = data.get("stdin", "")
    return jsonify(run_code(language, code, stdin))


@app.route("/run-code")
def run_code_ui():
    return render_template(
        "run_code.html", user_name=session.get("user_name", "Guest")
    )


@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now().year,
        "user_name": session.get("user_name", "Guest"),
    }


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
