import { useEffect, useState } from "react";

import { ApiError, apiClient, type P91OnboardingDraft } from "../api/client";
import { CollectorProfileWizard } from "../components/collector/onboarding/CollectorProfileWizard";

export function CollectorOnboardingPage(): JSX.Element {
  const [draft, setDraft] = useState<P91OnboardingDraft | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const status = await apiClient.getCollectorOnboardingStatus();
        setDraft(status.draft);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Unable to load onboarding.");
      }
    })();
  }, []);

  return (
    <div className="relative min-h-screen bg-slate-950 text-slate-100">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.07]"
        aria-hidden
        style={{
          backgroundImage:
            "linear-gradient(135deg, #0f172a 0%, #1e293b 40%, #334155 100%), repeating-linear-gradient(90deg, transparent, transparent 48px, rgba(255,255,255,0.03) 48px, rgba(255,255,255,0.03) 49px)",
        }}
      />
      <div className="relative mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-10 sm:px-6">
        <header className="mb-8 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">P91-01 · Welcome</p>
          <h1 className="text-3xl font-semibold tracking-tight text-white">Build your collector profile</h1>
          <p className="max-w-xl text-sm text-slate-300">
            A guided setup so ComicOS understands how you collect — with plain-language choices and catalog-backed
            favorites.
          </p>
        </header>
        <main className="flex-1 rounded-2xl border border-slate-800 bg-white p-6 text-slate-900 shadow-2xl sm:p-8">
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {draft ? <CollectorProfileWizard mode="onboarding" initialDraft={draft} /> : (
            <p className="text-sm text-slate-500">Loading your progress…</p>
          )}
        </main>
      </div>
    </div>
  );
}
