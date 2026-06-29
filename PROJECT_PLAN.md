# Jan Aushadi Finder - Project Plan

## 1. Product Summary

Jan Aushadi Finder helps people in Indore find affordable generic medicine alternatives and nearby Jan Aushadi Kendras where they can ask about availability.

The app is anonymous, lightweight, and focused on three tasks:

1. Identify a medicine from typed text or an uploaded photo.
2. Match it to a generic Jan Aushadi equivalent.
3. Show the nearest Jan Aushadi Kendras with a WhatsApp availability-check action.

## 2. Target Users

- People in Indore searching for cheaper generic medicine alternatives.
- Family members or caregivers checking medicine availability before visiting a store.
- Users who may know only the brand name or may only have a photo of the medicine strip or box.

## 3. Core Features

### Medicine Search

- Text input for medicine name.
- Photo upload for medicine strip or box.
- AI-assisted medicine identification from image.
- Generic drug name result.
- Clear disclaimer that the app does not provide dosage, substitution, or medical advice.

### Generic Equivalent Matching

- Match identified medicine to its generic drug name.
- Return Jan Aushadi equivalent when available.
- Show confidence or "needs confirmation" state when the match is uncertain.
- Encourage users to confirm with a pharmacist or doctor where appropriate.

### Kendra Finder

- Request device location permission.
- Sort Jan Aushadi Kendras nearest-to-farthest.
- Show the top 3 Kendras.
- Include:
  - Kendra name
  - Address
  - Distance from user
  - WhatsApp availability-check button

### WhatsApp Availability Check

- WhatsApp button opens a pre-filled message.
- Message includes the medicine or generic name.
- Example:

```text
Namaste, I want to check availability of [medicine name / generic name] at your Jan Aushadi Kendra. Please confirm if it is available.
```

### Location Fallback

- If location permission is denied or unavailable:
  - Ask user to enter city/area manually.
  - Default city should be Indore.
  - Sort Kendras by best available area match or show known Indore Kendras.

## 4. Out of Scope

- No direct medicine sales.
- No payments.
- No user login or signup.
- No prescriptions or dosage guidance.
- No real-time stock guarantee.
- No replacement for doctor or pharmacist advice.

## 5. Primary User Flow

1. User opens the app.
2. User enters a medicine name or uploads a photo.
3. App identifies the medicine.
4. App shows the generic equivalent.
5. App asks for device location.
6. App lists the 3 nearest Jan Aushadi Kendras.
7. User taps WhatsApp next to a Kendra.
8. WhatsApp opens with a pre-filled availability-check message.

## 6. Error and Edge Cases

- Medicine not recognized:
  - Ask user to try another spelling or upload a clearer photo.
- Low-confidence image result:
  - Show possible match and ask user to confirm.
- No generic equivalent found:
  - Show "No Jan Aushadi equivalent found yet" and allow another search.
- Location denied:
  - Show manual area input.
- No WhatsApp number available:
  - Hide WhatsApp button or show phone/contact unavailable state.
- User is offline:
  - Show a friendly message and allow retry.

## 7. Data Requirements

### Medicine Data

- Brand medicine name.
- Generic drug name.
- Strength/form where available.
- Jan Aushadi equivalent availability.
- Source or last verified date.

### Kendra Data

- Kendra name.
- Address.
- Latitude and longitude.
- WhatsApp phone number.
- Area/locality.
- Last verified date.

## 8. Technical Approach

### Frontend

- Mobile-first web app.
- Anonymous access.
- Simple home screen with text search and photo upload.
- Results screen with generic equivalent and nearby Kendra list.

### AI / OCR

- Use image recognition or OCR to read medicine strip/box text.
- Extract likely brand or drug name.
- Match extracted text against medicine database.

### Location

- Use browser/device geolocation where permitted.
- Calculate distance using latitude and longitude.
- Fallback to manual area input.

### WhatsApp

- Use WhatsApp deep links:

```text
https://wa.me/[phone_number]?text=[encoded_message]
```

## 9. MVP Milestones

### Milestone 1 - Static Prototype

- Build the main screens.
- Support typed medicine search.
- Use sample medicine and Kendra data.
- Show top 3 Kendras.
- Generate WhatsApp links.

### Milestone 2 - Location Sorting

- Add geolocation permission request.
- Sort Kendras by distance.
- Add manual area fallback.

### Milestone 3 - Photo Upload

- Add photo upload.
- Add OCR or AI-based medicine text extraction.
- Connect extracted name to generic matching.

### Milestone 4 - Data Verification

- Expand Indore Kendra list.
- Add verified WhatsApp numbers.
- Add medicine mapping source and last verified date.

### Milestone 5 - Safety and Polish

- Add clear medical disclaimer.
- Improve uncertain-match handling.
- Test mobile usability.
- Optimize image result time.

## 10. Success Criteria

- Photo upload returns a generic-name match within 5 seconds for common medicine packaging.
- Kendra list is sorted nearest-to-farthest using device location.
- WhatsApp button opens WhatsApp with the correct Kendra number.
- Pre-filled WhatsApp message includes the medicine or generic name.
- App still works when location permission is denied by using manual city/area input.
- No login is required.
- No medical or dosage advice is shown.

## 11. Key Risks

- Medicine identification from photos may be unreliable if packaging is blurry or partially visible.
- Generic substitution can be medically sensitive and must be framed carefully.
- Kendra phone/WhatsApp data may become outdated.
- Real-time stock availability cannot be guaranteed without Kendra-side integration.

## 12. Recommended MVP Dataset

Start with a small verified Indore-only dataset:

- 20-50 commonly searched medicines.
- 10-20 Jan Aushadi Kendras in Indore.
- Verified address, coordinates, and WhatsApp numbers.

This keeps the first version useful while making data quality manageable.

