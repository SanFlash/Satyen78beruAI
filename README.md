# Satyen78AI

> **Learn faster. Ask clearly. Get visual study-ready answers.**

Satyen78AI is a Flask-based academic AI web app designed to help students understand topics quickly. Users can enter a topic and question, choose an explanation style such as Easy, Hinglish, or Professional, and receive an AI-generated answer with optional related images. The app also includes authentication, saved answers, PDF export, syllabus-based question generation, and a code-running page.

## Latest release updates

This release focuses on **Gemini reliability, code-runner reliability, current API compatibility, security, and deployment readiness without changing the core product layout**.

### Code Runner updates

- Fixed the frontend/backend endpoint mismatch: the UI now calls `/run-code`, which is the Flask API route.
- Added clear JSON error handling when the runner service is unavailable.
- Python execution now uses the active Python interpreter instead of assuming a `python` executable is on PATH.
- Added execution timeout handling and cleanup for temporary files.
- Added Piston request timeouts and structured compile/run output handling.
- Added `PISTON_API_KEY` support for hosted execution of JavaScript, C, C++, and Java.
- Added `PISTON_API_URL` so the project can use a self-hosted Piston instance.
- The public Piston service now requires authorization, so a Piston credential or self-hosted execution service is required for the non-Python languages. See the official Piston project documentation for current access requirements.

### Gemini updates

- Migrated from the legacy `google-generativeai` package to the current `google-genai` SDK.
- Updated the dependency requirement to `google-genai>=2.0.0`.
- Default model is now `gemini-3.5-flash-lite`.
- `GEMINI_MODEL` remains configurable through environment variables.
- Supports one Gemini key or multiple comma-separated keys through `GEMINI_API_KEYS`.
- Added failover handling for authentication, quota, rate-limit, and temporary provider errors.
- Provides a specific error message for `ACCESS_TOKEN_TYPE_UNSUPPORTED` instead of exposing confusing provider details to users.
- Gemini credentials remain backend-only and are never embedded in frontend JavaScript.

### Supabase updates

- Supabase credentials are loaded only from environment variables.
- The repository contains no real Supabase credentials.
- New deployments should use the Supabase `sb_secret_...` server-side key where available instead of the legacy `service_role` key.
- The secret key must remain on the Flask server and must never be placed in browser code.

### Security hardening

- Removed hard-coded Supabase credentials from `app.py`.
- Removed hard-coded Gemini API keys from source code.
- Removed the committed `beru.env` secrets file from the repository.
- Added `.gitignore` rules for `.env` and local secret files.
- Added `.env.example` so required configuration is documented without exposing credentials.
- Moved Google Custom Search credentials out of browser JavaScript and behind a Flask API route.
- Added configurable Gemini key rotation/failover through `GEMINI_API_KEYS`.
- Added safer startup validation for required environment variables.

> **Important:** Because credentials were previously committed to a public repository, treat those old credentials as compromised. Rotate/revoke them in their respective provider dashboards and create fresh values before deploying the updated app.

## Features

- AI academic answers powered by Google Gemini
- Gemini 3.5 Flash-Lite by default
- Explanation styles for different learning preferences
- Optional related-image search through Google Custom Search
- User signup/login with bcrypt password hashing
- Personal answer history stored in Supabase
- Delete saved answers
- Export selected answers to PDF
- Syllabus-based predicted-question generation
- Multi-language code execution page
- Responsive UI with subtle animations and accessibility-aware reduced-motion support
- Backend-only handling for secret API credentials

## Requirements

Recommended local setup:

- Python 3.11+
- pip
- A Supabase project
- A current Gemini API credential
- Optional: Google Programmable Search / Custom Search configuration for related images
- A Piston API credential for hosted JavaScript/C/C++/Java execution, or your own Piston instance

## Environment configuration

Create a local `.env` file and never commit it.

```env
SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=0

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-secret-key

GEMINI_API_KEYS=your-gemini-key-1,your-gemini-key-2
GEMINI_MODEL=gemini-3.5-flash-lite

GOOGLE_API_KEY=
SEARCH_ENGINE_ID=

PISTON_API_KEY=
PISTON_API_URL=https://emkc.org/api/v2/piston/execute
```

For the Piston credential, keep the value only in your local `.env` or Render environment settings. Never commit it to GitHub.

## Local setup

```bash
git clone https://github.com/SanFlash/Satyen78beruAI.git
cd Satyen78beruAI
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Generate a Flask secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configure the Supabase tables from `schema.sql`, then start the application:

```bash
python app.py
```

Open `http://127.0.0.1:5000`.

## Code Runner configuration

