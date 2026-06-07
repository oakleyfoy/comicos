import { Link } from "react-router-dom";

import type { BuyOpportunityDisplayCard } from "./buyOpportunityPresentation";

type Props = {
  card: BuyOpportunityDisplayCard;
};

export function BuyOpportunityCard({ card }: Props): JSX.Element {
  return (
    <article
      className={`rounded-lg border bg-white px-4 py-4 text-blue-950 shadow-sm ${
        card.isTopOpportunity ? "border-red-600 ring-2 ring-red-200" : "border-blue-800"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {card.isTopOpportunity ? (
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-700">Top Opportunity</p>
          ) : null}
          <h2 className="text-base font-semibold leading-snug">
            <Link to={`/marketplace-opportunity/${card.primaryId}`} className="text-red-700 hover:underline">
              {card.displayTitle}
            </Link>
          </h2>
          {card.variantLabel ? (
            <p className="mt-0.5 text-xs text-blue-700">Variant: {card.variantLabel}</p>
          ) : null}
        </div>
        <span className="shrink-0 rounded-full bg-red-700 px-2.5 py-0.5 text-xs font-semibold text-white">
          {card.badgeLabel}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs uppercase tracking-wide text-blue-600">Price</dt>
          <dd className="font-medium">${card.bestPrice.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-blue-600">FMV</dt>
          <dd className="font-medium">${card.fmv.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-blue-600">Upside</dt>
          <dd className="font-medium">{card.upsideText.replace(/^Upside:\s*/, "")}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-blue-600">Score</dt>
          <dd className="font-medium text-blue-800">{Math.round(card.score)}</dd>
        </div>
      </dl>

      {card.hasVerifiedListings ? (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs uppercase tracking-wide text-blue-600">Best marketplace</dt>
            <dd className="font-medium">{card.bestMarketplaceLabel ?? "eBay"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-blue-600">Best price</dt>
            <dd className="font-medium">${card.bestPrice.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-blue-600">Listings</dt>
            <dd className="font-medium">{card.activeListingCount}</dd>
          </div>
          {card.savingsVsHighest != null ? (
            <div className="sm:col-span-3">
              <dt className="text-xs uppercase tracking-wide text-blue-600">Savings vs highest</dt>
              <dd className="font-medium">${card.savingsVsHighest.toFixed(2)}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {card.reasons.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-blue-800">
          {card.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}

      {card.otherListingsCount > 0 ? (
        <p className="mt-3 text-xs text-blue-700">
          Best price found: ${card.bestPrice.toFixed(2)} · Other listings: {card.otherListingsCount}
        </p>
      ) : null}

      <p className="mt-3 text-sm">
        <Link
          to={`/marketplace-opportunity/${card.primaryId}`}
          className="inline-block rounded-md border border-blue-800 px-3 py-1.5 font-medium text-blue-900 hover:bg-blue-50"
        >
          {card.hasVerifiedListings ? "View Listings" : "View Opportunity"}
        </Link>
      </p>
    </article>
  );
}
