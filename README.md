# Satyen78AI

> **Learn faster. Ask clearly. Get visual study-ready answers.**

Satyen78AI is a Flask-based academic AI web app designed to help students understand topics quickly. Users can enter a topic and question, choose an explanation style such as Easy, Hinglish, or Professional, and receive an AI-generated answer with optional related images. The app also includes authentication, saved answers, PDF export, syllabus-based question generation, and a code-running page.

## Latest release updates

This release focuses on **Gemini reliability, current API compatibility, security, and deployment readiness without changing the core product layout**.

### Gemini updates

- Migrated from the legacy `google-generativeai` package to the current `google-genai` SDK.
- Updated the dependency requirement to `google-genai>=2.0.0`.
- Default model is now `gemini-3.5-flash-lite`.
- `GEMINI_MODEL` remains configurable through environment variables.
- Supports one Gemini key or multiple comma-separated keys through `GEMINI_API_KEYS`.
- Added failover handling for authentication, quota, rate-limit, and temporary provider errors.
- Provides a specific error message for `ACCESS_TOKEN_TYPE_UNSUPPORTED` instead of exposing confusing provider details to users.
- Gemini credentials remain backend-only and are never embedded in frontend JavaScript.

Google currently documents `gemini-3.5-flash-lite` as an available Gemini 3 model. The project uses the Generate Content API through the current Google GenAI SDK. Verify model availability and project access in Google AI Studio when deploying.

### Supabase updates

- Supabase credentials are loaded only from environment variables.
- The repository contains no real Supabase credentials.
- New deployments should use the Supabase `sb_secret_...` server-side key where available instead of the legacy `service_role` key.
- The secret key must remain on the Flask server and must never be placed in browser code.

Supabase is deprecating the legacy `anon` and `service_role` keys in favor of publishable and secret keys during 2026. Existing projects can migrate incrementally.

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
- Code execution page
- Responsive UI with subtle animations and accessibility-aware reduced-motion support
- Backend-only handling for secret API credentials

## Project structure

```text
Satyen78beruAI/
├── app.py
├── code_run.py
├── download.py
├── download_utils.py
├── models.py
├── schema.sql
├── requirements.txt
├── Procfile
├── .env.example
├── .gitignore
├── static/
│   ├── Background.png
│   ├── background.png
│   ├── Satyen78AI_Logo.png
│   ├── script.js
│   └── style.css
└── templates/
    ├── index.html
    ├── answers.html
    ├── login.html
    ├── signup.html
    └── predict.html
```

## Requirements

Recommended local setup:

- Python 3.11+
- pip
- A Supabase project
- A current Gemini API credential
- Optional: Google Programmable Search / Custom Search configuration for related images

The application is a Flask app and can run locally or behind a production WSGI server such as Gunicorn.

## 1. Clone the repository

```bash
git clone https://github.com/SanFlash/Satyen78beruAI.git
cd Satyen78beruAI
```

## 2. Create a virtual environment

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a local `.env` file in the project root. **Do not commit it.** Use `.env.example` as the template.

```env
SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=0

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-secret-key

# One key or multiple comma-separated Gemini keys.
GEMINI_API_KEYS=your-gemini-key-1,your-gemini-key-2
GEMINI_MODEL=gemini-3.5-flash-lite

# Optional related-image search.
GOOGLE_API_KEY=
SEARCH_ENGINE_ID=
```

### Generating a Flask secret

A secure random value can be generated with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into `SECRET_KEY`.

## 5. Configure Supabase

Create the database tables expected by the application using the SQL in `schema.sql`.

For a server-side Flask deployment, use a Supabase secret key (`sb_secret_...`) when your project has the new API keys available. Keep it private and never place it in frontend JavaScript or source control.

If your project still uses a legacy `service_role` key, it can work during migration, but replace it with a new secret key and retire the legacy credential after confirming the application works.

## 6. Configure Gemini

Create/configure a current Gemini API credential in Google AI Studio and place it in `GEMINI_API_KEYS`.

The recommended project configuration is:

```env
GEMINI_MODEL=gemini-3.5-flash-lite
```

For key failover, provide multiple keys separated by commas:

```env
GEMINI_API_KEYS=key_one,key_two,key_three
```

The backend attempts configured keys in order when a retryable authentication, quota, rate-limit, or temporary provider failure occurs.

### Gemini `ACCESS_TOKEN_TYPE_UNSUPPORTED`

