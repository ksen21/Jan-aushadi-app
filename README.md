# Jan Aushadi Finder 💊

A simple web app to help people in Indore find the **generic equivalent** of a branded medicine, and locate the **nearest Jan Aushadi Kendra (PMBJP store)** to buy it from — via text search, a photo of the medicine strip/box, or manual entry.

**Live app:** [jan-aushadi-app.vercel.app](https://jan-aushadi-app.vercel.app)

> ⚠️ **Disclaimer:** This app only matches medicine names to their likely generic equivalents. It does **not** provide dosage, treatment, prescription, or substitution advice. Always confirm with a doctor or pharmacist before switching any medicine.

---

## Why this exists

Jan Aushadi Kendras sell the same medicines as branded pharmacies at a fraction of the price — but most people don't know the generic name of what they're taking, or where their nearest Kendra is. This app closes both gaps in a few taps.

## Features

- **🔍 Text search** — type a brand name (e.g. "Crocin") and get the matched generic name.
- **📷 Photo search** — upload a picture of the medicine strip/box; the app reads the name off the packaging and matches it.
- **📍 Nearby Kendra finder** — uses your location (or a manually entered area) to show the 3 closest Jan Aushadi Kendras, sorted by distance.
- **💬 WhatsApp contact** — message a Kendra directly with the medicine name pre-filled.
- **🗺️ Live Kendra data** — Kendra details are pulled from a maintained Google Sheet, not hardcoded, so new stores can be added without a redeploy.

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind CSS |
| Backend | FastAPI (Python) |
| Text matching | NaraRouter (Claude-compatible router) |
| Photo matching | Groq (Llama 4 Scout vision model) |
| Kendra data | Google Sheet (published as CSV), with a static JSON fallback |
| Hosting | Vercel (frontend) + Render (backend) |

## Project structure

```
app/                  # Next.js frontend (single-page app, view-switched)
  page.tsx            # Search, result, and Kendra list screens
  error.tsx           # Error boundary
server/
  main.py             # FastAPI app — all API endpoints
  data/
    medicines.json    # Brand -> generic name reference data
    kendras.json      # Offline fallback Kendra data
decisions.md                        # Log of architecture decisions and why they were made
jan-aushadi-finder-build-plan.md    # Original phased build plan
```

## Getting started locally

### Prerequisites
- Node.js 18+
- Python 3.11+

### 1. Clone and install
```bash
git clone https://github.com/ksen21/Jan-aushadi-app.git
cd Jan-aushadi-app
npm install
```

### 2. Set up the backend
```bash
cd server
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` -> `.env` inside `server/` and fill in:
- `NARAROUTER_API_KEY` — for text-based brand -> generic matching
- `GROQ_API_KEY` — for photo-based matching
- `KENDRA_SHEET_CSV_URL` — your published Google Sheet CSV link (optional; falls back to `data/kendras.json` if unset)

Run the backend:
```bash
uvicorn main:app --reload --port 8000
```

### 3. Set up the frontend
Copy `.env.example` -> `.env` in the repo root and set:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Run the frontend:
```bash
npm run dev
```

Visit `http://localhost:3000`.

## Kendra data sheet format

The Google Sheet (published to web as CSV) needs these columns:

| Column | Description |
|---|---|
| `name` | Kendra name |
| `address` | Full address |
| `whatsapp_number` | Contact number (with country code) |
| `maps_url` | Google Maps share link |

Coordinates are auto-extracted from `maps_url`. If a link can't be resolved to coordinates, that row is skipped (and logged) — add `latitude`/`longitude` columns directly for guaranteed reliability.

## Deployment

- **Frontend (Vercel):** import the repo, set `NEXT_PUBLIC_API_BASE_URL` to your backend URL in Environment Variables.
- **Backend (Render):** Web Service, root directory `server`, build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`. Set `NARAROUTER_API_KEY`, `GROQ_API_KEY`, `KENDRA_SHEET_CSV_URL`, and `ALLOWED_ORIGINS` (your Vercel URL) as environment variables.

See `decisions.md` for the reasoning behind these choices, and `jan-aushadi-finder-build-plan.md` for how the app was built phase by phase.

## Security notes

- No search queries or uploaded images are logged or persisted — the app is anonymous by design.
- API keys live only in environment variables, never in committed code.
- `/api/medicine-match` is rate-limited to prevent abuse.

## License

Not yet licensed — all rights reserved by the author. (Add a license here if you want this to be open source.)