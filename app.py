import os
import json
from datetime import datetime
from io import BytesIO

import bcrypt
from google import genai
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
    value = os.getenv(name, "").strip()
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

# Supports either one key or multiple comma-separated keys.
# Example: GEMINI_API_KEYS=key1,key2,key3
GEMINI_API_KEYS = [
    key.strip().strip('"').strip("'")
    for key in os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")).split(",")
    if key.strip()
]

if not GEMINI_API_KEYS:
    raise RuntimeError(
        "Missing GEMINI_API_KEYS (or GEMINI_API_KEY). "
        "Provide one or more Gemini API keys in your environment."
    )

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID", "").strip()
# Default to the user's current Gemini 3.5 Flash-Lite model. This remains
# configurable through GEMINI_MODEL so the model can be changed without code edits.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

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


def create_gemini_client(api_key: str):
    """Create the current Google GenAI client using an API key.

    The project previously used the deprecated google-generativeai package.
    Google recommends the google-genai SDK for the current Gemini API and newer
    API-key formats.
    """
    return genai.Client(api_key=api_key)


def generate_with_gemini(prompt: str):
    """Generate content with configured Gemini keys and fail over safely."""
    last_error = None
    failover_markers = (
        "quota",
        "rate limit",
        "resource exhausted",
        "too many requests",
        "invalid api key",
        "permission denied",
        "unauthenticated",
        "access_token_type_unsupported",
        "401",
        "429",
        "503",
    )

    for api_key in GEMINI_API_KEYS:
        try:
            client = create_gemini_client(api_key)
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "text/plain"},
            )
        except Exception as exc:
            last_error = exc
            error_text = str(exc).lower()
            if not any(marker in error_text for marker in failover_markers):
                raise

    error_text = str(last_error) if last_error else "Unknown Gemini error"
    if "access_token_type_unsupported" in error_text.lower():
        raise RuntimeError(
            "Gemini authentication was rejected (ACCESS_TOKEN_TYPE_UNSUPPORTED). "
            "Create/configure a current Gemini API credential in Google AI Studio, "
            "make sure Gemini API is enabled for its project, and replace GEMINI_API_KEYS "
            "in your local .env or hosting environment. Do not send the key in chat."
        ) from last_error
    raise RuntimeError(
        f"Gemini request failed after trying all configured keys: {error_text}"
    ) from last_error


# -----------------------------------------------------------------------------
# Routes / application logic
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    data = request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "").strip()

    if not email or not password:
        return render_template("signup.html", error="Email and password are required.")

    existing = supabase.table("users").select("id").eq("email", email).limit(1).execute()
    if existing.data:
        return render_template("signup.html", error="An account with this email already exists.")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    result = supabase.table("users").insert({
        "email": email,
        "password_hash": password_hash,
        "name": name,
    }).execute()

    if not result.data:
        return render_template("signup.html", error="Unable to create the account.")

    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    data = request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    result = supabase.table("users").select("*").eq("email", email).limit(1).execute()
    user = result.data[0] if result.data else None

    if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    session["user_email"] = user["email"]
    session["user_name"] = user.get("name") or user["email"]
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/api/generate-answer", methods=["POST"])
def api_generate_answer():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or data.get("question") or "").strip()
    if not prompt:
        return jsonify({"error": "Prompt is required."}), 400

    try:
        response = generate_with_gemini(prompt)
        text = getattr(response, "text", None) or ""
        return jsonify({"answer": text})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/search-images", methods=["GET"])
def api_search_images():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"images": []})
    if not GOOGLE_API_KEY or not SEARCH_ENGINE_ID:
        return jsonify({"images": []})

    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_API_KEY,
                "cx": SEARCH_ENGINE_ID,
                "q": query,
                "searchType": "image",
                "num": 6,
                "safe": "active",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        images = [
            {
                "url": item.get("link"),
                "thumbnail": item.get("image", {}).get("thumbnailLink"),
                "title": item.get("title", ""),
            }
            for item in payload.get("items", [])
            if item.get("link")
        ]
        return jsonify({"images": images})
    except Exception as exc:
        return jsonify({"images": [], "error": str(exc)}), 200


@app.route("/answers")
def answers():
    if not session.get("user_id"):
        return redirect("/login")
    result = (
        supabase.table("answers")
        .select("*")
        .eq("user_id", session["user_id"])
        .order("created_at", desc=True)
        .execute()
    )
    return render_template("answers.html", answers=result.data or [])


@app.route("/delete-answer/<answer_id>", methods=["POST", "DELETE"])
def delete_answer(answer_id):
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    supabase.table("answers").delete().eq("id", answer_id).eq("user_id", session["user_id"]).execute()
    if request.method == "DELETE" or request.is_json:
        return jsonify({"success": True})
    return redirect("/answers")


@app.route("/save-answer", methods=["POST"])
def save_answer():
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form
    question = (data.get("question") or "").strip()
    answer = data.get("answer") or ""
    if not question or not answer:
        return jsonify({"error": "Question and answer are required."}), 400

    result = supabase.table("answers").insert({
        "user_id": session["user_id"],
        "question": question,
        "answer": answer,
    }).execute()
    return jsonify({"success": bool(result.data), "answer": result.data[0] if result.data else None})


@app.route("/combined-pdf", methods=["POST"])
def combined_pdf():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not items:
        return jsonify({"error": "No answers supplied."}), 400

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for item in items:
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.multi_cell(0, 10, str(item.get("question", "Question")))
        pdf.ln(3)
        pdf.set_font("Arial", size=11)
        text = str(item.get("answer", ""))
        pdf.multi_cell(0, 7, text.encode("latin-1", "replace").decode("latin-1"))

    output = BytesIO(pdf.output(dest="S").encode("latin-1"))
    output.seek(0)
    return send_file(output, mimetype="application/pdf", as_attachment=True, download_name="satyen78ai_answers.pdf")


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt") or data.get("question") or ""
    if not prompt.strip():
        return jsonify({"error": "Prompt is required."}), 400
    try:
        response = generate_with_gemini(prompt)
        return jsonify({"prediction": getattr(response, "text", "") or ""})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/run-code", methods=["POST"])
def run_code_route():
    data = request.get_json(silent=True) or {}
    language = data.get("language", "python")
    code = data.get("code", "")
    if not code.strip():
        return jsonify({"error": "Code is required."}), 400
    try:
        result = run_code(language, code)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.context_processor
def inject_user():
    return {
        "current_user": {
            "id": session.get("user_id"),
            "email": session.get("user_email"),
            "name": session.get("user_name"),
        }
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "0") == "1")
