import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P89ListingDraftRead } from "../api/client";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { PatriotPageLayout } from "../components/PatriotPageLayout";

function money(value: number | null | undefined): string {
  if (value == null) return "Pricing unavailable.";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function DraftCard({
  draft,
  onArchive,
}: {
  draft: P89ListingDraftRead;
  onArchive: (id: number) => void;
}): JSX.Element {
  return (
    <article className="rounded-lg border border-blue-800 bg-white px-4 py-4 text-blue-950 shadow-sm">
      <div className="flex flex-wrap justify-between gap-2">
        <div>
          <h3 className="font-semibold">{draft.comic_title || draft.title}</h3>
          <p className="text-xs uppercase tracking-wide text-red-700">{draft.marketplace}</p>
        </div>
        <p className="text-sm font-medium">{money(draft.suggested_price)}</p>
      </div>
      <p className="mt-2 text-xs text-blue-800">
        Status: {draft.status} · Created {new Date(draft.created_at).toLocaleDateString()}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={`/listing-drafts/${draft.id}`}
          className="rounded-md border border-blue-800 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-50"
        >
          Review Draft
        </Link>
        {draft.status !== "ARCHIVED" ? (
          <button
            type="button"
            className="rounded-md border border-slate-400 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-50"
            onClick={() => onArchive(draft.id)}
          >
            Archive
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function ListingDraftsPage(): JSX.Element {
  const [items, setItems] = useState<P89ListingDraftRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.listListingDrafts({ limit: 100 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load listing drafts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => {
    return {
      DRAFT: items.filter((i) => i.status === "DRAFT"),
      REVIEWED: items.filter((i) => i.status === "REVIEWED"),
      ARCHIVED: items.filter((i) => i.status === "ARCHIVED"),
    };
  }, [items]);

  async function archive(id: number) {
    await apiClient.patchListingDraft(id, { status: "ARCHIVED" });
    await load();
  }

  return (
    <PatriotPageLayout
      eyebrow="Sell"
      title="Listing Drafts"
      description="Copy-ready marketplace listing drafts — review and paste into your marketplace; ComicOS does not post listings."
      showExpansionNav
      error={error}
      onRetry={() => void load()}
    >
      {loading ? <p className="text-sm text-blue-100">Loading…</p> : null}
      {!loading && items.length === 0 ? (
        <CollectorEmptyState
          title="No listing drafts yet."
          description="Generate a draft from Sell Candidates or Market Pricing when you are ready to list a book."
        />
      ) : null}
      {!loading && items.length > 0 ? (
        <div className="space-y-10">
          {(
            [
              ["Drafts", grouped.DRAFT],
              ["Reviewed", grouped.REVIEWED],
              ["Archived", grouped.ARCHIVED],
            ] as const
          ).map(([label, rows]) =>
            rows.length === 0 ? null : (
              <section key={label}>
                <h2 className="mb-3 text-lg font-semibold text-white">{label}</h2>
                <ul className="space-y-4">
                  {rows.map((draft) => (
                    <li key={draft.id}>
                      <DraftCard draft={draft} onArchive={(id) => void archive(id)} />
                    </li>
                  ))}
                </ul>
              </section>
            ),
          )}
        </div>
      ) : null}
    </PatriotPageLayout>
  );
}
