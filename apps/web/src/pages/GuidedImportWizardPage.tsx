import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type DraftImportConfirmResponse,
  type GuidedImportProgressRead,
  type GuidedImportReviewRead,
  type GuidedImportSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { LegacyFeatureBanner } from "../components/LegacyFeatureBanner";
import { GuidedImportExceptionCard } from "../components/imports/guided/GuidedImportExceptionCard";
import { GuidedImportProgressPanel } from "../components/imports/guided/GuidedImportProgressPanel";
import { GuidedImportSuccessPanel } from "../components/imports/guided/GuidedImportSuccessPanel";

type WizardStep = "source" | "processing" | "review" | "summary" | "success";

export function GuidedImportWizardPage(): JSX.Element {
  const navigate = useNavigate();
  const { importId: importIdParam } = useParams();
  const [searchParams] = useSearchParams();
  const jobIdParam = searchParams.get("jobId");

  const [step, setStep] = useState<WizardStep>(importIdParam ? "review" : jobIdParam ? "processing" : "source");
  const [rawText, setRawText] = useState("");
  const [jobId, setJobId] = useState<string | null>(jobIdParam);
  const [importId, setImportId] = useState<number | null>(importIdParam ? Number(importIdParam) : null);
  const [progress, setProgress] = useState<GuidedImportProgressRead | null>(null);
  const [review, setReview] = useState<GuidedImportReviewRead | null>(null);
  const [summary, setSummary] = useState<GuidedImportSummaryRead | null>(null);
  const [confirmResult, setConfirmResult] = useState<DraftImportConfirmResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [autoExpanded, setAutoExpanded] = useState(false);

  const loadReview = useCallback(async (id: number) => {
    const body = await apiClient.getGuidedImportReview(id);
    setReview(body);
    const sum = await apiClient.getGuidedImportSummary(id);
    setSummary(sum);
  }, []);

  useEffect(() => {
    if (importId && step === "review") {
      void loadReview(importId).catch((err) => {
        setError(err instanceof ApiError ? err.message : "Could not load import review.");
      });
    }
  }, [importId, step, loadReview]);

  useEffect(() => {
    if (step !== "processing" || !jobId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const prog = await apiClient.getGuidedImportProgress(jobId);
        if (cancelled) return;
        setProgress(prog);
        if (prog.import_id) {
          setImportId(prog.import_id);
        }
        if (prog.engine_state === "COMPLETE" && prog.import_id) {
          setStep("review");
          navigate(`/imports/guided/${prog.import_id}`, { replace: true });
          return;
        }
        if (prog.error) {
          setError(prog.error);
          return;
        }
        window.setTimeout(() => void poll(), 1200);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Processing failed.");
        }
      }
    };
    void poll();
    return () => {
      cancelled = true;
    };
  }, [step, jobId, navigate]);

  async function startPasteImport(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const enqueued = await apiClient.enqueueImportParseJob({ raw_text: rawText });
      setJobId(enqueued.job_id);
      setStep("processing");
      navigate(`/imports/guided?jobId=${encodeURIComponent(enqueued.job_id)}`, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start import.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport(): Promise<void> {
    if (!importId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.confirmImport(importId);
      setConfirmResult(result);
      setStep("success");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add books to inventory.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto max-w-3xl px-4 py-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">P92 · Guided import</p>
          <h1 className="mt-2 text-2xl font-semibold text-white">Import your comics</h1>
          <p className="mt-2 text-sm text-slate-400">
            ComicOS detects books, quantities, variants, and pricing — you only review exceptions.
          </p>

          <LegacyFeatureBanner feature="Email / paste import" />

          {error ? (
            <p className="mt-4 rounded-lg border border-red-500/40 bg-red-950/40 px-3 py-2 text-sm text-red-200">{error}</p>
          ) : null}

          {step === "source" ? (
            <section className="mt-8 space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
              <h2 className="text-lg font-semibold">Step 1 — Import your comics</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <Link
                  to="/imports/email"
                  className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 text-sm hover:border-slate-500"
                >
                  📧 Gmail — forward receipts
                </Link>
                <div className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 text-sm text-slate-400">
                  📄 PDF / screenshot — use paste below
                </div>
              </div>
              <label className="block text-sm">
                Paste order text
                <textarea
                  className="mt-2 min-h-[140px] w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder="Paste your retailer confirmation email or order summary…"
                />
              </label>
              <p className="text-xs text-slate-500">
                We&apos;ll automatically detect books, quantities, variants, and pricing.
              </p>
              <button
                type="button"
                disabled={busy || !rawText.trim()}
                onClick={() => void startPasteImport()}
                className="rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-40"
              >
                Continue
              </button>
            </section>
          ) : null}

          {step === "processing" ? (
            <section className="mt-8">
              <h2 className="text-lg font-semibold">Step 2 — Processing order</h2>
              <GuidedImportProgressPanel progress={progress} />
            </section>
          ) : null}

          {step === "review" && review && summary ? (
            <section className="mt-8 space-y-6">
              <h2 className="text-lg font-semibold">Step 3 — Review exceptions only</h2>
              <button
                type="button"
                className="flex w-full items-center justify-between rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-4 py-3 text-left text-sm"
                onClick={() => setAutoExpanded((v) => !v)}
              >
                <span>
                  Looks good — {review.auto_matched_count} books matched automatically
                </span>
                <span className="text-emerald-300">{autoExpanded ? "Hide" : "Show"}</span>
              </button>
              {autoExpanded ? (
                <p className="text-xs text-slate-500">High-confidence matches are already approved and hidden.</p>
              ) : null}
              <div className="rounded-xl border border-amber-500/40 bg-amber-950/20 px-4 py-3">
                <p className="font-medium text-amber-100">
                  Needs attention — {review.exception_count} {review.exception_count === 1 ? "book requires" : "books require"} review
                </p>
              </div>
              <ul className="space-y-3">
                {review.exceptions.map((item) => (
                  <GuidedImportExceptionCard
                    key={item.item_index}
                    item={item}
                    importId={importId!}
                    onUpdated={() => void loadReview(importId!)}
                  />
                ))}
              </ul>
              {review.exception_count === 0 ? (
                <p className="text-sm text-slate-400">Nothing needs attention — you&apos;re ready to add everything to inventory.</p>
              ) : null}
              <button
                type="button"
                className="rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-slate-950"
                onClick={() => setStep("summary")}
              >
                Continue to summary
              </button>
            </section>
          ) : null}

          {step === "summary" && summary ? (
            <section className="mt-8 space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
              <h2 className="text-lg font-semibold">Step 4 — Import summary</h2>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-slate-500">Books imported</dt>
                  <dd className="text-lg font-semibold">{summary.books_imported}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Publishers</dt>
                  <dd className="text-lg font-semibold">{summary.publisher_count}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Variants</dt>
                  <dd className="text-lg font-semibold">{summary.variant_count}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Value tracked</dt>
                  <dd className="text-lg font-semibold">${summary.value_tracked.toFixed(2)}</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-slate-500">New series found</dt>
                  <dd className="text-lg font-semibold">{summary.new_series_count}</dd>
                </div>
              </dl>
              <button
                type="button"
                disabled={busy}
                onClick={() => void confirmImport()}
                className="w-full rounded-lg bg-emerald-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                {busy ? "Adding…" : "Add to inventory"}
              </button>
            </section>
          ) : null}

          {step === "success" && confirmResult && summary ? (
            <GuidedImportSuccessPanel
              booksAdded={confirmResult.total_copies_created}
              summary={summary}
            />
          ) : null}
        </div>
      </div>
    </AppShell>
  );
}
