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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    with httpx.Client(timeout=15) as client:
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
                _kendra_cache["data"] = kendras
                _kendra_cache["fetched_at"] = now
                return kendras
        except httpx.HTTPError:
            # Sheet unreachable this request — fall through to static backup below.
            pass

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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[AI lookup] GEMINI_API_KEY not found in environment — check server/.env")
        return MedicineMatchResponse(
            matchedName=None,
            confidence=0,
            source="text",
            message="No confident match found. Try typing the medicine name manually.",
        )

    print(f"[AI lookup] Calling Gemini for query={query!r}")

    model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash")
    prompt = (
        "You are identifying the generic (active ingredient) name "
        "for a medicine brand name sold in India, for an app that "
        "helps people find cheaper generic alternatives. "
        "Do not give dosage, treatment, or safety advice. "
        f'Brand name: "{query}". '
        "If you are not confident about the generic name, return "
        "null instead of guessing. "
        "Respond with ONLY JSON in this exact shape: "
        '{"generic_name": "name or null", '
        '"common_strengths": ["e.g. 100mg", "..."], '
        '"confidence": 0.0}'
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError:
        return MedicineMatchResponse(
            matchedName=None,
            confidence=0,
            source="text",
            message="No confident match found. Try typing the medicine name manually.",
        )

    if response.status_code >= 400:
        print(f"[AI lookup] Gemini error {response.status_code}: {response.text[:500]}")
        return MedicineMatchResponse(
            matchedName=None,
            confidence=0,
            source="text",
            message=f"AI lookup failed (HTTP {response.status_code}). Try typing the medicine name manually.",
        )

    data = response.json()
    output_text = None
    try:
        output_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        print(f"[AI lookup] Could not extract text from Gemini response: {data}")

    try:
        parsed = json.loads(output_text) if output_text else {}
    except json.JSONDecodeError:
        print(f"[AI lookup] JSON parse failed on model output: {output_text!r}")
        parsed = {}

    generic_name = parsed.get("generic_name")
    confidence = parsed.get("confidence") or 0

    print(f"[AI lookup] query={query!r} -> generic_name={generic_name!r} confidence={confidence}")

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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Image lookup] GEMINI_API_KEY not found in environment — check server/.env")
        return None

    image_data = clean_base64_image(image)
    try:
        base64.b64decode(image_data, validate=True)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid image data.") from error

    model = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash")
    prompt = (
        "Extract only the likely medicine brand name or drug name "
        "from this medicine packaging image. Do not provide dosage "
        "or medical advice. Return only JSON like "
        '{"medicine_name":"name or null","confidence":0.0}.'
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_data}},
                ]
            }
        ],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        print(f"[Image lookup] Gemini error {response.status_code}: {response.text[:500]}")
        raise HTTPException(status_code=502, detail="Image extraction failed.")

    data = response.json()
    output_text = None
    try:
        output_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        print(f"[Image lookup] Could not extract text from Gemini response: {data}")

    if not output_text:
        return None

    try:
        extracted = json.loads(output_text)
    except json.JSONDecodeError:
        return output_text.strip()[:120] or None

    medicine_name = extracted.get("medicine_name")
    if not medicine_name or medicine_name == "null":
        return None
    return str(medicine_name)


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
    query = (payload.text or "").strip()
    source = "text"

    if payload.image:
        if payload.mimeType not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPG, PNG, or WebP images are allowed.")
        extracted_name = await extract_medicine_name_with_gemini(payload.image, payload.mimeType)
        if not extracted_name:
            return MedicineMatchResponse(
                matchedName=None,
                confidence=0,
                source="image",
                message="No confident match found. Try typing the medicine name manually.",
            )
        query = extracted_name
        source = "image"

    if not query:
        raise HTTPException(status_code=400, detail="Enter a medicine name or upload a medicine photo.")

    result = find_best_match(query)
    if result.matchedName is None:
        # Static Jan Aushadi list didn't have a confident match — ask the AI
        # to identify the generic name instead of giving up.
        result = await lookup_drug_with_ai(query)

    result.source = source
    return result