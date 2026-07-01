import asyncio
import base64
import csv
import io
import json
import math
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

app = FastAPI(title="Jan Aushadi Finder API")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Local dev origins are always allowed. Production origins (e.g. the deployed
# Vercel URL) come from ALLOWED_ORIGINS in .env / the Render dashboard as a
# comma-separated list, e.g. "https://jan-aushadi-finder.vercel.app,https://janaushadi.in"
_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if not _extra_origins:
    print(
        "[CORS ⚠] ALLOWED_ORIGINS not set — only localhost is allowed. "
        "Set ALLOWED_ORIGINS on Render to your Vercel URL before going live."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

DATA_PATH = Path(__file__).parent / "data" / "medicines.json"
KENDRA_DATA_PATH = Path(__file__).parent / "data" / "kendras.json"
MAX_IMAGE_BASE64_LENGTH = 7_000_000
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
EARTH_RADIUS_KM = 6371.0

# Live Google Sheet (published as CSV) is the source of truth for Kendra data.
# Set this in server/.env. Falls back to the static kendras.json if not set.
KENDRA_SHEET_CSV_URL = os.getenv("KENDRA_SHEET_CSV_URL")
KENDRA_CACHE_TTL_SECONDS = 300  # 5 minutes
_kendra_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}


class MedicineMatchRequest(BaseModel):
    text: str | None = Field(default=None, max_length=120)
    image: str | None = Field(default=None, max_length=MAX_IMAGE_BASE64_LENGTH)
    mimeType: str | None = None


class MedicineMatchResponse(BaseModel):
    matchedName: str | None
    genericName: str | None = None
    confidence: float = 0
    source: str
    message: str | None = None
    strengths: list[str] = []
    janAushadiAvailable: bool = False
    aiGenerated: bool = False


class KendraResult(BaseModel):
    name: str
    address: str
    phone: str | None = None
    distanceKm: float


def load_medicines() -> list[dict[str, Any]]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def score_name(query: str, candidate: str) -> float:
    normalized_query = normalize(query)
    normalized_candidate = normalize(candidate)

    if not normalized_query or not normalized_candidate:
        return 0
    if normalized_query == normalized_candidate:
        return 1
    if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
        return 0.9

    return SequenceMatcher(None, normalized_query, normalized_candidate).ratio()


def find_best_match(query: str) -> MedicineMatchResponse:
    best_item: dict[str, Any] | None = None
    best_name: str | None = None
    best_score = 0.0

    for item in load_medicines():
        names = [
            *item.get("brandNames", []),
            item.get("genericName", ""),
            *item.get("aliases", []),
        ]
        for name in names:
            score = score_name(query, name)
            if score > best_score:
                best_item = item
                best_name = name
                best_score = score

    if not best_item or best_score < 0.65:
        return MedicineMatchResponse(
            matchedName=None,
            confidence=round(best_score, 2),
            source="text",
            message="No confident match found. Try typing the medicine name manually.",
        )

    return MedicineMatchResponse(
        matchedName=best_name,
        genericName=best_item["genericName"],
        confidence=round(best_score, 2),
        source="text",
        strengths=best_item.get("strengths", []),
        janAushadiAvailable=bool(best_item.get("janAushadiAvailable")),
    )


def extract_lat_lng_from_maps_url(maps_url: str) -> tuple[float, float] | None:
    """Extract latitude/longitude from a Google Maps URL.

    Handles two cases:
    1. Long URLs already containing coordinates, e.g. .../?q=22.71,75.85 or /@22.71,75.85,17z
    2. Short links like https://maps.app.goo.gl/xxxxx, which redirect to a long URL.
       We follow the redirect (without downloading the page body) and parse the
       resulting Location header.
    """
    if not maps_url:
        return None

    coord_pattern = r"(-?\d{1,3}\.\d+),\s*(-?\d{1,3}\.\d+)"

    def parse_coords(url: str) -> tuple[float, float] | None:
        match = re.search(coord_pattern, url)
        if not match:
            return None
        lat, lng = float(match.group(1)), float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
        return None

    direct = parse_coords(maps_url)
    if direct:
        return direct

    if "goo.gl" in maps_url or "maps.app.goo.gl" in maps_url:
        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(maps_url)
                final_url = str(response.url)
            return parse_coords(final_url)
        except httpx.HTTPError:
            return None

    return None


def fetch_kendras_from_sheet(csv_url: str) -> list[dict[str, Any]]:
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        response = client.get(csv_url)
        response.raise_for_status()

    reader = csv.DictReader(io.StringIO(response.text))
    kendras: list[dict[str, Any]] = []

    for row in reader:
        name = (row.get("name") or "").strip()
        address = (row.get("address") or "").strip()
        whatsapp_number = (row.get("whatsapp_number") or "").strip()
        maps_url = (row.get("maps_url") or "").strip()

        if not name or not address:
            continue

        coords = extract_lat_lng_from_maps_url(maps_url)
        if not coords:
            # Skip rows where coordinates can't be determined yet, instead of
            # crashing the whole endpoint over one bad/incomplete row.
            continue

        lat, lng = coords
        kendras.append(
            {
                "name": name,
                "address": address,
                "phone": whatsapp_number or None,
                "latitude": lat,
                "longitude": lng,
            }
        )

    return kendras


def load_kendras() -> list[dict[str, Any]]:
    now = time.time()
    if (
        _kendra_cache["data"] is not None
        and now - _kendra_cache["fetched_at"] < KENDRA_CACHE_TTL_SECONDS
    ):
        return _kendra_cache["data"]

    if KENDRA_SHEET_CSV_URL:
        try:
            kendras = fetch_kendras_from_sheet(KENDRA_SHEET_CSV_URL)
            if kendras:
                print(f"[Kendra] Loaded {len(kendras)} kendras from Google Sheet")
                _kendra_cache["data"] = kendras
                _kendra_cache["fetched_at"] = now
                return kendras
            print("[Kendra] Sheet fetch returned zero usable rows (check maps_url column)")
        except httpx.HTTPError as error:
            print(f"[Kendra] Sheet fetch failed: {error!r} — falling back to static file")
    else:
        print("[Kendra] KENDRA_SHEET_CSV_URL not set — using static file")

    if not KENDRA_DATA_PATH.exists():
        print(f"[Kendra] Fallback file also missing: {KENDRA_DATA_PATH}")
        return []

    with KENDRA_DATA_PATH.open("r", encoding="utf-8") as file:
        kendras = json.load(file)
    _kendra_cache["data"] = kendras
    _kendra_cache["fetched_at"] = now
    return kendras


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def find_nearest_kendras(lat: float, lng: float, limit: int = 3) -> list[KendraResult]:
    results: list[KendraResult] = []
    for kendra in load_kendras():
        distance = haversine_distance_km(lat, lng, kendra["latitude"], kendra["longitude"])
        results.append(
            KendraResult(
                name=kendra["name"],
                address=kendra["address"],
                phone=kendra.get("phone"),
                distanceKm=round(distance, 2),
            )
        )

    results.sort(key=lambda kendra: kendra.distanceKm)
    return results[:limit]


def clean_base64_image(image: str) -> str:
    if "," in image and image.strip().startswith("data:"):
        return image.split(",", 1)[1]
    return image


async def lookup_drug_with_ai(query: str) -> MedicineMatchResponse:
    # ── TEXT SEARCH → NaraRouter (free) ──────────────────────────────────
    api_key = os.getenv("NARAROUTER_API_KEY")
    if not api_key:
        print("[TEXT ❌] NARAROUTER_API_KEY missing — check server/.env")
        return MedicineMatchResponse(
            matchedName=None,
            confidence=0,
            source="text",
            message="No confident match found. Try typing the medicine name manually.",
        )

    model = os.getenv("NARAROUTER_TEXT_MODEL", "claude-haiku-4.5")
    base_url = os.getenv("NARAROUTER_BASE_URL", "https://router.bynara.id/v1")
    print(f"[TEXT →] NaraRouter | model={model} | query={query!r}")

    prompt = (
        "You are a pharmaceutical expert for India. "
        "Given a medicine brand name, find its exact drug composition (active ingredients with doses). "
        "For example: 'Mygrum' → 'Ergotamine Tartrate 1mg + Caffeine 100mg', "
        "'Dolo 650' → 'Paracetamol 650mg', 'Crocin' → 'Paracetamol 500mg'. "
        "Return the composition/generic drug name, not the brand name. "
        "If you are not confident, return null. "
        f'Brand name: "{query}". '
        "Respond with ONLY JSON in this exact shape, nothing else: "
        '{"generic_name": "full composition with doses, or null", '
        '"common_strengths": ["e.g. 1mg+100mg", "..."], '
        '"confidence": 0.0}'
    )

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    max_attempts = 3
    response = None
    try:
        for attempt in range(1, max_attempts + 1):
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            if response.status_code not in (429, 503):
                break

            print(f"[TEXT ⚠] NaraRouter {response.status_code} rate-limited, attempt {attempt}/{max_attempts}")
            if attempt < max_attempts:
                await asyncio.sleep(2 * attempt)
    except httpx.HTTPError as e:
        print(f"[TEXT ❌] NaraRouter network error: {e}")
        return MedicineMatchResponse(
            matchedName=None,
            confidence=0,
            source="text",
            message="No confident match found. Try typing the medicine name manually.",
        )

    if response.status_code >= 400:
        print(f"[TEXT ❌] NaraRouter HTTP {response.status_code}: {response.text[:300]}")
        fail_message = (
            "The AI model is busy right now. Please try again in a few seconds."
            if response.status_code in (429, 503)
            else f"AI lookup failed (HTTP {response.status_code}). Try typing the medicine name manually."
        )
        return MedicineMatchResponse(
            matchedName=None,
            confidence=0,
            source="text",
            message=fail_message,
        )

    data = response.json()
    output_text = None
    try:
        output_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(f"[TEXT ❌] Could not parse NaraRouter response: {data}")

    if output_text:
        output_text = output_text.strip()
        if output_text.startswith("```"):
            output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text).strip()

    try:
        parsed = json.loads(output_text) if output_text else {}
    except json.JSONDecodeError:
        print(f"[TEXT ❌] JSON parse failed: {output_text!r}")
        parsed = {}

    generic_name = parsed.get("generic_name")
    confidence = parsed.get("confidence") or 0

    print(f"[TEXT ✓] NaraRouter replied | generic_name={generic_name!r} | confidence={confidence}")

    if not generic_name or generic_name == "null" or confidence < 0.6:
        return MedicineMatchResponse(
            matchedName=None,
            confidence=round(float(confidence), 2) if confidence else 0,
            source="text",
            message="No confident match found. Try typing the medicine name manually.",
        )

    return MedicineMatchResponse(
        matchedName=query,
        genericName=str(generic_name),
        confidence=round(float(confidence), 2),
        source="text",
        strengths=[str(s) for s in parsed.get("common_strengths", [])][:6],
        janAushadiAvailable=False,
        aiGenerated=True,
        message=(
            "This match was identified by AI, not verified against the Jan "
            "Aushadi database. Please confirm with a pharmacist before buying."
        ),
    )



