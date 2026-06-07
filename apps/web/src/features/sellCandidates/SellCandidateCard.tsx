import type { SellCandidateDisplayCard } from "./sellCandidatePresentation";

type Props = {
  card: SellCandidateDisplayCard;
  onGenerateDraft?: (card: SellCandidateDisplayCard) => void;
  draftLinkId?: number | null;
  reviewDraftUrl?: string;
};

function money(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function profitText(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${money(value)}`;
}

export function SellCandidateCard({ card, onGenerateDraft, reviewDraftUrl }: Props): JSX.Element {
  return (
    <article
      className={`rounded-lg border bg-white px-4 py-4 text-blue-950 shadow-sm ${
        card.isTopOpportunity ? "border-red-600 ring-2 ring-red-200" : "border-blue-800"
      }`}
    >
      <div className="flex flex-wrap items-start gap-4">
        {card.coverImageUrl ? (
          <img
            src={card.coverImageUrl}
            alt=""
            className="h-24 w-16 shrink-0 rounded object-cover"
          />
        ) : (
          <div className="flex h-24 w-16 shrink-0 items-center justify-center rounded border border-blue-200 bg-blue-50 text-xs text-blue-600">
            Cover
          </div>
        )}
        <div className="min-w-0 flex-1">
          {card.isTopOpportunity ? (
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-700">Top Sell Opportunity</p>
          ) : null}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="text-base font-semibold leading-snug text-blue-950">{card.displayTitle}</h2>
            <span className="shrink-0 rounded-full bg-red-700 px-2.5 py-0.5 text-xs font-semibold uppercase text-white">
              {card.badgeLabel}
            </span>
          </div>
          <p className="mt-1 text-sm text-blue-800">
            Confidence: <span className="font-medium">{card.confidence}</span>
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-blue-600">Estimated Sale</dt>
              <dd className="font-medium">{money(card.estimatedSaleValue)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-blue-600">Estimated Profit</dt>
              <dd className="font-medium">{profitText(card.estimatedProfit)}</dd>
            </div>
          </dl>
          {card.quickSalePrice != null ? (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs uppercase tracking-wide text-blue-600">Quick Sale</dt>
                <dd className="font-medium">{money(card.quickSalePrice)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-blue-600">Market</dt>
                <dd className="font-medium">{card.marketPrice != null ? money(card.marketPrice) : "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-blue-600">Premium</dt>
                <dd className="font-medium">{card.premiumPrice != null ? money(card.premiumPrice) : "—"}</dd>
              </div>
            </dl>
          ) : null}
          {card.pricingConfidence ? (
            <p className="mt-2 text-sm text-blue-800">
              Pricing confidence: <span className="font-medium">{card.pricingConfidence}</span>
            </p>
          ) : null}
          {card.reasonSummary ? (
            <p className="mt-3 text-sm text-blue-800">{card.reasonSummary}</p>
          ) : null}
          {card.reasons.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-blue-800">
              {card.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
          {onGenerateDraft &&
          (card.recommendation === "SELL_NOW" || card.recommendation === "GRADE_FIRST") ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="rounded-md border border-blue-800 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-50"
                onClick={() => onGenerateDraft(card)}
              >
                Generate Listing Draft
              </button>
              {reviewDraftUrl ? (
                <a href={reviewDraftUrl} className="text-sm text-red-700 underline">
                  Review Listing Draft
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
