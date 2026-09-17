# code_run.py
import os
import subprocess
import sys
import tempfile

import requests

STATIC_IMG_PATH = os.path.join("static", "plot.png")
PISTON_URL = os.getenv("PISTON_API_URL", "https://emkc.org/api/v2/piston/execute").strip()
PISTON_API_KEY = os.getenv("PISTON_API_KEY", "").strip()

LANGUAGE_MAP = {
    "python": "python3",
    "javascript": "javascript",
    "c": "c",
    "cpp": "cpp",
    "java": "java",
}


def run_code(language, code, stdin=""):
    language = (language or "").strip().lower()
    if not code or not code.strip():
        return {"output": "Code is required.", "image": None}

    if language == "python":
        return run_python(code, stdin)
    if language in LANGUAGE_MAP:
        return run_via_piston(language, code, stdin)
    return {"output": f"Unsupported language: {language}", "image": None}


def run_python(code, stdin=""):
    os.makedirs(os.path.dirname(STATIC_IMG_PATH), exist_ok=True)
    if os.path.exists(STATIC_IMG_PATH):
        try:
            os.remove(STATIC_IMG_PATH)
        except OSError:
            pass

    if "plt.show()" in code:
        code = code.replace("plt.show()", f"plt.savefig({STATIC_IMG_PATH!r})")
    elif "plt.plot" in code and "plt.savefig" not in code:
        code += f"\nplt.savefig({STATIC_IMG_PATH!r})"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".py",
            mode="w",
            encoding="utf-8",
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            input=stdin or "",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            cwd=os.getcwd(),
        )

        output = (result.stdout or "") + (result.stderr or "")
        return {
            "output": output.strip() or "No output.",
            "image": STATIC_IMG_PATH if os.path.exists(STATIC_IMG_PATH) else None,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"output": "Execution timed out after 10 seconds.", "image": None, "exit_code": -1}
    except Exception as exc:
        return {"output": f"Python runner error: {exc}", "image": None, "exit_code": -1}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def run_via_piston(language, code, stdin=""):
    version_map = {
        "python": "3.x",
        "javascript": "18.x",
        "c": "10.x",
        "cpp": "10.x",
        "java": "15.x",
    }

    if not PISTON_API_KEY:
        return {
            "output": (
                "Piston code execution is not configured. "
                "Set PISTON_API_KEY in the hosting environment. "
                "The public Piston API now requires authorization."
            ),
            "image": None,
            "exit_code": -1,
        }

    payload = {
        "language": LANGUAGE_MAP[language],
        "version": version_map.get(language, "*"),
        "files": [{"name": f"main.{language}", "content": code}],
        "stdin": stdin or "",
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PISTON_API_KEY}",
    }

    try:
        response = requests.post(
            PISTON_URL,
            json=payload,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        return {
            "output": f"Code execution service unavailable: {exc}",
            "image": None,
            "exit_code": -1,
        }

    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:1000]
        return {
            "output": f"Piston API error ({response.status_code}): {detail}",
            "image": None,
            "exit_code": -1,
        }

    try:
        result = response.json()
    except ValueError:
        return {"output": "Piston returned an invalid response.", "image": None, "exit_code": -1}

    compile_result = result.get("compile") or {}
    run_result = result.get("run") or {}
    output = "".join(
        part for part in [
            compile_result.get("stdout", ""),
            compile_result.get("stderr", ""),
            run_result.get("stdout", ""),
            run_result.get("stderr", ""),
        ] if part
    )

    return {
        "output": output.strip() or "No output.",
        "image": None,
        "exit_code": run_result.get("code", 0),
    }
