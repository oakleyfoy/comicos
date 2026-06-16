import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type PlaceholderMatchCandidate,
  type PlaceholderQueueItem,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";

const PAGE_SIZE = 50;

export function PlaceholderMatchQueuePage(): JSX.Element {
  const [items, setItems] = useState<PlaceholderQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<PlaceholderQueueItem | null>(null);
  const [candidates, setCandidates] = useState<PlaceholderMatchCandidate[]>([]);
  const [manualSearch, setManualSearch] = useState("");
  const [placeholderLabel, setPlaceholderLabel] = useState("");
  const [linkBusy, setLinkBusy] = useState(false);
  const [linkMessage, setLinkMessage] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogUniversePlaceholders({
        search: search || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setItems(resp.items);
      setTotal(resp.total_count);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load placeholders.");
    } finally {
      setLoading(false);
    }
  }, [offset, search]);

  useEffect(() => {
    const t = window.setTimeout(() => void loadQueue(), 250);
    return () => window.clearTimeout(t);
  }, [loadQueue]);

  const loadCandidates = useCallback(
    async (row: PlaceholderQueueItem, q?: string) => {
      setLinkMessage(null);
      setLinkBusy(true);
      try {
        const resp = await apiClient.listPlaceholderMatchCandidates(row.placeholder_issue_id, {
          q: q || undefined,
        });
        setPlaceholderLabel(resp.placeholder_label);
        setCandidates(resp.candidates);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not load match candidates.");
        setCandidates([]);
      } finally {
        setLinkBusy(false);
      }
    },
    [],
  );

  const selectRow = (row: PlaceholderQueueItem) => {
    setSelected(row);
    setManualSearch("");
    void loadCandidates(row);
  };

  const linkToCatalog = async (catalogIssueId: number) => {
    if (!selected) return;
    setLinkBusy(true);
    setLinkMessage(null);
    try {
      const resp = await apiClient.linkCatalogPlaceholder(selected.placeholder_issue_id, catalogIssueId);
      setLinkMessage(
        `Linked to catalog issue #${resp.catalog_issue_id}. Updated ${resp.inventory_copies_updated} inventory cop${resp.inventory_copies_updated === 1 ? "y" : "ies"}.`,
      );
      setSelected(null);
      setCandidates([]);
      await loadQueue();
    } catch (err) {
      setLinkMessage(err instanceof ApiError ? err.message : "Link failed.");
    } finally {
      setLinkBusy(false);
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageIndex = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Catalog"
        title="Placeholder Match Queue"
        description="Unresolved acquisition placeholders — local catalog matching only."
      />
      <div className="mx-auto max-w-6xl px-4 py-6">
        <p className="mb-4 text-sm text-slate-400">
          <Link to="/catalog-universe" className="text-sky-400 hover:underline">
            Universe Tree
          </Link>
        </p>

        <div className="mb-4 flex flex-wrap gap-3">
          <input
            aria-label="Search placeholders"
            value={search}
            onChange={(e) => {
              setOffset(0);
              setSearch(e.target.value);
            }}
            placeholder="Search publisher, title, issue #"
            className="min-w-[240px] flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
          />
        </div>

        {error ? (
          <p role="alert" className="mb-4 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
            {error}
          </p>
        ) : null}
        {linkMessage ? (
          <p className="mb-4 rounded-lg bg-emerald-500/15 px-3 py-2 text-sm text-emerald-200">{linkMessage}</p>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-800 bg-slate-950/60">
            <div className="border-b border-slate-800 px-3 py-2 text-sm font-medium text-slate-300">
              Unresolved ({total.toLocaleString()})
            </div>
            {loading ? (
              <p className="p-4 text-sm text-slate-500">Loading…</p>
            ) : items.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">No placeholders need catalog matching.</p>
            ) : (
              <ul className="max-h-[520px] divide-y divide-slate-800 overflow-y-auto">
                {items.map((row) => (
                  <li key={row.placeholder_issue_id}>
                    <button
                      type="button"
                      onClick={() => selectRow(row)}
                      className={`w-full px-3 py-3 text-left text-sm hover:bg-slate-900/80 ${
                        selected?.placeholder_issue_id === row.placeholder_issue_id ? "bg-sky-950/40" : ""
                      }`}
                    >
                      <p className="font-medium text-white">
                        {row.publisher || "Unknown"} / {row.title} / #{row.issue_number || "?"}
                        {row.variant_label ? (
                          <span className="ml-1 text-slate-400">({row.variant_label})</span>
                        ) : null}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Qty {row.quantity} · {row.acquisition_type || "Acquisition"} ·{" "}
                        {row.seller_name || "Unknown seller"} ·{" "}
                        {new Date(row.created_at).toLocaleDateString()}
                        {row.tree_linked ? (
                          <span className="ml-2 rounded bg-emerald-500/20 px-1 text-emerald-300">Tree Linked</span>
                        ) : null}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {total > PAGE_SIZE ? (
              <div className="flex items-center justify-between border-t border-slate-800 px-3 py-2 text-xs text-slate-400">
                <button
                  type="button"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  className="rounded border border-slate-700 px-2 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <span>
                  Page {pageIndex} of {pageCount}
                </span>
                <button
                  type="button"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  className="rounded border border-slate-700 px-2 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            ) : null}
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
            {!selected ? (
              <p className="text-sm text-slate-500">Select a placeholder to review suggested catalog matches.</p>
            ) : (
              <>
                <h2 className="text-sm font-semibold text-white">Placeholder</h2>
                <p className="mt-1 text-sm text-slate-300">{placeholderLabel || "…"}</p>

                <div className="mt-4 flex gap-2">
                  <input
                    aria-label="Manual catalog search"
                    value={manualSearch}
                    onChange={(e) => setManualSearch(e.target.value)}
                    placeholder="Search catalog manually"
                    className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white"
                  />
                  <button
                    type="button"
                    disabled={linkBusy}
                    onClick={() => void loadCandidates(selected, manualSearch)}
                    className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:border-sky-400 disabled:opacity-50"
                  >
                    Search
                  </button>
                </div>

                <h3 className="mt-4 text-xs font-medium uppercase tracking-wide text-slate-500">Suggested matches</h3>
                {linkBusy && candidates.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">Loading candidates…</p>
                ) : candidates.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">No candidates — try manual search.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {candidates.map((c) => (
                      <li
                        key={c.catalog_issue_id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2"
                      >
                        <div className="text-sm">
                          <p className="font-medium text-white">
                            {c.series} #{c.issue_number}
                          </p>
                          <p className="text-xs text-slate-500">
                            {c.publisher || "Unknown publisher"} · Status: {c.catalog_status} · Confidence:{" "}
                            {c.confidence}
                          </p>
                        </div>
                        <button
                          type="button"
                          disabled={linkBusy}
                          onClick={() => void linkToCatalog(c.catalog_issue_id)}
                          className="rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
                        >
                          Link to catalog
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-4 text-xs text-slate-500">
                  Linking preserves acquisition cost basis and history. No automatic merge — confirm each link.
                </p>
              </>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}