### Python

Python code runs through the server's active Python interpreter with a short execution timeout. This is suitable for a controlled/private deployment, but arbitrary code execution should **not** be exposed to untrusted public users without a real sandbox.

### JavaScript, C, C++, Java

These languages use Piston because compiled/interpreted user code should run outside the Flask process.

The current public Piston project documentation states that its public API requires authorization. If you have an authorized Piston credential, configure:

```env
PISTON_API_KEY=your-piston-credential
PISTON_API_URL=https://emkc.org/api/v2/piston/execute
```

If you do not have a public Piston credential, run your own Piston instance and point `PISTON_API_URL` to that instance instead. Do not remove the authorization requirement or expose an unprotected code execution service.

The UI sends code to:

```text
POST /run-code
```

with:

```json
{
  "language": "python",
  "code": "print('Hello')",
  "stdin": ""
}
```

The backend returns JSON containing `output`, `image`, and `exit_code` where available.

## Gemini configuration

Create/configure a current Gemini API credential in Google AI Studio and place it in `GEMINI_API_KEYS`.

Recommended model:

```env
GEMINI_MODEL=gemini-3.5-flash-lite
```

For key failover:

```env
GEMINI_API_KEYS=key_one,key_two,key_three
```

### Gemini `ACCESS_TOKEN_TYPE_UNSUPPORTED`

If the application returns this error:

1. Create a fresh current Gemini API credential.
2. Ensure it belongs to the intended Google AI Studio/Gemini API project.
3. Ensure Gemini API access is enabled for the project.
4. Put it in `GEMINI_API_KEYS`, not in frontend JavaScript.
5. Do not prefix it with `Bearer`.
6. Restart/redeploy the service after changing the environment.
7. Confirm `GEMINI_MODEL` is available to the project.

## Supabase configuration

Use a server-side Supabase secret key (`sb_secret_...`) where available. Keep it private and never put it in browser code or source control.

If an old `service_role` credential was previously exposed, rotate it in Supabase and update the deployment with the replacement credential.

## Deployment on Render

1. Create a Web Service from this repository.
2. Build command:

```bash
pip install -r requirements.txt
```

3. Start command:

```bash
gunicorn app:app
```

4. Add these environment variables in Render:

```text
SECRET_KEY
SUPABASE_URL
SUPABASE_KEY
GEMINI_API_KEYS
GEMINI_MODEL=gemini-3.5-flash-lite
PISTON_API_KEY
PISTON_API_URL
```

`GOOGLE_API_KEY` and `SEARCH_ENGINE_ID` are optional image-search settings.

5. Redeploy after environment changes.

## API routes

| Route | Method | Purpose |
|---|---|---|
| `/signup` | GET/POST | User registration |
| `/login` | GET/POST | User authentication |
| `/logout` | GET | Clear session |
| `/api/generate-answer` | POST | Generate Gemini answer |
| `/api/search-images` | GET | Server-side image search proxy |
| `/api/save-answer` | POST | Save generated answer |
| `/answers` | GET | View saved answers |
| `/delete-answer/<id>` | POST/DELETE | Delete an answer |
| `/combined-pdf` | POST | Export selected answers |
| `/predict` | POST | Generate predicted questions |
| `/run-code` | POST | Execute code |

## Security notice

Never commit API keys, passwords, session secrets, service-role tokens, secret keys, Piston credentials, or `.env` files to a public repository.

The Python code runner executes code in a server subprocess. If this application is intended for public users, replace direct server-side Python execution with a sandboxed execution service before allowing arbitrary users to run code. Python's subprocess documentation also recommends careful handling of timeouts and subprocess cleanup. 

## Troubleshooting

### Code Runner says `Unable to run code right now`

Hard refresh the browser after deployment. The current UI calls `/run-code`. If JavaScript/C/C++/Java reports that Piston is not configured, add `PISTON_API_KEY` or use your own Piston endpoint through `PISTON_API_URL`.

### Piston API authentication error

Check `PISTON_API_KEY`, `PISTON_API_URL`, and the provider's current authorization requirements. Do not put the credential in frontend JavaScript.

### Python runner error

Check Render/local logs for the Python exception. The runner now returns a readable timeout or execution error instead of hiding it behind a generic browser message.

### Gemini authentication error

Verify the Gemini credential, Google project, API access, `GEMINI_API_KEYS`, and `GEMINI_MODEL`.

### Supabase connection error

Verify `SUPABASE_URL`, `SUPABASE_KEY`, project status, and the tables in `schema.sql`.

## License

No license file is currently included. Add an explicit open-source license before distributing the project under standard open-source terms.
