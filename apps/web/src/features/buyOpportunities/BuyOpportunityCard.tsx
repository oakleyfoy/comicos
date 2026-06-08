import { Link } from "react-router-dom";

import type { BuyOpportunityDisplayCard } from "./buyOpportunityPresentation";
import { resolveOpportunityBuyCta } from "./buyVerifiedAction";

type Props = {
  card: BuyOpportunityDisplayCard;
};

export function BuyOpportunityCard({ card }: Props): JSX.Element {
  const cta = resolveOpportunityBuyCta({
    id: card.primaryId,
    title: card.displayTitle,
    series: "",
    issue: "",
    marketplace: card.marketplaceLabel ?? "",
    external_listing_id: "",
    listing_url: card.bestVerifiedListing?.listing_url ?? "",
    asking_price: card.bestPrice,
    estimated_fmv: card.fmv,
    discount_to_fmv: 0,
    liquidity: 0,
    velocity: 0,
    grading_upside: 0,
    ownership_status: "",
    profile_match_score: 0,
    opportunity_score: card.score,
    recommendation: card.recommendation,
    reasons: card.reasons,
    status: "ACTIVE",
    created_at: "",
    updated_at: "",
    publisher: "",
    variant: "",
    has_verified_listings: card.hasVerifiedListings,
    best_verified_listing: card.bestVerifiedListing ?? null,
  });

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
          {cta.subtext ? <p className="mt-1 text-xs text-blue-700">{cta.subtext}</p> : null}
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

      {card.reasons.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-blue-800">
          {card.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}

      <p className="mt-3 text-sm">
        {cta.external ? (
          <a
            href={cta.href}
            target="_blank"
            rel="noreferrer"
            className="inline-block rounded-md bg-red-700 px-3 py-1.5 font-medium text-white hover:bg-red-800"
          >
            {cta.label}
          </a>
        ) : (
          <Link
            to={cta.href}
            className="inline-block rounded-md border border-blue-800 px-3 py-1.5 font-medium text-blue-900 hover:bg-blue-50"
          >
            {cta.label}
          </Link>
        )}
      </p>
    </article>
  );
}
