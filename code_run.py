# code_run.py
import subprocess
import tempfile
import os
import requests

STATIC_IMG_PATH = "static/plot.png"
PISTON_URL = "https://emkc.org/api/v2/piston/execute"

LANGUAGE_MAP = {
    "python": "python3",
    "javascript": "javascript",
    "c": "c",
    "cpp": "cpp",
    "java": "java"
}

def run_code(language, code, stdin=''):
    if language == "python":
        return run_python(code, stdin)
    elif language in LANGUAGE_MAP:
        return run_via_piston(language, code, stdin)
    else:
        return {"output": f"Unsupported language: {language}", "image": None}

def run_python(code, stdin=''):
    if os.path.exists(STATIC_IMG_PATH):
        os.remove(STATIC_IMG_PATH)

    if "plt.show()" in code:
        code = code.replace("plt.show()", f"plt.savefig('{STATIC_IMG_PATH}')")
    elif "plt.plot" in code and "plt.savefig" not in code:
        code += f"\nplt.savefig('{STATIC_IMG_PATH}')"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode='w') as tmp:
        tmp.write(code)
        tmp.flush()
        result = subprocess.run(
            ["python", tmp.name],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
    os.unlink(tmp.name)
    output = result.stdout + result.stderr
    return {
        "output": output.strip(),
        "image": STATIC_IMG_PATH if os.path.exists(STATIC_IMG_PATH) else None
    }

def run_via_piston(language, code, stdin=''):
    VERSION_MAP = {
        "python": "3.10.0",
        "javascript": "18.15.0",
        "c": "10.2.0",
        "cpp": "10.2.0",
        "java": "15.0.2"
    }

    lang_key = LANGUAGE_MAP[language]
    version = VERSION_MAP.get(language)

    payload = {
        "language": lang_key,
        "version": version,
        "files": [{"name": f"main.{language}", "content": code}],
        "stdin": stdin
    }

    response = requests.post(PISTON_URL, json=payload)
    if response.status_code != 200:
        return {"output": f"Piston API error: {response.text}", "image": None}

    result = response.json()
    output = result.get("run", {}).get("stdout", "") + result.get("run", {}).get("stderr", "")
    return {"output": output.strip() or "No output.", "image": None}
