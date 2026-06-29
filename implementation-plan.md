# Implementation Plan

## Current Status

1. Spec - done in `PROJECT_PLAN.md`.
2. Config file - done above.
3. Plan review - this document.
4. Feature 1: Medicine Search - next.
5. Feature 2: Kendra Finder - after medicine search works end-to-end.
6. Feature 3: WhatsApp Contact - after Kendra cards exist.
7. Security pass - before deploy.
8. Polish and deploy - final stage.

## Recommended Build Order

### Step 1 - App Foundation

Create a mobile-first web app with these screens and states:

- Search area with medicine text input.
- Photo upload control.
- Generic match result panel.
- Kendra results list.
- Location denied/manual area fallback.
- Safety disclaimer.

Acceptance check:

- User can open the app and search using sample local data without any external API.

### Step 2 - Static Data Files

Use local JSON files for:

- Medicine mappings.
- Indore Jan Aushadi Kendra list.

Suggested files:

- `data/medicines.json`
- `data/kendras.json`

Acceptance check:

- Text search can match at least a few sample brand names to generic names.
- Kendra cards can render from JSON.

### Step 3 - Feature 1: Medicine Search

Build end-to-end text search first:

- Normalize user input.
- Match against brand name, generic name, and aliases.
- Show generic name, form/strength where available, and confidence state.

Then add photo input:

- Accept image upload.
- Extract text using OCR or an AI vision API.
- Reuse the same matching function used by text search.

Acceptance check:

- Typed medicine search returns a generic match.
- Uploaded photo returns a likely match within 5 seconds for clear packaging.
- No dosage or medical advice appears.

Detailed plan: see `feature-1-medicine-search-plan.md`.

### Step 4 - Feature 2: Kendra Finder

Implement Kendra discovery:

- Request device location.
- Calculate distance from user to each Kendra.
- Sort nearest-to-farthest.
- Show the nearest 3.
- If permission is denied, show manual area input.

Acceptance check:

- With location permission, results sort by distance.
- Without location permission, manual area fallback still shows useful Indore results.

### Step 5 - Feature 3: WhatsApp Contact

Add tap-to-message behavior:

- Each Kendra card gets a WhatsApp button if a number is available.
- Generate a `wa.me` link with encoded text.
- Include the searched medicine and generic name in the message.

Acceptance check:

- Button opens WhatsApp or WhatsApp Web.
- Message contains the right medicine name.
- Kendra phone number is formatted correctly for India.

### Step 6 - Security Pass

Review the app before deployment:

- Move API keys to environment variables.
- Do not expose private keys in frontend code.
- Validate text input length and image file type/size.
- Do not store personal location data.
- Keep the app anonymous.

Acceptance check:

- No secrets are committed.
- Uploads are restricted to safe image types and reasonable size limits.
- Location is used only for sorting and not stored.

### Step 7 - Polish and Deploy

Finish the user experience:

- Improve mobile layout.
- Add loading, error, empty, and low-confidence states.
- Verify WhatsApp links on mobile.
- Deploy to Vercel or GitHub Pages depending on the final stack.

Acceptance check:

- App works on mobile and desktop.
- Main flow is clear without signup.
- Deployment link opens successfully.

## Suggested MVP Tech Stack

Use a simple static-first frontend unless image recognition needs a server:

- Vite + React for the app.
- Static JSON for medicine and Kendra data.
- Browser geolocation for distance sorting.
- WhatsApp `wa.me` links for contact.
- Optional serverless function for AI/OCR if using an API key.

## Important Implementation Notes

- Keep medicine matching separate from the UI so text input and photo OCR use the same logic.
- Treat photo recognition as uncertain unless confidence is high.
- Never present a match as medical advice.
- Show "confirm with pharmacist or doctor" near generic substitutions.
- Keep Kendra stock availability manual through WhatsApp for MVP.
