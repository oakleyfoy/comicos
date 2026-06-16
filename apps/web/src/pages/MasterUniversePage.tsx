import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type MasterUniverseIssueNode,
  type MasterUniversePublisherNode,
  type MasterUniverseSummary,
  type MasterUniverseVariantNode,
  type MasterUniverseVolumeNode,
} from "../api/client";
import { AppShell } from "../components/AppShell";

function statusBadge(status: string): JSX.Element {
  if (status === "CATALOGED") {
    return (
      <span className="rounded-full bg-emerald-900/60 px-2 py-0.5 text-xs font-medium text-emerald-200">
        Cataloged
      </span>
    );
  }
  return (
    <span className="rounded-full bg-sky-900/60 px-2 py-0.5 text-xs font-medium text-sky-200">
      Discovered
    </span>
  );
}

function variantBadge(node: MasterUniverseVariantNode): JSX.Element {
  if (node.is_unknown_shell) {
    return (
      <span className="rounded-full bg-amber-900/60 px-2 py-0.5 text-xs font-medium text-amber-200">
        Unknown variant
      </span>
    );
  }
  return statusBadge(node.status);
}

export function MasterUniversePage(): JSX.Element {
  const [summary, setSummary] = useState<MasterUniverseSummary | null>(null);
  const [publishers, setPublishers] = useState<MasterUniversePublisherNode[]>([]);
  const [volumes, setVolumes] = useState<MasterUniverseVolumeNode[]>([]);
  const [issues, setIssues] = useState<MasterUniverseIssueNode[]>([]);
  const [variants, setVariants] = useState<MasterUniverseVariantNode[]>([]);
  const [selectedPublisher, setSelectedPublisher] = useState<MasterUniversePublisherNode | null>(null);
  const [selectedVolume, setSelectedVolume] = useState<MasterUniverseVolumeNode | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<MasterUniverseIssueNode | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadPublishers = useCallback(async () => {
    setError(null);
    try {
      const resp = await apiClient.listMasterUniversePublishers(search || undefined);
      setSummary(resp.summary);
      setPublishers(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load publishers.");
    }
  }, [search]);

  useEffect(() => {
    void loadPublishers();
  }, [loadPublishers]);

  const selectPublisher = async (row: MasterUniversePublisherNode) => {
    setSelectedPublisher(row);
    setSelectedVolume(null);
    setSelectedIssue(null);
    setVariants([]);
    setError(null);
    try {
      const resp = await apiClient.listMasterUniverseVolumes(row.id);
      setVolumes(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load volumes.");
    }
  };

  const selectVolume = async (row: MasterUniverseVolumeNode) => {
    setSelectedVolume(row);
    setSelectedIssue(null);
    setVariants([]);
    setError(null);
    try {
      const resp = await apiClient.listMasterUniverseIssues(row.id);
      setIssues(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load issues.");
    }
  };

  const selectIssue = async (row: MasterUniverseIssueNode) => {
    setSelectedIssue(row);
    setError(null);
    try {
      const resp = await apiClient.listMasterUniverseVariants(row.id);
      setVariants(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load variants.");
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-7xl px-4 py-6">
        <header className="mb-4">
          <h1 className="text-2xl font-bold text-white">Master Universe</h1>
          <p className="text-sm text-slate-400">
            Permanent ComicVine reference tree — not catalog, not inventory. Browse publisher → volume → issue →
            variant shells.
          </p>
          {summary ? (
            <p className="mt-2 text-xs text-slate-500">
              {summary.publisher_count.toLocaleString()} publishers · {summary.volume_count.toLocaleString()} volumes ·{" "}
              {summary.issue_count.toLocaleString()} issues · {summary.variant_count.toLocaleString()} variants
            </p>
          ) : null}
        </header>

        <div className="mb-4">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search publishers"
            className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
          />
        </div>

        {error ? (
          <p role="alert" className="mb-4 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
            {error}
          </p>
        ) : null}

        <div className="grid min-h-[420px] grid-cols-1 gap-3 lg:grid-cols-4">
          <section className="rounded-xl border border-slate-800 bg-slate-950/50">
            <h2 className="border-b border-slate-800 px-3 py-2 text-sm font-semibold text-white">Publishers</h2>
            <ul className="max-h-[480px] overflow-y-auto p-2">
              {publishers.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    onClick={() => void selectPublisher(row)}
                    className={`mb-1 w-full rounded-lg px-2 py-2 text-left text-sm ${
                      selectedPublisher?.id === row.id ? "bg-sky-900/50 text-white" : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {row.name}
                    <span className="block text-xs text-slate-500">{row.volume_count} vol · {row.issue_count} iss</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-950/50">
            <h2 className="border-b border-slate-800 px-3 py-2 text-sm font-semibold text-white">Volumes</h2>
            <ul className="max-h-[480px] overflow-y-auto p-2">
              {volumes.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    onClick={() => void selectVolume(row)}
                    className={`mb-1 w-full rounded-lg px-2 py-2 text-left text-sm ${
                      selectedVolume?.id === row.id ? "bg-sky-900/50 text-white" : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {row.start_year ? `${row.name} (${row.start_year})` : row.name}
                    <span className="block text-xs text-slate-500">{row.issue_shell_count} issue shells</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-950/50">
            <h2 className="border-b border-slate-800 px-3 py-2 text-sm font-semibold text-white">Issues</h2>
            <ul className="max-h-[480px] overflow-y-auto p-2">
              {issues.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    onClick={() => void selectIssue(row)}
                    className={`mb-1 flex w-full items-center justify-between gap-2 rounded-lg px-2 py-2 text-left text-sm ${
                      selectedIssue?.id === row.id ? "bg-sky-900/50 text-white" : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    <span>
                      #{row.issue_number}
                      {row.issue_title ? ` — ${row.issue_title}` : ""}
                    </span>
                    {statusBadge(row.status)}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-slate-800 bg-slate-950/50">
            <h2 className="border-b border-slate-800 px-3 py-2 text-sm font-semibold text-white">Variants</h2>
            <ul className="max-h-[480px] overflow-y-auto p-2">
              {variants.map((row) => (
                <li
                  key={row.id}
                  className="mb-2 rounded-lg border border-slate-800 bg-slate-900/40 px-2 py-2 text-sm text-slate-200"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{row.variant_name || row.variant_type}</span>
                    {variantBadge(row)}
                  </div>
                  <p className="text-xs text-slate-500">{row.variant_type}</p>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
