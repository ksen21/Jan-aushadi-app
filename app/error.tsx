"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log for our own visibility; nothing user-sensitive is captured here.
    console.error("Jan Aushadi Finder crashed:", error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f7faf8] px-5 text-slate-950">
      <div className="w-full max-w-md rounded-lg border border-red-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-slate-950">Something went wrong</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          The app hit an unexpected error. This is usually temporary — try again, and if it keeps
          happening, the backend service may be down.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-5 h-11 w-full rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white transition hover:bg-emerald-800"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
