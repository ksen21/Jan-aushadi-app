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
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

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
                <button
                  type="button"
                  className="mt-5 h-11 w-full rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-900 transition hover:bg-slate-50"
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
          This app only matches medicine names to likely generic names. It does
          not provide dosage, treatment, prescription, or substitution advice.
          Confirm with a doctor or pharmacist before changing any medicine.
        </div>
      </section>
    </main>
  );
}
