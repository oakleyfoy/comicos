import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type P91OnboardingDraft,
  type P91RecommendationPreviewRead,
} from "../../../api/client";
import { SearchableInterestMultiSelect } from "./SearchableInterestMultiSelect";
import { WizardSelectionCard } from "./WizardSelectionCard";
import {
  COLLECTOR_TYPE_CARDS,
  HORIZON_CARDS,
  ONBOARDING_STEPS,
  RISK_CARDS,
  TOTAL_ONBOARDING_STEPS,
} from "./wizardConfig";

export type CollectorProfileWizardMode = "onboarding" | "settings";

type Props = {
  mode: CollectorProfileWizardMode;
  initialDraft?: P91OnboardingDraft;
  onFinished?: () => void;
};

const EMPTY_DRAFT: P91OnboardingDraft = {
  step: 1,
  collector_type: null,
  risk_profile: null,
  time_horizon: null,
  publisher_labels: [],
  character_labels: [],
  creator_labels: [],
};

export function CollectorProfileWizard({ mode, initialDraft, onFinished }: Props): JSX.Element {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<P91OnboardingDraft>(initialDraft ?? EMPTY_DRAFT);
  const [preview, setPreview] = useState<P91RecommendationPreviewRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (initialDraft) {
      setDraft(initialDraft);
    }
  }, [initialDraft]);

  useEffect(() => {
    if (mode !== "onboarding") return;
    void (async () => {
      try {
        const status = await apiClient.getCollectorOnboardingStatus();
        if (status.draft) setDraft(status.draft);
      } catch {
        // Keep local/initial draft.
      }
    })();
  }, [mode]);

  const stepIndex = Math.min(Math.max(draft.step, 1), TOTAL_ONBOARDING_STEPS) - 1;
  const stepDef = ONBOARDING_STEPS[stepIndex];

  const persistDraft = useCallback(async (next: P91OnboardingDraft) => {
    setDraft(next);
    if (mode === "onboarding") {
      try {
        await apiClient.saveCollectorOnboardingDraft({ draft: next });
      } catch {
        // Best-effort — local state still advances; user can retry on complete.
      }
    }
  }, [mode]);

  useEffect(() => {
    if (stepDef.id !== "preview") return;
    let cancelled = false;
    void (async () => {
      try {
        const body = await apiClient.previewCollectorOnboarding(draft);
        if (!cancelled) setPreview(body);
      } catch {
        if (!cancelled) setPreview(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [draft, stepDef.id]);

  const canContinue = useMemo(() => {
    switch (stepDef.id) {
      case "collector_type":
        return Boolean(draft.collector_type);
      case "risk_tolerance":
        return Boolean(draft.risk_profile);
      case "time_horizon":
        return Boolean(draft.time_horizon);
      default:
        return true;
    }
  }, [draft, stepDef.id]);

  async function goNext(): Promise<void> {
    setError(null);
    const nextStep = Math.min(draft.step + 1, TOTAL_ONBOARDING_STEPS);
    await persistDraft({ ...draft, step: nextStep });
  }

  async function goBack(): Promise<void> {
    setError(null);
    const prevStep = Math.max(draft.step - 1, 1);
    await persistDraft({ ...draft, step: prevStep });
  }

  async function finish(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const payload = { ...draft, step: TOTAL_ONBOARDING_STEPS };
      if (mode === "onboarding") {
        await apiClient.completeCollectorOnboarding({ draft: payload });
        onFinished?.();
        navigate("/collector-home", { replace: true });
      } else {
        await apiClient.updateCollectorProfile({
          ...(payload.collector_type ? { collector_type: payload.collector_type } : {}),
          ...(payload.risk_profile ? { risk_profile: payload.risk_profile } : {}),
          ...(payload.time_horizon ? { time_horizon: payload.time_horizon } : {}),
          publishers: payload.publisher_labels.map((label, index) => ({
            interest_type: "PUBLISHER",
            label,
            priority_rank: index + 1,
          })),
          characters: payload.character_labels.map((label, index) => ({
            interest_type: "CHARACTER",
            label,
            priority_rank: index + 1,
          })),
          creators: payload.creator_labels.map((label, index) => ({
            interest_type: "CREATOR",
            label,
            priority_rank: index + 1,
          })),
        });
        onFinished?.();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save profile.");
    } finally {
      setBusy(false);
    }
  }

  function renderStepBody(): JSX.Element {
    switch (stepDef.id) {
      case "collector_type":
        return (
          <div className="grid gap-3 sm:grid-cols-2">
            {COLLECTOR_TYPE_CARDS.map((card) => (
              <WizardSelectionCard
                key={card.value}
                title={`${card.icon} ${card.title}`}
                description={card.description}
                badge={card.value === "HYBRID" ? "Popular" : undefined}
                selected={draft.collector_type === card.value}
                onSelect={() => void persistDraft({ ...draft, collector_type: card.value })}
              >
                <p className="font-medium">{card.behavior}</p>
                <ul className="mt-2 list-inside list-disc space-y-0.5 text-xs opacity-90">
                  {card.examples.map((ex) => (
                    <li key={ex}>{ex}</li>
                  ))}
                </ul>
              </WizardSelectionCard>
            ))}
            <p className="sm:col-span-2 text-center text-sm text-slate-500">Most ComicOS users choose Hybrid.</p>
          </div>
        );
      case "risk_tolerance":
        return (
          <div className="grid gap-3">
            {RISK_CARDS.map((card) => (
              <WizardSelectionCard
                key={card.value}
                title={card.title}
                description={card.summary}
                selected={draft.risk_profile === card.value}
                onSelect={() => void persistDraft({ ...draft, risk_profile: card.value })}
              >
                {card.examples ? (
                  <p className="text-xs">Examples: {card.examples.join(", ")}</p>
                ) : null}
              </WizardSelectionCard>
            ))}
            <p className="text-sm text-slate-500">Risk tolerance directly affects recommendation rankings.</p>
          </div>
        );
      case "time_horizon":
        return (
          <div className="grid gap-3 sm:grid-cols-2">
            {HORIZON_CARDS.map((card) => (
              <WizardSelectionCard
                key={card.value}
                title={card.title}
                description={`${card.range} — ${card.focus}`}
                badge={card.value === "MIXED" ? "Popular" : undefined}
                selected={draft.time_horizon === card.value}
                onSelect={() => void persistDraft({ ...draft, time_horizon: card.value })}
              />
            ))}
            <p className="sm:col-span-2 text-center text-sm text-slate-500">Most collectors select Mixed.</p>
          </div>
        );
      case "publishers":
        return (
          <SearchableInterestMultiSelect
            kind="PUBLISHER"
            selected={draft.publisher_labels}
            onChange={(publisher_labels) => void persistDraft({ ...draft, publisher_labels })}
            placeholder="Search publishers (Marvel, DC, Image…)"
          />
        );
      case "characters":
        return (
          <SearchableInterestMultiSelect
            kind="CHARACTER"
            selected={draft.character_labels}
            onChange={(character_labels) => void persistDraft({ ...draft, character_labels })}
            placeholder="Search characters"
          />
        );
      case "creators":
        return (
          <SearchableInterestMultiSelect
            kind="CREATOR"
            selected={draft.creator_labels}
            onChange={(creator_labels) => void persistDraft({ ...draft, creator_labels })}
            placeholder="Search creators"
          />
        );
      case "preview":
        return (
          <div className="space-y-6">
            <dl className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm sm:grid-cols-2">
              {preview
                ? Object.entries(preview.summary).map(([key, value]) => (
                    <div key={key}>
                      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{key}</dt>
                      <dd className="mt-1 font-medium text-slate-900">
                        {Array.isArray(value) ? (value.length ? value.join(", ") : "—") : value}
                      </dd>
                    </div>
                  ))
                : null}
            </dl>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">ComicOS will prioritize:</h3>
              <ul className="mt-3 space-y-2">
                {(preview?.priorities ?? []).map((item) => (
                  <li key={item.text} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="text-emerald-600" aria-hidden>
                      ✓
                    </span>
                    {item.text}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        );
      default:
        return <p className="text-sm text-slate-600">Step coming soon.</p>;
    }
  }

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
          Step {draft.step} of {TOTAL_ONBOARDING_STEPS}
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{stepDef.title}</h2>
        <p className="mt-2 text-sm text-slate-600">{stepDef.subtitle}</p>
      </div>

      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}

      {renderStepBody()}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
        <button
          type="button"
          className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
          disabled={draft.step <= 1 || busy}
          onClick={() => void goBack()}
        >
          Back
        </button>
        <div className="flex gap-2">
          {stepDef.id !== "preview" ? (
            <button
              type="button"
              className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
              disabled={busy}
              onClick={() => void goNext()}
            >
              Skip
            </button>
          ) : null}
          {stepDef.id === "preview" ? (
            <button
              type="button"
              disabled={busy}
              className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
              onClick={() => void finish()}
            >
              {busy ? "Saving…" : mode === "onboarding" ? "Enter ComicOS" : "Save profile"}
            </button>
          ) : (
            <button
              type="button"
              disabled={!canContinue || busy}
              className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
              onClick={() => void goNext()}
            >
              Continue
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