If the application returns:

```text
ACCESS_TOKEN_TYPE_UNSUPPORTED
```

check the following before changing application code:

1. The credential is a current Gemini API credential, not an unrelated OAuth access token.
2. The credential belongs to the intended Google AI Studio/Gemini API project.
3. The Gemini API is enabled for that project.
4. `GEMINI_API_KEYS` contains the credential without extra quotes or accidental spaces.
5. `GEMINI_MODEL` is a model available to that project.
6. The deployment has been restarted after changing environment variables.

Do not put a Gemini credential in frontend JavaScript or commit it to GitHub.

## 7. Optional image search

Related images are optional. When `GOOGLE_API_KEY` and `SEARCH_ENGINE_ID` are both configured, the frontend calls the Flask route `/api/search-images` and the server communicates with Google Custom Search.

When they are blank, AI answer generation still works and image search is simply skipped.

## 8. Run locally

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

For local debugging, set:

```env
FLASK_DEBUG=1
```

For normal operation, keep `FLASK_DEBUG=0`.

## Deployment on Render

1. Create a new **Web Service** from this GitHub repository.
2. Set the build command to:

```bash
pip install -r requirements.txt
```

3. Set the start command to:

```bash
gunicorn app:app
```

4. Add the environment variables from `.env.example` in Render's Environment settings.
5. Set `GEMINI_MODEL=gemini-3.5-flash-lite`.
6. Add the Gemini credential as `GEMINI_API_KEYS`.
7. Add the Supabase project URL and server-side secret as `SUPABASE_URL` and `SUPABASE_KEY`.
8. Do not upload `.env` or secret values to GitHub.
9. Deploy and test signup, login, answer generation, history, PDF export, and optional image search.

## Secret rotation checklist

If an API key has ever been committed to GitHub, rotating the key is not optional. Remove the old value from the application configuration, revoke/rotate it at the provider, then add the new value through environment variables.

For Supabase, create a new secret key, update the deployment, verify all components work, and then retire the compromised legacy `service_role` key.

Changing `.env` locally or adding a new environment variable does **not** automatically revoke an already exposed provider key. The provider dashboard is where the old credential must be disabled.

## Recommended production practices

- Keep `FLASK_DEBUG=0` in production.
- Use a strong, unique `SECRET_KEY`.
- Store secrets only in the deployment platform's encrypted environment-variable store.
- Keep Supabase secret keys strictly server-side.
- Review Supabase Row Level Security policies before exposing the application publicly.
- Add rate limiting before opening the AI endpoint to heavy anonymous traffic.
- Consider a database-backed or Redis-backed session store for multi-instance deployments.
- Rotate credentials immediately after accidental exposure.

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
| `/run-code` | POST | Run code |

## UI improvements

The original visual direction is preserved while improving:

- Softer cards, borders, and shadows
- More consistent spacing and rounded controls
- Better focus states for keyboard users
- Smoother answer reveal and loading feedback
- Responsive image-result cards
- Mobile-friendly sizing
- Reduced-motion handling for users who request less animation
- Cleaner error presentation

## Troubleshooting

### `Missing required environment variable`

Check that the variable exists in `.env` locally or in the deployment environment.

### Gemini returns `ACCESS_TOKEN_TYPE_UNSUPPORTED`

This is an authentication/credential-type problem rather than a Supabase database problem. Verify the Gemini credential, Google project, API access, environment variable name, and deployment restart. The app uses `google-genai` and sends the configured API key through the SDK.

### Gemini model not found

Verify that `GEMINI_MODEL` matches a model available to the configured Google project. The current default is:

```env
GEMINI_MODEL=gemini-3.5-flash-lite
```

### Image search is empty

Confirm both `GOOGLE_API_KEY` and `SEARCH_ENGINE_ID` are configured. Image search is intentionally optional.

### Supabase connection fails

Verify `SUPABASE_URL`, `SUPABASE_KEY`, the project status, and that the tables in `schema.sql` exist. For new Supabase projects, prefer the server-side `sb_secret_...` key.

## Security notice

Never commit API keys, passwords, session secrets, service-role tokens, secret keys, or `.env` files to a public repository.

Because this project previously contained credential literals in tracked files, review your provider dashboards and rotate any previously exposed credentials before relying on this release.

## License

No license file is currently included. Add an explicit open-source license before distributing the project under standard open-source terms.
