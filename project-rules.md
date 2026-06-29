# Project Rules

## Commands

Frontend:

```bash
npm run dev
```

Backend:

```bash
cd server
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --reload
```

## Folder Structure

- `app/` - Next.js frontend app.
- `public/` - Static frontend assets.
- `server/` - FastAPI backend for AI extraction, medicine matching, and future API logic.
- `server/requirements.txt` - Python backend dependencies.
- `PROJECT_PLAN.md` - Product spec and project plan.
- `implementation-plan.md` - Overall implementation sequence.
- `feature-1-medicine-search-plan.md` - Pre-coding plan for medicine search.
- `jan-aushadi-finder-build-plan.md` - Phase-by-phase build plan.
- `decisions.md` - Decision log for technical/product choices.

## Non-Negotiables

- Do NOT add login or signup.
- Do NOT add payment processing.
- Do NOT sell medicines directly.
- Do NOT provide dosage, prescription, treatment, or substitution advice.
- Do NOT expose API keys in frontend code.
- Do NOT commit real `.env` secrets.
- Keep the app anonymous for MVP.
- Use `OPENAI_API_KEY` on the backend for image extraction when using ChatGPT/OpenAI APIs.

## Build Process

- Build one phase at a time.
- Finish and test the current phase before starting the next.
- Ask the user for confirmation before moving to the next phase.
- Log non-obvious technical decisions in `decisions.md`.
