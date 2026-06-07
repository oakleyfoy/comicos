import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import {
  formatRecommendationBadge,
  formatUpsideDisplay,
  isSafeMarketplaceListingUrl,
} from "../features/buyOpportunities/buyOpportunityPresentation";

export function MarketplaceOpportunityDetailPage(): JSX.Element {
  const { id } = useParams();
  const [opp, setOpp] = useState<P82MarketplaceAcquisitionOpportunityRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    setLoading(true);
    try {
      setOpp(await apiClient.getMarketplaceAcquisitionOpportunity(Number(id)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Not found.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const listingSafe = opp ? isSafeMarketplaceListingUrl(opp) : false;
  const badge = opp ? formatRecommendationBadge(opp.recommendation, opp.opportunity_score) : "";
  const upside = opp ? formatUpsideDisplay(opp.asking_price, opp.estimated_fmv) : null;

  return (
    <PatriotPageLayout
      eyebrow="Buy"
      title={opp?.title ?? "Buy opportunity"}
      showExpansionNav={true}
      error={error}
      onRetry={() => void load()}
      loading={loading && !opp}
      maxWidthClass="max-w-3xl"
      headerExtra={
        <Link to="/buy-opportunities" className="text-blue-100 hover:text-white hover:underline">
          ← Buy Opportunities
        </Link>
      }
    >
      {opp ? (
        <PatriotPanel>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="rounded-full bg-red-700 px-2.5 py-0.5 text-xs font-semibold text-white">
              {badge}
            </span>
            <span className="text-sm text-blue-800">Score {Math.round(opp.opportunity_score)}</span>
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-blue-600">Price</dt>
              <dd className="font-medium">${opp.asking_price.toFixed(2)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-blue-600">FMV</dt>
              <dd className="font-medium">${opp.estimated_fmv.toFixed(2)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-blue-600">Upside</dt>
              <dd className="font-medium">{upside?.text.replace(/^Upside:\s*/, "") ?? "Unknown"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-blue-600">Discount to FMV</dt>
              <dd className="font-medium">{opp.discount_to_fmv.toFixed(1)}%</dd>
            </div>
          </dl>

          {opp.reasons.length > 0 ? (
            <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-blue-800">
              {opp.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : null}

          {listingSafe ? (
            <a
              href={opp.listing_url}
              className="mt-4 inline-block rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-800"
              target="_blank"
              rel="noreferrer"
            >
              View Marketplace Listing
            </a>
          ) : (
            <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
              <p className="font-medium">No live marketplace listing is available for this opportunity yet.</p>
              <p className="mt-1 text-blue-800">
                ComicOS identified this as a buy opportunity based on value and collection signals, but the listing
                source is not currently verified.
              </p>
            </div>
          )}
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
