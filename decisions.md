# Decisions Log

## 2026-06-24

Decision: Use static JSON for Kendra data initially, not a full database.

Reason: The MVP only needs around 50-100 Indore Kendras, so static JSON keeps the app simple and fast to ship. PostgreSQL or another database can be added later if the dataset grows, admin editing is needed, or real-time updates become important.

## 2026-06-24

Decision: Build the app in feature order: text medicine search first, then photo recognition, then location sorting, then WhatsApp contact.

Reason: Text search validates the core medicine-matching logic before adding OCR or AI image complexity. Once the matching logic works, photo upload can feed into the same flow, and Kendra/WhatsApp features can be added around a stable result.

## 2026-06-24

Decision: Use Claude API only to extract the likely medicine name from uploaded packaging images, then use the app's own medicine database for the generic equivalent match.

Reason: This keeps medical matching controlled by verified project data instead of relying on the model to decide substitutions. It also makes confidence handling and future database upgrades easier.

## 2026-06-24

Decision: Support OpenAI API keys for medicine image extraction instead of hard-coding the feature to Claude.

Reason: The image extraction step should be provider-flexible. For this phase, the backend reads `OPENAI_API_KEY` and uses OpenAI vision input when a medicine photo is uploaded; the verified generic 
match still comes from the project medicine data.

## 2026-06-28

Decision: Switched Kendra data source from static kendras.json to a live Google Sheet (published as CSV via "Publish to web") read at request time, with kendras.json kept only as an offline fallback.

Reason: The user maintains real, verified kendra data (name, address, WhatsApp number, Google Maps share link) directly in a Google Sheet and wants new entries to be picked up automatically without redeploying or editing JSON. The backend reads KENDRA_SHEET_CSV_URL from .env, parses each row, and extracts latitude/longitude from the Google Maps URL column (handles both long URLs with coordinates already in them and short maps.app.goo.gl links by following the redirect). Results are cached in memory for 5 minutes to avoid hitting Google on every request. If the sheet is unreachable or the URL isn't set, the app falls back to the static kendras.json so the endpoint never goes fully down.

## 2026-06-28

Decision: Built the Kendra List screen (Phase 2.3) as a view-switch inside the existing single-page app (`app/page.tsx`), not a separate route.

Reason: Consistent with how Phase 1's Result Screen was already built (same page, state-driven view, not Next.js routing). Added a "Find nearby Jan Aushadi Kendra" button to the medicine match result, which requests browser geolocation; on denial, a manual locality input maps a small set of known Indore area names to approximate coordinates so the kendra-search endpoint still gets a usable lat/lng. Also added the WhatsApp link-generator function here (`buildWhatsAppLink`) since it's needed to render each kendra card's contact button — this gets the core Phase 3 logic in place early, but the dedicated Phase 3 testing pass (malformed numbers, full WhatsApp flow) is still pending.


## 2026-06-28

Decision: Added an AI fallback (lookup_drug_with_ai, OpenAI text model) for brand names that don't match anything in the static medicines.json list — e.g. "Itracip 100" → "Itraconazole" with strengths like 100mg/200mg.

Reason: The static list only covers a handful of pre-verified medicines and can never cover every Indian brand name. The static list is still checked first (fast, pre-verified, marked janAushadiAvailable accurately); the AI is only consulted on a miss. To control hallucination risk on medical data: the AI is prompted to return null rather than guess if unsure, results below 0.6 confidence are rejected outright, and any AI-sourced result is tagged aiGenerated: true with janAushadiAvailable forced to false (unknown, not verified) and a message telling the user to confirm with a pharmacist. The frontend shows a distinct amber warning box for AI-sourced matches so they're visually different from verified Jan Aushadi matches. The same fallback applies to both the text path and the image path, since image search already funnels into find_best_match via the extracted name.

## 2026-06-28

Decision: Ran Phase 4 (Security Pass) against the build plan checklist. Added rate limiting (slowapi, 10 requests/minute per IP) to POST /api/medicine-match, the one item that was missing.

Reason: This endpoint now calls a paid OpenAI API on cache misses (both for image extraction and the AI drug-name fallback), so an unlimited endpoint risks an unexpected bill if hit repeatedly by a script or bot. Verified with a real 12-request burst test: requests 1-10 returned 200, requests 11-12 returned 429 as expected. All other checklist items were verified directly against the codebase and passed without changes: no hardcoded API keys (checked via grep + git history for .env), .env* correctly gitignored except .env.example, image size capped at 5MB on both frontend and backend, no logging or persistence of uploaded images or search text anywhere in the code, and the image MIME type allow-list is enforced server-side (not just in the frontend file picker), so it can't be bypassed by calling the API directly

2026-06-29

Decision: Switched both AI integrations (text-based generic-name lookup in lookup_drug_with_ai, and image-based medicine-name extraction in extract_medicine_name_with_gemini) from OpenAI to Google's Gemini API (gemini-3.5-flash, REST via generateContent).

Reason: The user wants to use a free-tier AI provider rather than paid OpenAI/Anthropic credits. Both functions now read GEMINI_API_KEY from .env, call https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent with x-goog-api-key auth, and use generationConfig.responseMimeType: "application/json" to keep structured-output parsing reliable (same approach used previously with OpenAI's JSON mode). All existing safety behavior is preserved: confidence threshold of 0.6 for the text fallback, aiGenerated: true tagging, janAushadiAvailable forced to false for AI-sourced matches, and debug print statements on every failure path (missing key, HTTP error, empty/unparseable model output) so future issues are visible in the server console instead of silently returning "no match."