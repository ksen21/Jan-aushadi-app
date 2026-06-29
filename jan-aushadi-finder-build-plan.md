# Jan Aushadi Finder — Build Plan for Codex

**Stack:** React.js / Next.js (frontend), Node.js + FastAPI (backend — FastAPI handles AI/medicine-matching logic, Node handles general API/server tasks), MongoDB (database), Vercel (deployment)

**Build philosophy:** One feature at a time, end-to-end, fully tested before moving to the next. Do not skip ahead. Do not build multiple screens in parallel.

---

## PHASE 0 — Project Setup

**Goal:** Empty but running project skeleton. No features yet.

1. Initialize Next.js app (`npx create-next-app@latest`)
2. Initialize FastAPI backend in a separate `/server` folder
3. Connect MongoDB (Atlas free tier) — create `.env` with `MONGODB_URI`
4. Create `.env` for `ANTHROPIC_API_KEY` (or whichever AI API used for image-to-medicine-name matching)
5. Add `.env` to `.gitignore`
6. Create `project-rules.md` (config file) in repo root:
   - Commands to run frontend/backend
   - Folder structure explanation
   - "Do NOT add login/signup", "Do NOT add payment processing"
7. Create `decisions.md` (empty, ready to log decisions)
8. Push empty skeleton to GitHub, connect to Vercel (confirm deploy pipeline works before writing real features)

**Test before moving on:** Does `npm run dev` start cleanly? Does FastAPI server start cleanly? Does a blank deploy succeed on Vercel?

---

## PHASE 1 — Feature: Medicine Search (Core Feature #1)

### Screen 1.1 — Home / Search Screen

**What's on this screen:**
- App title/logo ("Jan Aushadi Finder")
- One text input: "Enter medicine name"
- One upload button: "Or upload a photo of the medicine"
- One "Search" button (disabled until either text or image is provided)
- Loading spinner state (shown while waiting for match result)

**Build order for this screen:**
1. Static UI first — no logic, just layout (text input, upload button, search button)
2. Wire up text input state (React `useState`)
3. Wire up image upload (convert to base64, store in state)
4. Connect "Search" button to call backend endpoint (build endpoint next, in 1.2)
5. Add loading state while waiting for response
6. Add error state ("Couldn't find a match, try typing the name manually")

### Backend 1.2 — Medicine Matching Endpoint

**Endpoint:** `POST /api/medicine-match`

**Logic:**
1. Accept either `{ text: string }` or `{ image: base64 }`
2. If image: send to Claude API (vision) with prompt to extract medicine name from packaging
3. Take extracted/given medicine name → search against Jan Aushadi generic-name reference data
4. Return `{ matchedName, genericName, confidence }`
5. If no confident match: return `{ matchedName: null }`

**Build order:**
1. Build endpoint with hardcoded test response first (no AI call yet) — confirms frontend↔backend wiring works
2. Add real text-based matching against a static JSON of Jan Aushadi generic names (no AI yet — simple string matching)
3. Add image-based matching (Claude vision call) — only after text-based path works
4. Add confidence scoring / no-match fallback

### Screen 1.3 — Result Screen

**What's on this screen:**
- Shows matched generic name clearly
- Shows original medicine name searched
- "Find nearby Jan Aushadi Kendra" button → leads to Phase 2
- "Search again" button → back to 1.1

**Test before moving to Phase 2:**
- [ ] Type a known medicine name → correct generic name shown within 5 seconds
- [ ] Upload a clear photo → correct generic name shown within 5 seconds
- [ ] Type a nonsense/unknown name → graceful "no match" message, not a crash
- [ ] Mobile screen size — does the layout hold up?
- [ ] Git commit this feature as complete before starting Phase 2

---

## PHASE 2 — Feature: Kendra Finder (Core Feature #2)

### Data Setup 2.1 — Kendra Database

1. Create `/data/kendras.json` (or MongoDB collection `kendras`) with Indore Jan Aushadi Kendra data: `{ name, address, phone, latitude, longitude }`
2. Seed MongoDB with this data (or keep static JSON for MVP — note this choice in `decisions.md`)

