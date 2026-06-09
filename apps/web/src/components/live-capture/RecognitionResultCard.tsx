import type { RecognitionIdentifyRead, ReceivingSessionItemRead } from "../../api/client";

interface RecognitionResultCardProps {
  identification?: RecognitionIdentifyRead | null;
  item?: ReceivingSessionItemRead | null;
  onConfirm?: () => void;
  onSkip?: () => void;
  onReview?: () => void;
  keyboardHint?: string | null;
}

export function RecognitionResultCard({
  identification,
  item,
  onConfirm,
  onSkip,
  onReview,
  keyboardHint,
}: RecognitionResultCardProps): JSX.Element | null {
  if (!identification && !item) {
    return null;
  }

  const title =
    item?.selected_candidate_json && typeof item.selected_candidate_json === "object"
      ? `${String((item.selected_candidate_json as Record<string, unknown>).series ?? "Unknown")} #${String(
          (item.selected_candidate_json as Record<string, unknown>).issue_number ?? "?",
        )}`
      : identification?.series
        ? `${identification.series} #${identification.issue_number ?? "?"}`
        : "Recognition result";
  const confidence =
    item?.recognition_confidence != null
      ? `${Math.round(item.recognition_confidence * 100)}%`
      : identification
        ? `${Math.round(identification.confidence * 100)}%`
        : "—";
  const bucket = item?.recognition_bucket ?? identification?.bucket ?? "—";

  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900 p-4 text-slate-100 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Latest capture</p>
          <h2 className="mt-1 text-xl font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-slate-400">
            Bucket {bucket} · Confidence {confidence}
          </p>
        </div>
        {keyboardHint ? <div className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">{keyboardHint}</div> : null}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={onConfirm} className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950">
          Confirm
        </button>
        <button type="button" onClick={onSkip} className="rounded-full bg-slate-700 px-4 py-2 text-sm font-semibold text-white">
          Skip
        </button>
        <button type="button" onClick={onReview} className="rounded-full bg-amber-400 px-4 py-2 text-sm font-semibold text-slate-950">
          Review
        </button>
      </div>
    </section>
  );
}