async def extract_medicine_name_with_gemini(image: str, mime_type: str) -> str | None:
    # ── IMAGE SEARCH → Groq (free, vision supported) ─────────────────────
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[IMAGE ❌] GROQ_API_KEY missing — check server/.env")
        return None

    image_data = clean_base64_image(image)
    try:
        base64.b64decode(image_data, validate=True)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid image data.") from error

    model = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    print(f"[IMAGE →] Groq | model={model} | mime={mime_type} | size={len(image_data)} chars")

    prompt = (
        "You are a pharmaceutical expert. Look at this medicine packaging image. "
        "1. Find the BRAND NAME printed on the box/strip (e.g. 'Mygrum', 'Dolo 650', 'Crocin'). "
        "2. From that brand name, identify the full DRUG COMPOSITION with doses "
        "(e.g. 'Ergotamine Tartrate 1mg + Caffeine 100mg', 'Paracetamol 650mg'). "
        "Return ONLY JSON, nothing else: "
        '{"brand_name": "brand name or null", '
        '"drug_composition": "full composition with doses or null", '
        '"confidence": 0.0}'
    )

    payload = {
        "model": model,
        "max_tokens": 256,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                    },
                ],
            }
        ],
    }

    max_attempts = 3
    response = None
    for attempt in range(1, max_attempts + 1):
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code not in (429, 503):
            break

        print(f"[IMAGE ⚠] Groq {response.status_code} rate-limited, attempt {attempt}/{max_attempts}")
        if attempt < max_attempts:
            await asyncio.sleep(2 * attempt)

    if response.status_code >= 400:
        print(f"[IMAGE ❌] Groq HTTP {response.status_code}: {response.text[:300]}")
        if response.status_code in (429, 503):
            raise HTTPException(
                status_code=503,
                detail="The AI model is busy right now. Please try again in a few seconds.",
            )
        raise HTTPException(status_code=502, detail="Image extraction failed.")

    data = response.json()
    output_text = None
    try:
        output_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(f"[IMAGE ❌] Could not parse Groq response: {data}")

    if not output_text:
        print("[IMAGE ❌] Groq returned empty content")
        return None

    output_text = output_text.strip()
    if output_text.startswith("```"):
        output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text).strip()

    try:
        extracted = json.loads(output_text)
    except json.JSONDecodeError:
        print(f"[IMAGE ⚠] JSON parse failed, using raw text: {output_text!r}")
        return output_text.strip()[:120] or None

    medicine_name = extracted.get("brand_name")
    drug_composition = extracted.get("drug_composition")

    if not medicine_name or medicine_name == "null":
        print(f"[IMAGE ✓] Groq replied but no brand name found | confidence={extracted.get('confidence',0)}")
        return None

    # drug_composition bhi attach karo taaki endpoint use kar sake
    result_name = medicine_name
    if drug_composition and drug_composition != "null":
        result_name = f"{medicine_name}||{drug_composition}"  # separator se dono bhejo

    print(f"[IMAGE ✓] Groq replied | brand={medicine_name!r} | drug={drug_composition!r} | confidence={extracted.get('confidence',0)}")
    return result_name


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/kendra-search", response_model=list[KendraResult])
def kendra_search(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
):
    return find_nearest_kendras(lat, lng, limit=3)


