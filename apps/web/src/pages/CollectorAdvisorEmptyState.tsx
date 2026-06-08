import {
  ADVISOR_CAPABILITY_CARDS,
  COLLECTOR_ADVISOR_ANALYSIS_BULLETS,
  COLLECTOR_ADVISOR_ANALYSIS_INTRO,
  COLLECTOR_ADVISOR_GENERATE_CTA,
  COLLECTOR_ADVISOR_NO_PLAN_MESSAGE,
  COLLECTOR_ADVISOR_PLAN_PITCH,
  COLLECTOR_ADVISOR_SUBTITLE,
} from "./collectorAdvisorPresentation";

type Props = {
  onGenerate: () => void;
  generating?: boolean;
  generateError?: string | null;
};

export function CollectorAdvisorEmptyState({
  onGenerate,
  generating = false,
  generateError = null,
}: Props): JSX.Element {
  return (
    <div className="space-y-6" data-testid="collector-advisor-empty">
      <div className="rounded-xl border border-blue-200 bg-white px-5 py-6 text-blue-950 shadow-sm">
        <p className="text-sm font-medium text-red-700">{COLLECTOR_ADVISOR_SUBTITLE}</p>
        <p className="mt-3 text-sm text-blue-900">{COLLECTOR_ADVISOR_ANALYSIS_INTRO}</p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-blue-800">
          {COLLECTOR_ADVISOR_ANALYSIS_BULLETS.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-blue-900">{COLLECTOR_ADVISOR_PLAN_PITCH}</p>
        <p className="mt-4 text-sm font-medium text-blue-950">{COLLECTOR_ADVISOR_NO_PLAN_MESSAGE}</p>
        {generateError ? <p className="mt-2 text-sm text-red-700">{generateError}</p> : null}
        <button
          type="button"
          data-testid="collector-advisor-generate"
          disabled={generating}
          onClick={() => onGenerate()}
          className="mt-4 rounded-md border border-red-700 bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {generating ? "Building your plan…" : COLLECTOR_ADVISOR_GENERATE_CTA}
        </button>
      </div>

      <div>
        <p className="mb-3 text-xs uppercase tracking-wide text-blue-200">What you will get</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ADVISOR_CAPABILITY_CARDS.map((card) => (
            <div
              key={card.key}
              className="rounded-lg border border-blue-800/80 bg-white/5 px-4 py-4 text-center"
            >
              <span className="text-2xl" aria-hidden>
                {card.icon}
              </span>
              <p className="mt-2 text-sm font-semibold text-white">{card.title}</p>
              <p className="mt-1 text-xs leading-snug text-blue-100">{card.blurb}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
