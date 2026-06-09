import { useState } from "react";

import type { ImportMetadataQuestion } from "../../pages/importMetadataQuestions";

type ImportMetadataQuestionsGateProps = {
  questions: ImportMetadataQuestion[];
  disabled?: boolean;
  onAnswer: (question: ImportMetadataQuestion, answer: string | null) => void | Promise<void>;
};

function ConfirmFieldPreview({ question }: { question: ImportMetadataQuestion }): JSX.Element | null {
  if (question.kind !== "confirm_parsed") {
    return null;
  }

  const fieldLabel = question.affectedField?.trim();
  const fromOrder = question.invoiceValue?.trim();
  const comicOsValue = question.parsedValue?.trim() ?? question.suggestedAnswer?.trim();
  const valuesMatch =
    fromOrder && comicOsValue && fromOrder.localeCompare(comicOsValue, undefined, { sensitivity: "accent" }) === 0;

  if (!fieldLabel && !fromOrder && !comicOsValue) {
    return null;
  }

  return (
    <div
      className="mt-4 rounded-2xl border border-white/15 bg-slate-950/90 px-4 py-4"
      data-testid="import-metadata-confirm-preview"
    >
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan-200/90">
        {fieldLabel ? `Confirm ${fieldLabel.toLowerCase()}` : "Confirm this value"}
      </p>
      {valuesMatch && comicOsValue ? (
        <p className="mt-3 text-base font-semibold text-white">{comicOsValue}</p>
      ) : (
        <dl className="mt-3 space-y-3 text-sm">
          {fromOrder ? (
            <div>
              <dt className="font-medium text-slate-400">From your order</dt>
              <dd className="mt-1 text-base font-semibold text-white">{fromOrder}</dd>
            </div>
          ) : null}
          {comicOsValue ? (
            <div>
              <dt className="font-medium text-slate-400">ComicOS will use</dt>
              <dd className="mt-1 text-base font-semibold text-emerald-100">{comicOsValue}</dd>
            </div>
          ) : null}
        </dl>
      )}
      <p className="mt-3 text-sm text-slate-400">
        {valuesMatch
          ? "If this matches your receipt, confirm below to continue."
          : "If ComicOS picked the right value, confirm below. You can fix it on the line item after the full order appears."}
      </p>
    </div>
  );
}

export function ImportMetadataQuestionsGate({
  questions,
  disabled = false,
  onAnswer,
}: ImportMetadataQuestionsGateProps): JSX.Element | null {
  const [draftAnswer, setDraftAnswer] = useState("");
  const [busy, setBusy] = useState(false);

  if (!questions.length) {
    return null;
  }

  const current = questions[0];
  const needsText =
    current.kind === "missing_publisher" ||
    current.kind === "publisher_canonical" ||
    current.kind === "release_date";

  const inputValue = draftAnswer || current.suggestedAnswer || "";

  async function submitText(): Promise<void> {
    const value = inputValue.trim();
    if (!value) {
      return;
    }
    setBusy(true);
    try {
      await onAnswer(current, value);
      setDraftAnswer("");
    } finally {
      setBusy(false);
    }
  }

  async function submitConfirm(): Promise<void> {
    setBusy(true);
    try {
      await onAnswer(current, null);
      setDraftAnswer("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="mt-6 rounded-3xl border border-cyan-400/25 bg-slate-900/90 p-6 shadow-xl shadow-black/30"
      data-testid="import-metadata-questions-gate"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
        Before we show your order · {questions.length}{" "}
        {questions.length === 1 ? "question left" : "questions left"}
      </p>
      <h2 className="mt-2 text-xl font-semibold text-white">{current.comicLabel}</h2>
      <p className="mt-4 text-base leading-relaxed text-slate-200">{current.prompt}</p>
      <ConfirmFieldPreview question={current} />

      {needsText ? (
        <div className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-slate-300">
            {current.kind === "release_date" ? "Release date" : "Publisher"}
            <input
              type="text"
              value={inputValue}
              onChange={(event) => setDraftAnswer(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-white/15 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-cyan-300/50"
              placeholder={
                current.kind === "missing_publisher"
                  ? "e.g. Marvel, Image, Dark Horse"
                  : current.kind === "release_date"
                    ? "YYYY-MM-DD"
                    : undefined
              }
              disabled={disabled || busy}
              data-testid="import-metadata-question-input"
            />
          </label>
          <button
            type="button"
            disabled={disabled || busy || !inputValue.trim()}
            onClick={() => void submitText()}
            className="rounded-2xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="import-metadata-question-continue"
          >
            {busy ? "Saving…" : "Continue"}
          </button>
        </div>
      ) : (
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={disabled || busy}
            onClick={() => void submitConfirm()}
            className="rounded-2xl bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="import-metadata-question-confirm"
          >
            {busy ? "Saving…" : "Yes, that's correct"}
          </button>
        </div>
      )}

      <p className="mt-6 text-xs text-slate-500">
        Nothing else from this import is shown until these answers are saved. Then you&apos;ll see
        covers, release dates, and the full line-item review.
      </p>
    </section>
  );
}