@app.post("/api/medicine-match", response_model=MedicineMatchResponse)
@limiter.limit("10/minute")
async def medicine_match(request: Request, payload: MedicineMatchRequest):

    # ── IMAGE MODE: Groq ek hi call mein brand + drug composition nikale ─
    if payload.image:
        print("[REQUEST] Mode=IMAGE — Groq will read brand name + drug composition in 1 call")
        if payload.mimeType not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPG, PNG, or WebP images are allowed.")

        groq_result = await extract_medicine_name_with_gemini(payload.image, payload.mimeType)

        if not groq_result:
            print("[REQUEST] IMAGE failed — Groq could not read medicine from photo")
            return MedicineMatchResponse(
                matchedName=None,
                confidence=0,
                source="image",
                message="Could not read medicine name from photo. Try typing the name manually.",
            )

        # Groq ne "BrandName||DrugComposition" format mein diya
        if "||" in groq_result:
            brand_name, drug_composition = groq_result.split("||", 1)
            print(f"[REQUEST] IMAGE — Groq gave both: brand={brand_name!r} drug={drug_composition!r}")
            print(f"[REQUEST] IMAGE — NaraRouter skipped (Groq already found composition) ✅")
            return MedicineMatchResponse(
                matchedName=brand_name,
                genericName=drug_composition,
                confidence=0.95,
                source="image",
                aiGenerated=True,
                message="Drug composition identified from photo by AI. Confirm with a pharmacist before buying.",
            )
        else:
            # Groq ko composition nahi mila — NaraRouter se try karo
            brand_name = groq_result
            print(f"[REQUEST] IMAGE — Groq found brand={brand_name!r} but no composition")
            print(f"[REQUEST] IMAGE — Fallback: NaraRouter will find drug composition")
            result = find_best_match(brand_name)
            if result.matchedName is None:
                result = await lookup_drug_with_ai(brand_name)
            result.source = "image"
            result.matchedName = brand_name
            print(f"[REQUEST] IMAGE fallback done — drug={result.genericName!r} confidence={result.confidence}")
            return result

    # ── TEXT MODE: sirf NaraRouter, Groq bilkul call nahi ───────────────
    query = (payload.text or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Enter a medicine name or upload a medicine photo.")

    print(f"[REQUEST] Mode=TEXT — only NaraRouter will be called (Groq skipped)")
    result = find_best_match(query)
    if result.matchedName is None:
        result = await lookup_drug_with_ai(query)
    result.source = "text"
    print(f"[REQUEST] TEXT flow done → matchedName={result.matchedName!r} confidence={result.confidence}")
    return result