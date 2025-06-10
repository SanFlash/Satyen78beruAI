import os
from flask import Flask, render_template, request, redirect, session, jsonify, send_file
from flask_session import Session
from datetime import datetime
from io import BytesIO
from fpdf import FPDF
from docx import Document
from supabase import create_client, Client
from dotenv import load_dotenv
import bcrypt
import google.generativeai as genai
import base64
import requests
from PIL import Image
from io import BytesIO
from docx.shared import Inches
from flask import abort
import json


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Initialize Supabase client
SUPABASE_URL = "https://eixxomrbysxndypbzqkp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVpeHhvbXJieXN4bmR5cGJ6cWtwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0ODY5MjQ5NiwiZXhwIjoyMDY0MjY4NDk2fQ.AMdQhzAXbTdDfeyIeABK6nfU_koyc8dJY9vZd3F4NfI"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)



GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key="AIzaSyBgWAiX5IzMeTsjxCdS-uTeyLlKucN0LmE")
model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
# ──────────────────────────────────────────────
# Routes: Auth
# ──────────────────────────────────────────────

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Check if user already exists
        existing_user = supabase.table("users").select("*").eq("email", email).execute()
        if existing_user.data:
            return "User already exists!"

        # Insert new user
        supabase.table("users").insert({
            "name": name,
            "email": email,
            "password": hashed_password
        }).execute()

        return redirect("/login")
    return render_template("signup.html" )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Fetch user from Supabase
        user = supabase.table("users").select("*").eq("email", email).execute()
        if not user.data:
            return "Invalid credentials!"

        user_data = user.data[0]
        if bcrypt.checkpw(password.encode('utf-8'), user_data["password"].encode('utf-8')):
            session["user_id"] = user_data["id"]
            session["user_name"] = user_data["name"]
            return redirect("/")
        else:
            return "Invalid credentials!"
    return render_template("login.html" , current_year=datetime.now().year)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ──────────────────────────────────────────────
# Home and Answer Dashboard
# ──────────────────────────────────────────────

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("index.html", user_name=session["user_name"], current_year=datetime.now().year)


@app.route("/answers")
def answers():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    answers = supabase.table("answers").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return render_template("answers.html", user_name=session["user_name"], answers=answers.data, current_year=datetime.now().year)


# ──────────────────────────────────────────────
# Generate Answer and Store It
# ──────────────────────────────────────────────

@app.route("/api/generate-answer", methods=["POST"])
def generate_answer():
    data = request.get_json()
    question = data.get("question", "").lower()
    style = data.get("style", "")

    if not question:
        return jsonify({"error": "Missing question"}), 400

    # Check if user is asking about the owner/developer
    ownership_keywords = [
        "who is the developer", "who made you", "who created you", 
        "owner of you","owner of Satyen78AI", "developer name", "built Satyen78AI app", "creator", "founder"
    ]

    if any(kw in question for kw in ownership_keywords):
        return jsonify({
            "answer": "**This project was developed by Satyendra Namdeo.**"
        })

    try:
        prompt = f"Explain in {style} style with examples and diagrams where needed:\n{question}"
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "text/plain"}
        )
        return jsonify({"answer": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
def generate_image_via_rest(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta2/models/image-alpha-001:generate"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}",
    }
    data = {
        "prompt": prompt,
        "size": "512x512",
        "candidateCount": 1,
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    res_json = response.json()
    image_url = res_json["candidates"][0]["imageUri"]
    return image_url

# ──────────────────────────────────────────────
# Download / Delete Answer
# ──────────────────────────────────────────────

@app.route("/delete/<int:id>", methods=["POST"])
def delete_single_answer(id):
    if "user_id" not in session:
        return redirect("/login")

    try:
        supabase.table("answers") \
            .delete() \
            .eq("user_id", session["user_id"]) \
            .eq("id", id) \
            .execute()
    except Exception as e:
        return f"Error deleting answer: {str(e)}", 500

    return redirect("/answers")

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
        response = supabase.table("answers") \
            .select("*") \
            .eq("user_id", session["user_id"]) \
            .in_("id", ids) \
            .order("created_at", desc=True) \
            .execute()
        answers = response.data
    except Exception as e:
        return f"Error fetching answers: {str(e)}", 500

    if not answers:
        return "No answers found", 404

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for ans in answers:
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, f"Q: {ans['question']}")
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, ans["answer"])
        
        image_url = ans.get("image_url")
        if image_url:
            try:
                img_resp = requests.get(image_url)
                img = Image.open(BytesIO(img_resp.content))
                img_path = f"/tmp/temp_img_{ans['id']}.jpg"
                img.convert("RGB").save(img_path, "JPEG")
                pdf.image(img_path, w=150)
            except Exception as e:
                pdf.multi_cell(0, 10, f"[Image failed to load: {str(e)}]")

    pdf_data = pdf.output(dest='S').encode('latin1')
    return send_file(BytesIO(pdf_data), mimetype='application/pdf', as_attachment=True, download_name='answers.pdf')



@app.route("/api/save-answer", methods=["POST"])
def save_answer():
    data = request.get_json()
    question = data.get("question")
    answer = data.get("answer")

    user_id = session.get("user_id")  # Use user_id from session

    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    try:
        supabase.table("answers").insert({
            "user_id": user_id,
            "question": question,
            "answer": answer,
            "created_at": datetime.utcnow().isoformat()  # Optional: track creation time
        }).execute()
        return jsonify({"message": "Answer saved successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import markdown2  

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    predicted_questions = None
    if request.method == 'POST':
        unit = request.form['unit']
        level = request.form['level']

        # Enhanced prompt for per-topic breakdown with 2–5 questions
        prompt = f"""
You are an expert academic question generator.

Given the following unit-wise syllabus topics:

{unit}

For **each topic**, generate between **3 to 5** questions depending on complexity. All questions should be of **{level} level**. Organize them by topic with clear headings, and use **bulleted lists** for the questions. 
Ensure formatting is clean and if applicable, include code blocks, tables, or diagrams in markdown.

Example format:
### Topic Name
- Question 1
- Question 2
...
        
Only output the final set of questions in markdown.
"""

        try:
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            html_output = markdown2.markdown(raw_text)  # Convert markdown → HTML
            predicted_questions = html_output
        except Exception as e:
            predicted_questions = f"<p><strong>Error generating questions:</strong> {str(e)}</p>"

    return render_template("predict.html",user_name=session["user_name"], predicted_questions=predicted_questions, current_year=datetime.now().year)

@app.route('/')
def index():
    return render_template("predict.html", predicted_questions=None)

# ──────────────────────────────────────────────
# Run the Flask app
# ──────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
