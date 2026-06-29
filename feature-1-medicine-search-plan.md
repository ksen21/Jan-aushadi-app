# Feature 1 Plan: Medicine Search

## Goal

Let users identify a medicine by either typing its name or uploading a photo of the strip/box, then return the likely Jan Aushadi generic equivalent with a confidence score.

## User Flow

1. User opens the medicine search screen.
2. User either:
   - Types a medicine name, or
   - Uploads a medicine strip/box photo.
3. If a photo is uploaded, the frontend converts the image to base64 and sends it to the backend.
4. Backend calls an AI vision API with the image and asks it to extract the medicine name from the packaging.
5. Backend normalizes the extracted or typed name.
6. Backend searches the medicine database.
7. Backend returns the best match with confidence.
8. Frontend shows:
   - Identified medicine name
   - Generic name
   - Match confidence
   - Safety note
9. If there is no confident match, frontend shows:
   - "No confident match found. Try typing the medicine name manually."

## Frontend Requirements

- Text input for medicine name.
- Image upload input for strip/box photo.
- Search button.
- Loading state while image is processed.
- Result state for successful match.
- Low-confidence/no-match state.
- Error state for upload/API failure.

## Backend Requirements

### Image Endpoint

Suggested endpoint:

```text
POST /api/medicine/identify-image
```

Request body:

```json
{
  "imageBase64": "...",
  "mimeType": "image/jpeg"
}
```

Response body:

```json
{
  "extractedName": "Crocin",
  "genericName": "Paracetamol",
  "confidence": 0.88,
  "source": "image"
}
```

### Text Endpoint

Suggested endpoint:

```text
POST /api/medicine/search
```

Request body:

```json
{
  "query": "Crocin"
}
```

Response body:

```json
{
  "matchedName": "Crocin",
  "genericName": "Paracetamol",
  "confidence": 0.94,
  "source": "text"
}
```

## AI Image Extraction

The backend should send the uploaded image to the configured AI provider with a narrow extraction prompt:

```text
Extract only the likely medicine brand name or drug name from this medicine packaging image.
Do not provide dosage advice.
Return JSON with:
- medicine_name
- visible_strength
- confidence
- notes
If unreadable, return medicine_name as null.
```

The app should treat the model output as an extraction step only. The generic equivalent must come from the app's medicine database, not directly from the model.

Current implementation supports OpenAI vision extraction through `OPENAI_API_KEY`.

## Medicine Matching

Use the same matching function for both typed input and image-extracted names.

Matching should check:

- Exact brand name.
- Exact generic name.
- Aliases.
- Case-insensitive normalized text.
- Fuzzy match for spelling differences.

Recommended confidence behavior:

- `0.85+`: show confident match.
- `0.65-0.84`: show possible match and ask user to confirm.
- Below `0.65`: show no confident match and suggest manual typing.

## Data Source

Start with static JSON for MVP:

```text
data/medicines.json
```

Example shape:

```json
[
  {
    "brandNames": ["Crocin", "Calpol"],
    "genericName": "Paracetamol",
    "strengths": ["500mg", "650mg"],
    "aliases": ["Acetaminophen"],
    "janAushadiAvailable": true,
    "lastVerified": "2026-06-24"
  }
]
```

Postgres can be added later if medicine data needs admin editing, audit history, or frequent updates.

## Validation and Safety

- Limit image uploads by file type and size.
- Accept only common image MIME types:
  - `image/jpeg`
  - `image/png`
  - `image/webp`
- Store Claude API key only in environment variables.
- Do not expose API keys in frontend code.
- Do not store user images for MVP.
- Show a disclaimer that results are for generic-name matching only, not medical advice.

## Acceptance Criteria

- User can search by typing a medicine name.
- User can upload a medicine image.
- Image is sent to backend as base64.
- Backend extracts likely medicine name using Claude API.
- Extracted name is matched against medicine data.
- Frontend shows generic name and confidence score.
- No confident match shows a manual typing fallback.
- No dosage, substitution, or treatment advice is displayed.
