import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

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

  return (
    <PatriotPageLayout
      eyebrow="P82"
      title={opp?.title ?? "Marketplace opportunity"}
      showExpansionNav={true}
      error={error}
      onRetry={() => void load()}
      loading={loading && !opp}
      maxWidthClass="max-w-3xl"
      headerExtra={
        <Link to="/marketplace-opportunities" className="text-blue-100 hover:text-white hover:underline">
          ← Opportunities
        </Link>
      }
    >
      {opp ? (
        <PatriotPanel>
          <p className="text-blue-900">
            {opp.recommendation} · Score {opp.opportunity_score} · Discount to FMV {opp.discount_to_fmv}%
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-blue-800">
            {opp.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {opp.listing_url ? (
            <a
              href={opp.listing_url}
              className="mt-3 inline-block font-medium text-blue-700 hover:text-red-700 hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              View listing
            </a>
          ) : null}
        </PatriotPanel>
      ) : null}
    </PatriotPageLayout>
  );
}
