import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type P82MarketplaceAcquisitionOpportunityRead,
  type P88MarketplaceComparisonRead,
  type P88MarketplaceListingRead,
  type P88MarketplaceOpportunitySourceRead,
} from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import {
  formatRecommendationBadge,
  formatUpsideDisplay,
  isSafeMarketplaceListingUrl,
} from "../features/buyOpportunities/buyOpportunityPresentation";
import { ImportMarketplaceUrlModal } from "../features/buyOpportunities/ImportMarketplaceUrlModal";

function sourceTypeLabel(sourceType: string): string {
  if (sourceType === "MANUAL_IMPORT") {
    return "Manual Import";
  }
  return sourceType.replace(/_/g, " ");
}

export function MarketplaceOpportunityDetailPage(): JSX.Element {
  const { id } = useParams();
  const [opp, setOpp] = useState<P82MarketplaceAcquisitionOpportunityRead | null>(null);
  const [sources, setSources] = useState<P88MarketplaceOpportunitySourceRead[]>([]);
  const [listings, setListings] = useState<P88MarketplaceListingRead[]>([]);
  const [comparison, setComparison] = useState<P88MarketplaceComparisonRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [importOpen, setImportOpen] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    setLoading(true);
    try {
      const oppId = Number(id);
      const [detail, sourceList, listingList, comparisonBody] = await Promise.all([
        apiClient.getMarketplaceAcquisitionOpportunity(oppId),
        apiClient.listBuyOpportunitySources({ opportunity_id: oppId }).catch(() => ({ items: [] })),
        apiClient.listBuyOpportunityMarketplaceListings(oppId).catch(() => ({ items: [] })),
        apiClient.getBuyOpportunityMarketplaceComparison(oppId).catch(() => null),
      ]);
      setOpp(detail);
      setSources(sourceList.items ?? []);
      setListings(listingList.items ?? []);
      setComparison(comparisonBody?.comparison ?? null);
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
  const displayPrice =
    opp?.has_verified_listings && opp.best_active_price != null ? opp.best_active_price : opp?.asking_price;
  const badge = opp ? formatRecommendationBadge(opp.recommendation, opp.opportunity_score) : "";
  const upside = opp ? formatUpsideDisplay(displayPrice ?? opp.asking_price, opp.estimated_fmv) : null;
  const opportunityHealthBadges: string[] = [];
  if (opp?.has_verified_listings) {
    opportunityHealthBadges.push("Verified Listings");
  }
  for (const row of listings) {
    for (const b of row.health_badges ?? []) {
      if (!opportunityHealthBadges.includes(b)) {
        opportunityHealthBadges.push(b);
      }
    }
  }

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
      headerActions={
        opp ? (
          <button
            type="button"
            className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-blue-50"
            onClick={() => setImportOpen(true)}
          >
            Import Marketplace URL
          </button>
        ) : null
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

          {opportunityHealthBadges.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {opportunityHealthBadges.map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-blue-300 bg-white px-2 py-0.5 text-xs font-medium text-blue-900"
                >
                  {label}
                </span>
              ))}
            </div>
          ) : null}

          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-blue-600">Price</dt>
              <dd className="font-medium">${(displayPrice ?? opp.asking_price).toFixed(2)}</dd>
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

          {comparison && comparison.rankings.length > 0 ? (
            <div className="mt-6 border-t border-blue-200 pt-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-red-700">
                Marketplace comparison
              </h3>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[520px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-blue-200 text-left text-xs uppercase text-blue-600">
                      <th className="py-2 pr-3">Marketplace</th>
                      <th className="py-2 pr-3">Price</th>
                      <th className="py-2 pr-3">Shipping</th>
                      <th className="py-2 pr-3">Total cost</th>
                      <th className="py-2">Availability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.rankings.map((row) => (
                      <tr
                        key={row.marketplace}
                        className={`border-b border-blue-100 ${row.is_best ? "bg-green-50" : ""}`}
                      >
                        <td className="py-2 pr-3 font-medium">
                          {row.marketplace_name}
                          {row.is_best ? (
                            <span className="ml-2 rounded-full bg-green-700 px-2 py-0.5 text-xs font-semibold text-white">
                              Lowest Total Cost
                            </span>
                          ) : null}
                        </td>
                        <td className="py-2 pr-3">
                          {row.price != null ? `$${row.price.toFixed(2)}` : "—"}
                        </td>
                        <td className="py-2 pr-3">
                          {row.shipping != null ? `$${row.shipping.toFixed(2)}` : "—"}
                        </td>
                        <td className="py-2 pr-3 font-medium">
                          {row.overall_cost != null ? `$${row.overall_cost.toFixed(2)}` : "—"}
                        </td>
                        <td className="py-2">{row.availability_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {comparison.savings_vs_highest != null && comparison.savings_vs_highest > 0 ? (
                <p className="mt-2 text-sm text-blue-800">
                  Savings vs highest marketplace: ${comparison.savings_vs_highest.toFixed(2)}
                </p>
              ) : null}
            </div>
          ) : null}

          {listings.length > 0 ? (
            <div className="mt-6 border-t border-blue-200 pt-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-red-700">Marketplace listings</h3>
              <ul className="mt-2 space-y-3">
                {listings.map((row) => (
                  <li key={row.id} className="rounded border border-blue-200 bg-blue-50/50 px-3 py-2 text-sm">
                    <div className="flex flex-wrap gap-2">
                      {(row.health_badges ?? []).map((b) => (
                        <span key={b} className="rounded bg-white px-1.5 py-0.5 text-xs text-blue-800">
                          {b}
                        </span>
                      ))}
                    </div>
                    <p className="mt-1 font-medium">{row.marketplace_name || row.marketplace}</p>
                    <p>
                      ${row.price.toFixed(2)}
                      {row.shipping_cost > 0 ? ` +$${row.shipping_cost.toFixed(2)} shipping` : null}
                    </p>
                    {row.listing_confidence ? (
                      <p className="text-xs text-blue-700">Confidence: {row.listing_confidence}</p>
                    ) : null}
                    <p>{row.condition || "Condition unknown"}</p>
                    {row.seller_name ? <p>Seller: {row.seller_name}</p> : null}
                    {row.listing_type ? <p className="text-xs text-blue-700">{row.listing_type}</p> : null}
                    {row.is_active && row.health_status === "ACTIVE" ? (
                      <a
                        href={row.listing_url}
                        className="mt-2 inline-block rounded-md bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-800"
                        target="_blank"
                        rel="noreferrer"
                      >
                        View Marketplace Listing
                      </a>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : listingSafe ? (
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

          {sources.length > 0 ? (
            <div className="mt-6 border-t border-blue-200 pt-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-red-700">Marketplace sources</h3>
              <ul className="mt-2 space-y-3">
                {sources.map((source) => (
                  <li key={source.id} className="rounded border border-blue-200 bg-blue-50/50 px-3 py-2 text-sm">
                    <p>
                      <span className="font-medium">Marketplace:</span> {source.marketplace_display_name}
                    </p>
                    <p>
                      <span className="font-medium">Source:</span> {sourceTypeLabel(source.source_type)}
                    </p>
                    <p>
                      <span className="font-medium">URL:</span>{" "}
                      <a
                        href={source.source_url}
                        className="text-red-700 hover:underline"
                        target="_blank"
                        rel="noreferrer"
                      >
                        {source.source_url}
                      </a>
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </PatriotPanel>
      ) : null}
      {opp ? (
        <ImportMarketplaceUrlModal
          open={importOpen}
          onClose={() => setImportOpen(false)}
          opportunityId={opp.id}
          onSuccess={() => void load()}
        />
      ) : null}
    </PatriotPageLayout>
  );
}