### Backend 2.2 — Nearby Kendra Endpoint

**Endpoint:** `GET /api/kendra-search?lat=X&lng=Y`

**Logic:**
1. Accept user's lat/lng
2. Calculate distance to every kendra in DB (Haversine formula)
3. Return nearest 3, sorted by distance, with `{ name, address, phone, distanceKm }`

**Build order:**
1. Hardcode a fixed lat/lng first, confirm distance sorting works correctly
2. Then wire to real browser geolocation from frontend

### Screen 2.3 — Kendra List Screen

**What's on this screen:**
- Reached after Result Screen (1.3) via "Find nearby Jan Aushadi Kendra"
- Browser asks for location permission
- If permission denied → fallback manual input ("Enter your area/locality")
- List of 3 nearest kendras: name, address, distance
- Each kendra card has a WhatsApp icon/button (built in Phase 3)

**Build order:**
1. Request geolocation permission, handle granted/denied states
2. Call kendra-search endpoint with coordinates
3. Render the 3 results as cards
4. Add manual locality fallback input (only if geolocation denied)

**Test before moving to Phase 3:**
- [ ] Allow location → correct 3 nearest kendras shown, sorted correctly
- [ ] Deny location → manual input appears and still returns results
- [ ] Works on mobile browser (test actual phone, not just desktop devtools)
- [ ] Git commit this feature as complete before starting Phase 3

---

## PHASE 3 — Feature: WhatsApp Contact (Core Feature #3)

### Screen 3.1 — WhatsApp Button (added to Kendra List cards from 2.3)

**What it does:**
- Each kendra card gets a WhatsApp icon button
- Tapping it opens `wa.me/<kendra-phone>?text=<prefilled message>`
- Pre-filled message includes the medicine name from Phase 1's result

**Build order:**
1. Build the `wa.me` link generator function — test it standalone first (does the link format work when pasted in browser manually?)
2. Pass the matched medicine name from Result Screen (1.3) through to this screen (state/context, or query param)
3. Wire the button to open the link in a new tab
4. Handle missing/malformed phone numbers in kendra data gracefully (skip the button, don't crash)

**Test before moving to Phase 4:**
- [ ] Tap WhatsApp button → opens WhatsApp Web/App with correct number and pre-filled message
- [ ] Medicine name in the message matches what was searched
- [ ] Kendra with a malformed phone number doesn't break the page
- [ ] Git commit this feature as complete

---

## PHASE 4 — Security Pass (Do Not Skip)

Run this checklist across all three features before polish/deploy:

- [ ] `ANTHROPIC_API_KEY` and `MONGODB_URI` only in `.env`, never hardcoded anywhere in committed code
- [ ] `.env` confirmed in `.gitignore`, not present in any GitHub commit history
- [ ] Image upload size-limited (e.g., max 5MB) to prevent abuse and API cost spirals
- [ ] Rate-limit `/api/medicine-match` endpoint (e.g., max 10 requests/minute per IP)
- [ ] No uploaded images or search queries logged/stored anywhere (confirm no accidental persistence — app is anonymous by spec)
- [ ] Confirm no endpoint accepts arbitrary file types beyond images for the upload field

---

## PHASE 5 — Polish & Deploy (Last)

1. Mobile responsiveness pass across all 3 screens
2. Loading states / empty states reviewed for all screens
3. Basic error boundaries (what happens if backend is down?)
4. Final Vercel deploy, confirm environment variables are set in Vercel dashboard (not just local `.env`)
5. Test the full live URL end-to-end one more time: search → kendra list → WhatsApp

---

## Reminders for Codex While Building

- One phase at a time. Don't start Phase 2 code until Phase 1 is tested and committed.
- After each phase, log any non-obvious decisions in `decisions.md` (e.g., "used static JSON instead of MongoDB for kendra data because dataset is small").
- If a fix requires touching more than the file directly related to the bug, stop and ask before proceeding.
- Clear context between phases — don't carry Phase 1 debugging context into Phase 2 work.
