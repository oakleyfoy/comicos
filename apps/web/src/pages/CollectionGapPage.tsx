import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AcquisitionRead,
  type CollectionGapBuilderIssueRow,
  type CollectionGapBuilderPublisherRow,
  type CollectionGapBuilderVolumeRow,
  type CollectionGapYearRow,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

type IssueFilter = "ALL" | "MISSING" | "OWNED" | "PLACEHOLDER_OWNED";

function statusBadge(row: CollectionGapBuilderIssueRow): JSX.Element {
  if (row.gap_status === "OWNED") {
    return <span className="rounded bg-emerald-500/20 px-1.5 text-xs text-emerald-300">Owned</span>;
  }
  if (row.gap_status === "PLACEHOLDER_OWNED") {
    return <span className="rounded bg-sky-500/20 px-1.5 text-xs text-sky-300">Placeholder Owned</span>;
  }
  if (row.gap_status === "SOLD_HISTORY") {
    return <span className="rounded bg-slate-500/20 px-1.5 text-xs text-slate-300">Sold History</span>;
  }
  return <span className="rounded bg-rose-500/20 px-1.5 text-xs text-rose-300">Missing</span>;
}

export function CollectionGapPage(): JSX.Element {
  const [years, setYears] = useState<CollectionGapYearRow[]>([]);
  const [selectedYear, setSelectedYear] = useState(2025);
  const [publishers, setPublishers] = useState<CollectionGapBuilderPublisherRow[]>([]);
  const [selectedPublisher, setSelectedPublisher] = useState<string | null>(null);
  const [volumes, setVolumes] = useState<CollectionGapBuilderVolumeRow[]>([]);
  const [selectedVolume, setSelectedVolume] = useState<CollectionGapBuilderVolumeRow | null>(null);
  const [issues, setIssues] = useState<CollectionGapBuilderIssueRow[]>([]);
  const [selectedIssues, setSelectedIssues] = useState<Set<string>>(new Set());

  const [issueFilter, setIssueFilter] = useState<IssueFilter>("ALL");
  const [priorityOnly, setPriorityOnly] = useState(false);
  const [incompleteOnly, setIncompleteOnly] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [placeholderModal, setPlaceholderModal] = useState(false);
  const [acquisitions, setAcquisitions] = useState<AcquisitionRead[]>([]);
  const [acquisitionId, setAcquisitionId] = useState<number | null>(null);
  const [placeholderIssue, setPlaceholderIssue] = useState<CollectionGapBuilderIssueRow | null>(null);
  const [busy, setBusy] = useState(false);

  const yearSummary = useMemo(
    () => years.find((y) => y.year === selectedYear) ?? null,
    [years, selectedYear],
  );

  const loadYears = useCallback(async () => {
    setError(null);
    const resp = await apiClient.getCollectionGapYears();
    setYears(resp.items);
    setSelectedYear(resp.default_year);
  }, []);

  const loadPublishers = useCallback(async () => {
    if (!selectedYear) return;
    const resp = await apiClient.getCollectionGapPublishers(selectedYear, {
      priority_only: priorityOnly,
      limit: 100,
    });
    setPublishers(resp.items);
  }, [priorityOnly, selectedYear]);

  const loadVolumes = useCallback(async () => {
    if (!selectedPublisher || !selectedYear) return;
    const resp = await apiClient.getCollectionGapVolumes(selectedPublisher, selectedYear, {
      incomplete_only: incompleteOnly,
      limit: 100,
    });
    setVolumes(resp.items);
  }, [incompleteOnly, selectedPublisher, selectedYear]);

  const loadIssues = useCallback(async () => {
    if (!selectedVolume || !selectedYear) return;
    const gapStatus =
      issueFilter === "MISSING"
        ? "MISSING"
        : issueFilter === "OWNED"
          ? "OWNED"
          : issueFilter === "PLACEHOLDER_OWNED"
            ? "PLACEHOLDER_OWNED"
            : undefined;
    const resp = await apiClient.getCollectionGapIssues(selectedVolume.volume_id, selectedYear, {
      gap_status: gapStatus,
      limit: 200,
    });
    setIssues(resp.items);
    setSelectedIssues(new Set());
  }, [issueFilter, selectedVolume, selectedYear]);

  useEffect(() => {
    setLoading(true);
    void loadYears()
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load years."))
      .finally(() => setLoading(false));
  }, [loadYears]);

  useEffect(() => {
    void loadPublishers().catch((err) =>
      setError(err instanceof ApiError ? err.message : "Could not load publishers."),
    );
  }, [loadPublishers]);

  useEffect(() => {
    if (!selectedPublisher) {
      setVolumes([]);
      return;
    }
    void loadVolumes().catch((err) =>
      setError(err instanceof ApiError ? err.message : "Could not load volumes."),
    );
  }, [loadVolumes, selectedPublisher]);

  useEffect(() => {
    if (!selectedVolume) {
      setIssues([]);
      return;
    }
    void loadIssues().catch((err) =>
      setError(err instanceof ApiError ? err.message : "Could not load issues."),
    );
  }, [loadIssues, selectedVolume]);

  const toggleIssue = (issueNumber: string) => {
    setSelectedIssues((prev) => {
      const next = new Set(prev);
      if (next.has(issueNumber)) next.delete(issueNumber);
      else next.add(issueNumber);
      return next;
    });
  };

  const createWantListTargets = async () => {
    if (!selectedPublisher || !selectedVolume || selectedIssues.size === 0) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const targets = issues
        .filter((row) => selectedIssues.has(row.issue_number) && row.gap_status === "MISSING")
        .map((row) => ({
          publisher: selectedPublisher,
          series_title: selectedVolume.title,
          volume_id: selectedVolume.volume_id,
          issue_number: row.issue_number,
          catalog_issue_id: row.catalog_issue_id,
        }));
      const resp = await apiClient.createCollectionGapWantListTargets({ targets });
      setMessage(`Created ${resp.created_count} want-list targets (${resp.skipped_duplicates} skipped).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create want-list targets.");
    } finally {
      setBusy(false);
    }
  };

  const openPlaceholderFlow = async (row: CollectionGapBuilderIssueRow) => {
    if (!selectedPublisher || !selectedVolume) return;
    setPlaceholderIssue(row);
    setPlaceholderModal(true);
    setBusy(true);
    try {
      const resp = await apiClient.listAcquisitions({ status: "OPEN" });
      setAcquisitions(resp.items.filter((a) => a.status === "OPEN"));
      setAcquisitionId(resp.items[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load acquisitions.");
      setPlaceholderModal(false);
    } finally {
      setBusy(false);
    }
  };

  const createAcquisitionPlaceholder = async () => {
    if (!acquisitionId || !selectedPublisher || !selectedVolume || !placeholderIssue) return;
    setBusy(true);
    setError(null);
    try {
      if (placeholderIssue.catalog_issue_id) {
        await apiClient.addAcquisitionItems(acquisitionId, {
          items: [{ catalog_issue_id: placeholderIssue.catalog_issue_id, quantity: 1 }],
        });
      } else {
        await apiClient.createTreePlaceholderIssue(acquisitionId, {
          publisher: selectedPublisher,
          volume_id: selectedVolume.volume_id,
          issue_number: placeholderIssue.issue_number,
          quantity: 1,
          issue_title: placeholderIssue.issue_title,
        });
      }
      setMessage("Added to acquisition.");
      setPlaceholderModal(false);
      await loadIssues();
      await loadYears();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add to acquisition.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Universe tree + inventory"
        title="Collection Gap Builder"
        description="Browse release years from 2025 downward, compare owned vs missing issues, and send gaps to want lists or acquisitions (local DB only)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">
          Release year
          <select
            aria-label="Release year"
            value={selectedYear}
            onChange={(e) => {
              setSelectedYear(Number(e.target.value));
              setSelectedPublisher(null);
              setSelectedVolume(null);
            }}
            className="mt-1 block rounded-lg border border-white/10 bg-slate-900 px-2 py-1.5 text-sm text-white"
          >
            {years.map((y) => (
              <option key={y.year} value={y.year}>
                {y.year}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={priorityOnly}
            onChange={(e) => setPriorityOnly(e.target.checked)}
          />
          Publisher priority only
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={incompleteOnly}
            onChange={(e) => setIncompleteOnly(e.target.checked)}
          />
          Completion &lt; 100%
        </label>
      </div>

      {yearSummary ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          {[
            { label: "Total issues", value: yearSummary.total_issues },
            { label: "Owned", value: yearSummary.owned_issues },
            { label: "Missing", value: yearSummary.missing_issues },
            { label: "Completion %", value: `${yearSummary.completion_percent.toFixed(1)}%` },
          ].map((card) => (
            <div key={card.label} className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
              <p className="text-xs uppercase text-slate-500">{card.label}</p>
              <p className="text-lg font-semibold text-white">{card.value}</p>
            </div>
          ))}
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading…</p>
      ) : (
        <div className="mt-6 grid min-h-[420px] grid-cols-1 gap-3 lg:grid-cols-3">
          <section className="rounded-xl border border-slate-800 bg-slate-950/50">
            <h2 className="border-b border-slate-800 px-3 py-2 text-sm font-medium text-slate-300">Publishers</h2>
            <ul className="max-h-[480px] overflow-y-auto p-2">
              {publishers.map((row) => (
                <li key={row.publisher}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedPublisher(row.publisher);
                      setSelectedVolume(null);
                    }}
                    className={`mb-1 w-full rounded-lg px-2 py-2 text-left text-sm ${
                      selectedPublisher === row.publisher ? "bg-sky-900/40 text-white" : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {row.publisher}
                    <span className="ml-2 text-xs text-slate-500">
                      {row.owned_issues}/{row.total_issues} · {row.completion_percent.toFixed(0)}%
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-950/50">
            <h2 className="border-b border-slate-800 px-3 py-2 text-sm font-medium text-slate-300">Volumes</h2>
            <ul className="max-h-[480px] overflow-y-auto p-2">
              {volumes.map((row) => (
                <li key={row.volume_id}>
                  <button
                    type="button"
                    onClick={() => setSelectedVolume(row)}
                    className={`mb-1 w-full rounded-lg px-2 py-2 text-left text-sm ${
                      selectedVolume?.volume_id === row.volume_id
                        ? "bg-sky-900/40 text-white"
                        : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {row.title}
                    {row.start_year ? ` (${row.start_year})` : ""}
                    <span className="ml-2 text-xs text-slate-500">
                      {row.owned_count}/{row.issue_count_in_year} in {selectedYear}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-950/50">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
              <h2 className="text-sm font-medium text-slate-300">Issues</h2>
              <select
                aria-label="Issue filter"
                value={issueFilter}
                onChange={(e) => setIssueFilter(e.target.value as IssueFilter)}
                className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-white"
              >
                <option value="ALL">All</option>
                <option value="MISSING">Missing only</option>
                <option value="OWNED">Owned only</option>
                <option value="PLACEHOLDER_OWNED">Placeholder owned</option>
              </select>
            </div>
            <ul className="max-h-[400px] overflow-y-auto p-2">
              {issues.map((row) => (
                <li
                  key={row.issue_number}
                  className="mb-1 flex flex-wrap items-center gap-2 rounded-lg border border-slate-800/80 px-2 py-2 text-sm"
                >
                  {row.gap_status === "MISSING" ? (
                    <input
                      aria-label={`Select issue ${row.issue_number}`}
                      type="checkbox"
                      checked={selectedIssues.has(row.issue_number)}
                      onChange={() => toggleIssue(row.issue_number)}
                    />
                  ) : null}
                  <span className="font-medium text-white">#{row.issue_number}</span>
                  <span className="text-xs text-slate-500">{row.release_date ?? "—"}</span>
                  {statusBadge(row)}
                  {row.gap_status === "MISSING" ? (
                    <button
                      type="button"
                      onClick={() => void openPlaceholderFlow(row)}
                      className="ml-auto text-xs text-sky-400 hover:underline"
                    >
                      Create placeholder
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2 border-t border-slate-800 p-3">
              <button
                type="button"
                disabled={busy || selectedIssues.size === 0}
                onClick={() => void createWantListTargets()}
                className="rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
              >
                Create Want List Targets ({selectedIssues.size})
              </button>
              <Link to="/catalog-universe" className="text-xs text-slate-400 hover:text-sky-300">
                Universe Tree
              </Link>
            </div>
          </section>
        </div>
      )}

      {placeholderModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div role="dialog" aria-label="Add to acquisition" className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-950 p-4">
            <h3 className="text-lg font-semibold text-white">Add to acquisition</h3>
            <p className="mt-1 text-sm text-slate-400">
              #{placeholderIssue?.issue_number} — {selectedVolume?.title}
            </p>
            <label className="mt-3 block text-xs text-slate-400">
              Open acquisition
              <select
                value={acquisitionId ?? ""}
                onChange={(e) => setAcquisitionId(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white"
              >
                {acquisitions.map((a) => (
                  <option key={a.id} value={a.id}>
                    #{a.id} {a.seller_name ?? a.acquisition_type}
                  </option>
                ))}
              </select>
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setPlaceholderModal(false)} className="text-sm text-slate-400">
                Cancel
              </button>
              <button
                type="button"
                disabled={busy || !acquisitionId}
                onClick={() => void createAcquisitionPlaceholder()}
                className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
