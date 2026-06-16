import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type CatalogUniverseIssueNode,
  type CatalogUniversePublisherNode,
  type CatalogUniverseSummary,
  type CatalogUniverseVolumeNode,
} from "../api/client";
import { AppShell } from "../components/AppShell";

function statusBadge(status: CatalogUniverseIssueNode["catalog_status"]): JSX.Element {
  if (status === "CATALOGED") {
    return (
      <span className="rounded-full bg-emerald-900/60 px-2 py-0.5 text-xs font-medium text-emerald-200">
        Cataloged
      </span>
    );
  }
  if (status === "DISCOVERED") {
    return (
      <span className="rounded-full bg-sky-900/60 px-2 py-0.5 text-xs font-medium text-sky-200">
        Discovered
      </span>
    );
  }
  return (
    <span className="rounded-full bg-amber-900/60 px-2 py-0.5 text-xs font-medium text-amber-200">
      Placeholder Eligible
    </span>
  );
}

function SummaryCards({ summary }: { summary: CatalogUniverseSummary | null }): JSX.Element | null {
  if (!summary) return null;
  const cards = [
    { label: "Publishers", value: summary.total_publishers },
    { label: "Volumes", value: summary.total_volumes },
    { label: "Issues (universe)", value: summary.total_issues },
    { label: "Cataloged", value: summary.cataloged_issues },
    { label: "Discovered only", value: summary.discovered_only_issues },
  ];
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
          <p className="text-xs uppercase tracking-wide text-slate-500">{card.label}</p>
          <p className="text-lg font-semibold text-white">{card.value.toLocaleString()}</p>
        </div>
      ))}
    </div>
  );
}

