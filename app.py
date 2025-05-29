from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import google.generativeai as genai
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Load Gemini API Key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini SDK
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/generate-answer", methods=["POST"])
def generate_answer():
    data = request.get_json()
    question = data.get("question")
    style = data.get("style", "")

    if not question:
        return jsonify({"error": "Missing question"}), 400

    try:
        prompt = f"Explain in {style} style with examples and diagrams where needed:\n{question}"
        response = model.generate_content(prompt)
        return jsonify({"answer": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
