"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

type MatchResult = {
  matchedName: string | null;
  genericName?: string | null;
  confidence: number;
  source: "text" | "image";
  message?: string | null;
  strengths: string[];
  janAushadiAvailable: boolean;
  aiGenerated?: boolean;
};

type KendraResult = {
  name: string;
  address: string;
  phone: string | null;
  distanceKm: number;
};

type View = "search" | "kendras";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

const INDORE_LOCALITY_COORDS: Record<string, { lat: number; lng: number }> = {
  "vijay nagar": { lat: 22.7531, lng: 75.8937 },
  "rajwada": { lat: 22.7177, lng: 75.8557 },
  "mg road": { lat: 22.7211, lng: 75.865 },
  "rajendra nagar": { lat: 22.7308, lng: 75.9012 },
  "bhawarkua": { lat: 22.6967, lng: 75.865 },
  "sudama nagar": { lat: 22.689, lng: 75.85 },
  "annapurna": { lat: 22.6985, lng: 75.8392 },
  "khajrana": { lat: 22.7445, lng: 75.8862 },
  "palasia": { lat: 22.7244, lng: 75.8839 },
  "bengali square": { lat: 22.7536, lng: 75.912 },
};

function resolveManualLocality(input: string): { lat: number; lng: number } | null {
  const normalized = input.trim().toLowerCase();
  if (!normalized) return null;

  for (const [key, coords] of Object.entries(INDORE_LOCALITY_COORDS)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return coords;
    }
  }
  return { lat: 22.7196, lng: 75.8577 };
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read image."));
    reader.readAsDataURL(file);
  });
}