export function CatalogUniversePage(): JSX.Element {
  const [summary, setSummary] = useState<CatalogUniverseSummary | null>(null);
  const [publishers, setPublishers] = useState<CatalogUniversePublisherNode[]>([]);
  const [volumes, setVolumes] = useState<CatalogUniverseVolumeNode[]>([]);
  const [issues, setIssues] = useState<CatalogUniverseIssueNode[]>([]);
  const [selectedPublisher, setSelectedPublisher] = useState<string | null>(null);
  const [selectedVolume, setSelectedVolume] = useState<CatalogUniverseVolumeNode | null>(null);
  const [publisherSearch, setPublisherSearch] = useState("");
  const [seriesSearch, setSeriesSearch] = useState("");
  const [issueFilter, setIssueFilter] = useState("");
  const [loadingPublishers, setLoadingPublishers] = useState(true);
  const [loadingVolumes, setLoadingVolumes] = useState(false);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPublishers = useCallback(async (search: string) => {
    setLoadingPublishers(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogUniversePublishers(search || undefined);
      setPublishers(resp.items);
      setSummary(resp.summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load publishers.");
    } finally {
      setLoadingPublishers(false);
    }
  }, []);

  const loadVolumes = useCallback(async (publisher: string, search: string) => {
    setLoadingVolumes(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogUniverseVolumes(publisher, search || undefined);
      setVolumes(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load volumes.");
    } finally {
      setLoadingVolumes(false);
    }
  }, []);

  const loadIssues = useCallback(async (volumeId: number, issueNumber: string) => {
    setLoadingIssues(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogUniverseIssues(
        volumeId,
        issueNumber || undefined,
      );
      setIssues(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load issues.");
    } finally {
      setLoadingIssues(false);
    }
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void loadPublishers(publisherSearch);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [loadPublishers, publisherSearch]);

  useEffect(() => {
    if (!selectedPublisher) {
      setVolumes([]);
      return;
    }
    const handle = window.setTimeout(() => {
      void loadVolumes(selectedPublisher, seriesSearch);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [loadVolumes, selectedPublisher, seriesSearch]);

  useEffect(() => {
    if (!selectedVolume) {
      setIssues([]);
      return;
    }
    const handle = window.setTimeout(() => {
      void loadIssues(selectedVolume.volume_id, issueFilter);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [issueFilter, loadIssues, selectedVolume]);

  const volumeSubtitle = useMemo(() => {
    if (!selectedVolume) return null;
    const parts = [
      selectedVolume.start_year ? String(selectedVolume.start_year) : null,
      selectedVolume.comicvine_volume_id ? `CV ${selectedVolume.comicvine_volume_id}` : null,
      `${selectedVolume.catalog_issue_count} cataloged`,
    ].filter(Boolean);
    return parts.join(" · ");
  }, [selectedVolume]);

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto max-w-[1400px] px-4 py-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Catalog</p>
          <h1 className="mt-2 text-2xl font-semibold text-white">Universe Tree</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Text-only Publisher → Series/Volume → Issue browser from local ComicOS data. No live ComicVine calls.
          </p>

          {error ? (
            <div className="mt-4 rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          ) : null}

          <SummaryCards summary={summary} />

          <div className="mt-6 grid min-h-[480px] gap-4 lg:grid-cols-3">
            <section className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/40">
              <header className="border-b border-slate-800 px-3 py-2">
                <h2 className="text-sm font-semibold text-white">Publishers</h2>
                <input
                  aria-label="Search publishers"
                  value={publisherSearch}
                  onChange={(e) => setPublisherSearch(e.target.value)}
                  placeholder="Search publishers…"
                  className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white"
                />
              </header>
              <ul className="flex-1 overflow-y-auto p-2">
                {loadingPublishers ? (
                  <li className="px-2 py-3 text-sm text-slate-500">Loading…</li>
                ) : (
                  publishers.map((row) => (
                    <li key={row.publisher}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedPublisher(row.publisher);
                          setSelectedVolume(null);
                          setSeriesSearch("");
                          setIssueFilter("");
                        }}
                        className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                          selectedPublisher === row.publisher
                            ? "bg-emerald-900/50 text-white"
                            : "text-slate-200 hover:bg-slate-800"
                        }`}
                      >
                        <div className="font-medium">{row.publisher}</div>
                        <div className="text-xs text-slate-400">
                          {row.volume_count} vol · {row.issue_count.toLocaleString()} issues
                        </div>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </section>

            <section className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/40">
              <header className="border-b border-slate-800 px-3 py-2">
                <h2 className="text-sm font-semibold text-white">Series / Volumes</h2>
                <input
                  aria-label="Search series"
                  value={seriesSearch}
                  onChange={(e) => setSeriesSearch(e.target.value)}
                  placeholder="Search series…"
                  disabled={!selectedPublisher}
                  className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white disabled:opacity-50"
                />
              </header>
              <ul className="flex-1 overflow-y-auto p-2">
                {!selectedPublisher ? (
                  <li className="px-2 py-3 text-sm text-slate-500">Select a publisher</li>
                ) : loadingVolumes ? (
                  <li className="px-2 py-3 text-sm text-slate-500">Loading…</li>
                ) : (
                  volumes.map((row) => (
                    <li key={row.volume_id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedVolume(row);
                          setIssueFilter("");
                        }}
                        className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                          selectedVolume?.volume_id === row.volume_id
                            ? "bg-emerald-900/50 text-white"
                            : "text-slate-200 hover:bg-slate-800"
                        }`}
                      >
                        <div className="font-medium">{row.title}</div>
                        <div className="text-xs text-slate-400">
                          {row.catalog_issue_count}/{row.issue_count} in catalog
                          {row.missing_issue_count != null ? ` · ${row.missing_issue_count} missing` : ""}
                        </div>
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </section>

            <section className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/40">
              <header className="border-b border-slate-800 px-3 py-2">
                <h2 className="text-sm font-semibold text-white">Issues</h2>
                {selectedVolume ? (
                  <p className="mt-1 text-xs text-slate-400">{volumeSubtitle}</p>
                ) : null}
                <input
                  aria-label="Filter issue number"
                  value={issueFilter}
                  onChange={(e) => setIssueFilter(e.target.value)}
                  placeholder="Filter issue #…"
                  disabled={!selectedVolume}
                  className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white disabled:opacity-50"
                />
              </header>
              <ul className="flex-1 overflow-y-auto p-2">
                {!selectedVolume ? (
                  <li className="px-2 py-3 text-sm text-slate-500">Select a volume</li>
                ) : loadingIssues ? (
                  <li className="px-2 py-3 text-sm text-slate-500">Loading…</li>
                ) : issues.length === 0 ? (
                  <li className="px-2 py-3 text-sm text-slate-500">No catalog issues loaded for this volume yet.</li>
                ) : (
                  issues.map((row) => (
                    <li
                      key={`${row.issue_number}-${row.catalog_issue_id ?? "x"}`}
                      className="mb-2 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold text-white">#{row.issue_number}</span>
                        {statusBadge(row.catalog_status)}
                      </div>
                      {row.issue_title ? (
                        <p className="mt-1 text-sm text-slate-300">{row.issue_title}</p>
                      ) : null}
                      {row.release_date ? (
                        <p className="mt-1 text-xs text-slate-500">Release {row.release_date}</p>
                      ) : null}
                    </li>
                  ))
                )}
              </ul>
            </section>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
