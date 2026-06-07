import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiClient, type P89SellCandidateRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { PatriotPageLayout } from "../components/PatriotPageLayout";
import { SellCandidateCard } from "../features/sellCandidates/SellCandidateCard";
import { groupSellCandidatesByRecommendation, type SellCandidateDisplayCard } from "../features/sellCandidates/sellCandidatePresentation";

const SECTIONS: { key: P89SellCandidateRead["recommendation"]; title: string }[] = [
  { key: "SELL_NOW", title: "Sell Now" },
  { key: "GRADE_FIRST", title: "Grade First" },
  { key: "HOLD", title: "Hold" },
  { key: "MONITOR", title: "Monitor" },
];

export function SellCandidatePage(): JSX.Element {
  const [items, setItems] = useState<P89SellCandidateRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [draftLinkId, setDraftLinkId] = useState<number | null>(null);
  const [draftLinkForCandidate, setDraftLinkForCandidate] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getSellCandidates({ limit: 100 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load sell candidates.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => groupSellCandidatesByRecommendation(items), [items]);

  async function onGenerateListingDraft(card: SellCandidateDisplayCard) {
    if (card.recommendation === "GRADE_FIRST") {
      const ok = window.confirm("Consider grading before listing. Generate a listing draft anyway?");
      if (!ok) return;
    }
    try {
      const draft = await apiClient.createListingDraft({
        inventory_copy_id: card.inventoryCopyId,
        sell_candidate_id: card.sellCandidateId,
        marketplace: "EBAY",
      });
      setDraftLinkId(draft.id);
      setDraftLinkForCandidate(card.sellCandidateId);
      setMessage(`Listing draft created.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create listing draft.");
    }
  }

  async function onRefreshCandidates() {
    setGenerating(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.generateSellCandidates();
      setMessage(`Refreshed ${result.candidates} candidate(s).`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to refresh sell candidates.");
    } finally {
      setGenerating(false);
    }
  }

  const showEmpty = !loading && items.length === 0 && !error;

  return (
    <PatriotPageLayout
      eyebrow="Sell"
      title="Sell Candidates"
      description="Books ComicOS believes deserve selling consideration."
      showExpansionNav
      error={error}
      onRetry={() => void load()}
      headerActions={
        <button
          type="button"
          disabled={generating}
          onClick={() => void onRefreshCandidates()}
          className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-blue-50 disabled:opacity-50"
        >
          Refresh candidates
        </button>
      }
    >
      {message ? (
        <p className="mb-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          {message}
        </p>
      ) : null}
      {loading ? <p className="text-sm text-blue-800">Loading…</p> : null}
      {showEmpty ? (
        <CollectorEmptyState
          title="No sell candidates yet."
          description="Add inventory and refresh candidates so ComicOS can rank sell, hold, grade-first, and monitor paths."
        />
      ) : null}
      {!loading && items.length > 0 ? (
        <div className="space-y-10">
          {SECTIONS.map(({ key, title }) => {
            const cards = grouped[key];
            if (cards.length === 0) {
              return null;
            }
            return (
              <section key={key}>
                <h2 className="mb-3 text-lg font-semibold text-white">{title}</h2>
                <ul className="space-y-4">
                  {cards.map((card) => (
                    <li key={card.id}>
                      <SellCandidateCard
                        card={card}
                        onGenerateDraft={(c) => void onGenerateListingDraft(c)}
                        reviewDraftUrl={
                          draftLinkForCandidate === card.sellCandidateId && draftLinkId
                            ? `/listing-drafts/${draftLinkId}`
                            : undefined
                        }
                      />
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      ) : null}
    </PatriotPageLayout>
  );
}