export default function Home() {
  const [medicineName, setMedicineName] = useState("");
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imageName, setImageName] = useState("");
  const [mimeType, setMimeType] = useState<string | null>(null);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const [view, setView] = useState<View>("search");
  const [kendras, setKendras] = useState<KendraResult[]>([]);
  const [kendraError, setKendraError] = useState("");
  const [isLoadingKendras, setIsLoadingKendras] = useState(false);
  const [locationDenied, setLocationDenied] = useState(false);
  const [manualLocality, setManualLocality] = useState("");

  const canSearch = useMemo(
    () => Boolean(medicineName.trim() || imageBase64),
    [medicineName, imageBase64],
  );

  async function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    setError("");
    setResult(null);
    const file = event.target.files?.[0];
    if (!file) {
      setImageBase64(null);
      setImageName("");
      setMimeType(null);
      return;
    }

    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Please upload a JPG, PNG, or WebP medicine photo.");
      event.target.value = "";
      return;
    }

    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      setError("Image is too large. Please upload an image below 5MB.");
      event.target.value = "";
      return;
    }

    const dataUrl = await readFileAsDataUrl(file);
    setImageBase64(dataUrl);
    setImageName(file.name);
    setMimeType(file.type);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSearch) return;

    setIsLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/medicine-match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: medicineName.trim() || undefined,
          image: imageBase64 || undefined,
          mimeType: mimeType || undefined,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not find a match.");
      }
      setResult(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not find a match. Try typing the name manually.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  function resetSearch() {
    setMedicineName("");
    setImageBase64(null);
    setImageName("");
    setMimeType(null);
    setResult(null);
    setError("");
    setView("search");
  }

  async function fetchKendras(lat: number, lng: number) {
    setIsLoadingKendras(true);
    setKendraError("");
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/kendra-search?lat=${lat}&lng=${lng}`,
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Could not find nearby kendras.");
      }
      setKendras(data);
    } catch (requestError) {
      setKendraError(
        requestError instanceof Error
          ? requestError.message
          : "Could not find nearby kendras. Try entering your area instead.",
      );
    } finally {
      setIsLoadingKendras(false);
    }
  }

  function handleFindKendras() {
    setView("kendras");
    setLocationDenied(false);
    setKendraError("");
    setKendras([]);

    if (!navigator.geolocation) {
      setLocationDenied(true);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        fetchKendras(position.coords.latitude, position.coords.longitude);
      },
      () => {
        setLocationDenied(true);
      },
      { timeout: 10000 },
    );
  }

  function handleManualLocalitySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const coords = resolveManualLocality(manualLocality);
    if (!coords) {
      setKendraError("Please enter an area or locality name.");
      return;
    }
    fetchKendras(coords.lat, coords.lng);
  }

  function buildWhatsAppLink(kendra: KendraResult): string | null {
    if (!kendra.phone) return null;
    const digitsOnly = kendra.phone.replace(/[^0-9]/g, "");
    if (digitsOnly.length < 10) return null;

    const medicineLabel = result?.genericName || result?.matchedName || "this medicine";
    const message = `Hi, I'm looking for ${medicineLabel}. Do you have it available?`;
    return `https://wa.me/${digitsOnly}?text=${encodeURIComponent(message)}`;
  }

  return (
    <main className="min-h-screen bg-[#f7faf8] text-slate-950">
      <section className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-5 py-8 sm:px-8">
        <div className="mb-7">
          <p className="text-sm font-medium text-emerald-700">
            Indore generic medicine lookup
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950 sm:text-4xl">
            Jan Aushadi Finder
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Type a medicine name or upload a clear photo of the strip or box to
            find a likely generic name match.
          </p>
        </div>

        {view === "search" ? (
          <>
            <form
              onSubmit={handleSubmit}
              className="rounded-lg border border-emerald-100 bg-white p-5 shadow-sm sm:p-6"
            >
              <label
                htmlFor="medicine-name"
                className="text-sm font-semibold text-slate-900"
              >
                Medicine name
              </label>
              <input
                id="medicine-name"
                value={medicineName}
                onChange={(event) => {
                  setMedicineName(event.target.value);
                  setResult(null);
                  setError("");
                }}
                placeholder="Example: Crocin, Calpol, Pantocid"
                className="mt-2 h-12 w-full rounded-md border border-slate-300 px-3 text-base outline-none transition focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                maxLength={120}
              />

              <div className="mt-5">
                <label
                  htmlFor="medicine-photo"
                  className="text-sm font-semibold text-slate-900"
                >
                  Medicine photo
                </label>
                <input
                  id="medicine-photo"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageChange}
                  className="mt-2 block w-full rounded-md border border-dashed border-slate-300 bg-slate-50 p-3 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-emerald-700 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white"
                />
                {imageName ? (
                  <p className="mt-2 text-sm text-slate-600">Selected: {imageName}</p>
                ) : null}
              </div>

              <button
                type="submit"
                disabled={!canSearch || isLoading}
                className="mt-6 h-12 w-full rounded-md bg-emerald-700 px-4 text-base font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {isLoading ? "Finding match..." : "Search"}
              </button>
            </form>

            {error ? (
              <div className="mt-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                {error}
              </div>
            ) : null}

            {result ? (
              <section className="mt-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                {result.matchedName && result.genericName ? (
                  <>
                    <p className="text-sm font-medium text-emerald-700">
                      Match found from {result.source === "image" ? "photo" : "text"}
                      {result.aiGenerated ? " (AI-suggested)" : ""}
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                      {result.genericName}
                    </h2>
                    <p className="mt-2 text-sm text-slate-600">
                      Matched from: {result.matchedName}
                    </p>
                    {result.strengths.length ? (
                      <p className="mt-1 text-sm text-slate-600">
                        Common strengths in sample data: {result.strengths.join(", ")}
                      </p>
                    ) : null}
                    <p className="mt-3 text-sm font-medium text-slate-800">
                      Confidence: {Math.round(result.confidence * 100)}%
                    </p>
                    {result.aiGenerated ? (
                      <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                        This match was identified by AI and is not yet
                        verified against the official Jan Aushadi list.
                        Please confirm with a pharmacist before buying.
                      </div>
                    ) : null}
                    <button
                      type="button"
                      className="mt-5 h-11 w-full rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white transition hover:bg-emerald-800"
                      onClick={handleFindKendras}
                    >
                      Find nearby Jan Aushadi Kendra
                    </button>
                    <button
                      type="button"
                      className="mt-3 h-11 w-full rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-900 transition hover:bg-slate-50"
                      onClick={resetSearch}
                    >
                      Search again
                    </button>
                  </>
                ) : (
                  <>
                    <h2 className="text-xl font-semibold text-slate-950">
                      No confident match found
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {result.message ||
                        "Try typing the medicine name manually using the brand name printed on the strip or box."}
                    </p>
                  </>
                )}
              </section>
            ) : null}

            <div className="mt-5 rounded-md bg-amber-50 p-4 text-sm leading-6 text-amber-950">
              This app only matches medicine names to likely generic names. It
              does not provide dosage, treatment, prescription, or
              substitution advice. Confirm with a doctor or pharmacist before
              changing any medicine.
            </div>
          </>
        ) : (
          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <button
              type="button"
              onClick={() => setView("search")}
              className="text-sm font-semibold text-emerald-700 hover:text-emerald-800"
            >
              ← Back to search
            </button>

            <h2 className="mt-3 text-xl font-semibold text-slate-950">
              Nearby Jan Aushadi Kendra
            </h2>

            {isLoadingKendras ? (
              <p className="mt-4 text-sm text-slate-600">
                Finding kendras near you...
              </p>
            ) : null}

            {kendraError ? (
              <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                {kendraError}
              </div>
            ) : null}

            {locationDenied && !isLoadingKendras ? (
              <form
                onSubmit={handleManualLocalitySubmit}
                className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-4"
              >
                <label
                  htmlFor="manual-locality"
                  className="text-sm font-semibold text-amber-950"
                >
                  Location access was denied. Enter your area instead:
                </label>
                <input
                  id="manual-locality"
                  value={manualLocality}
                  onChange={(event) => setManualLocality(event.target.value)}
                  placeholder="Example: Vijay Nagar, Palasia, Rajwada"
                  className="mt-2 h-11 w-full rounded-md border border-amber-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                />
                <button
                  type="submit"
                  className="mt-3 h-10 w-full rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white transition hover:bg-emerald-800"
                >
                  Find kendras near this area
                </button>
              </form>
            ) : null}

            {kendras.length > 0 ? (
              <ul className="mt-5 space-y-3">
                {kendras.map((kendra) => {
                  const whatsappLink = buildWhatsAppLink(kendra);
                  return (
                    <li
                      key={`${kendra.name}-${kendra.distanceKm}`}
                      className="rounded-md border border-slate-200 p-4"
                    >
                      <p className="font-semibold text-slate-950">
                        {kendra.name}
                      </p>
                      <p className="mt-1 text-sm text-slate-600">
                        {kendra.address}
                      </p>
                      <p className="mt-1 text-sm font-medium text-emerald-700">
                        {kendra.distanceKm} km away
                      </p>
                      {whatsappLink ? (
                        <a
                          href={whatsappLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-3 inline-flex h-10 items-center justify-center rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white transition hover:bg-emerald-800"
                        >
                          Message on WhatsApp
                        </a>
                      ) : (
                        <p className="mt-3 text-sm text-slate-400">
                          WhatsApp number not available for this kendra.
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </section>
        )}
      </section>
    </main>
  );
}
