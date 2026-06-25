import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MasterUniverseCatalogDashboardResponse,
  type MasterUniverseCatalogDashboardSummary,
  type MasterUniverseIssueNode,
  type MasterUniversePublisherNode,
  type MasterUniverseVariantNode,
  type MasterUniverseVolumeNode,
} from "../api/client";
import { AppShell } from "../components/AppShell";

function SummaryGrid({ summary }: { summary: MasterUniverseCatalogDashboardSummary }): JSX.Element {
  const cards: { label: string; value: string; hint?: string }[] = [
    {
      label: "Your copies",
      value: summary.inventory_copy_count.toLocaleString(),
      hint: `${summary.inventory_linked_to_catalog.toLocaleString()} linked · ${summary.inventory_unlinked.toLocaleString()} unlinked`,
    },
    {
      label: "Catalog issues",
      value: summary.catalog_issue_count.toLocaleString(),
      hint: `${summary.catalog_series_count.toLocaleString()} series in ComicOS catalog`,
    },
    {
      label: "Universe ceiling",
      value: summary.universe_issue_ceiling.toLocaleString(),
      hint: `${summary.universe_volume_count.toLocaleString()} ComicVine volumes discovered`,
    },
    {
      label: "Missing from catalog",
      value: summary.missing_catalog_issues.toLocaleString(),
      hint: "Rough gap vs universe ceiling",
    },
    {
      label: "Catalog sources",
      value: [
        summary.catalog_source_counts.comicvine > 0 ? `CV ${summary.catalog_source_counts.comicvine}` : null,
        summary.catalog_source_counts.gcd > 0 ? `GCD ${summary.catalog_source_counts.gcd}` : null,
        summary.catalog_source_counts.other > 0 ? `Other ${summary.catalog_source_counts.other}` : null,
        summary.catalog_source_counts.unknown > 0 ? `Unknown ${summary.catalog_source_counts.unknown}` : null,
      ]
        .filter(Boolean)
        .join(" · ") || "—",
      hint: "From catalog_issue external_source_ids",
    },
    {
      label: "Reference tree (P98)",
      value: `${summary.reference_tree_issues.toLocaleString()} shells`,
      hint: `${summary.reference_tree_publishers} publishers · ${summary.reference_tree_variants} variant shells`,
    },
  ];

  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((card) => (
        <div key={card.label} className="rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{card.label}</p>
          <p className="mt-1 text-2xl font-semibold text-white">{card.value}</p>
          {card.hint ? <p className="mt-1 text-xs text-slate-400">{card.hint}</p> : null}
        </div>
      ))}
    </div>
  );
}

function CoverageTable(props: {
  dashboard: MasterUniverseCatalogDashboardResponse;
  search: string;
  onSearchChange: (value: string) => void;
}): JSX.Element {
  const { dashboard, search, onSearchChange } = props;

  return (
    <section className="mt-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Publisher coverage</h2>
          <p className="text-sm text-slate-400">
            What ComicOS knows in catalog, what ComicVine discovery expects, and what you own.
          </p>
        </div>
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Filter publishers…"
          className="w-full max-w-xs rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
          aria-label="Filter publishers"
        />
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-2">Publisher</th>
              <th className="px-3 py-2">Your copies</th>
              <th className="px-3 py-2">Catalog issues</th>
              <th className="px-3 py-2">Series</th>
              <th className="px-3 py-2">Universe ceiling</th>
              <th className="px-3 py-2">Missing catalog</th>
              <th className="px-3 py-2">CV volumes</th>
              <th className="px-3 py-2">Primary source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-950/40 text-slate-200">
            {dashboard.rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-slate-500">
                  No publisher rows yet. Import catalog data (ComicVine / GCD) or add comics to your portfolio.
                </td>
              </tr>
            ) : (
              dashboard.rows.map((row) => (
                <tr key={row.publisher} className="hover:bg-slate-900/60">
                  <td className="px-3 py-2 font-medium text-white">{row.publisher}</td>
                  <td className="px-3 py-2 tabular-nums">{row.inventory_copy_count.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">{row.catalog_issue_count.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">{row.catalog_series_count.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">{row.universe_issue_ceiling.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums text-amber-200/90">
                    {row.missing_catalog_issues > 0 ? row.missing_catalog_issues.toLocaleString() : "—"}
                  </td>
                  <td className="px-3 py-2 tabular-nums">{row.universe_volume_count.toLocaleString()}</td>
                  <td className="px-3 py-2 text-slate-400">{row.primary_catalog_source ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Showing {dashboard.rows.length.toLocaleString()} of {dashboard.total_count.toLocaleString()} publishers
      </p>
    </section>
  );
}

function ReferenceTreePanel(): JSX.Element {
  const [publishers, setPublishers] = useState<MasterUniversePublisherNode[]>([]);
  const [volumes, setVolumes] = useState<MasterUniverseVolumeNode[]>([]);
  const [issues, setIssues] = useState<MasterUniverseIssueNode[]>([]);
  const [variants, setVariants] = useState<MasterUniverseVariantNode[]>([]);
  const [selectedPublisher, setSelectedPublisher] = useState<MasterUniversePublisherNode | null>(null);
  const [selectedVolume, setSelectedVolume] = useState<MasterUniverseVolumeNode | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiClient.listMasterUniversePublishers(undefined, 80, 0).then(
      (resp) => setPublishers(resp.items),
      (err) => setError(err instanceof ApiError ? err.message : "Could not load reference tree."),
    );
  }, []);

  const selectPublisher = async (row: MasterUniversePublisherNode) => {
    setSelectedPublisher(row);
    setSelectedVolume(null);
    setIssues([]);
    setVariants([]);
    try {
      const resp = await apiClient.listMasterUniverseVolumes(row.id);
      setVolumes(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load volumes.");
    }
  };

  const selectVolume = async (row: MasterUniverseVolumeNode) => {
    setSelectedVolume(row);
    setVariants([]);
    try {
      const resp = await apiClient.listMasterUniverseIssues(row.id);
      setIssues(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load issues.");
    }
  };

  const selectIssue = async (row: MasterUniverseIssueNode) => {
    try {
      const resp = await apiClient.listMasterUniverseVariants(row.id);
      setVariants(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load variants.");
    }
  };

  return (
    <section className="mt-10 rounded-xl border border-slate-800 bg-slate-950/30 p-4">
      <h2 className="text-sm font-semibold text-white">P98 reference tree (variant shells)</h2>
      <p className="mt-1 text-xs text-slate-500">
        Separate from your catalog DB — populated when universe build jobs run. Use{" "}
        <Link to="/catalog-universe" className="text-sky-400 hover:underline">Universe Tree</Link> to browse catalog +
        discovery.
      </p>
      {error ? <p className="mt-2 text-sm text-rose-300">{error}</p> : null}
      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-4">
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 p-2 text-sm">
          {publishers.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => void selectPublisher(row)}
                className="w-full rounded px-2 py-1 text-left text-slate-200 hover:bg-slate-800"
              >
                {row.name}
              </button>
            </li>
          ))}
        </ul>
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 p-2 text-sm">
          {volumes.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => void selectVolume(row)}
                className="w-full rounded px-2 py-1 text-left text-slate-200 hover:bg-slate-800"
              >
                {row.name}
              </button>
            </li>
          ))}
        </ul>
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 p-2 text-sm">
          {issues.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => void selectIssue(row)}
                className="w-full rounded px-2 py-1 text-left text-slate-200 hover:bg-slate-800"
              >
                #{row.issue_number}
              </button>
            </li>
          ))}
        </ul>
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 p-2 text-sm text-slate-300">
          {variants.map((row) => (
            <li key={row.id} className="px-2 py-1">
              {row.variant_name || row.variant_type}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function MasterUniversePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<MasterUniverseCatalogDashboardResponse | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDashboard = useCallback(async (filter: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.getMasterUniverseCatalogDashboard(filter || undefined, 150, 0);
      setDashboard(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load catalog dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void loadDashboard(search);
    }, 300);
    return () => window.clearTimeout(handle);
  }, [loadDashboard, search]);

  return (
    <AppShell>
      <div className="mx-auto max-w-7xl px-4 py-6">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Catalog</p>
          <h1 className="mt-2 text-2xl font-bold text-white">Master Universe</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Full catalog command view: what ComicOS has cataloged, what ComicVine discovery expects, what you own, and
            where catalog rows came from (ComicVine, GCD, etc.).
          </p>
          <div className="mt-3 flex flex-wrap gap-3 text-sm">
            <Link to="/catalog-universe" className="font-medium text-sky-400 hover:underline">
              Open Universe Tree browser →
            </Link>
            <Link to="/catalog/import" className="font-medium text-sky-400 hover:underline">
              GCD Import Dashboard →
            </Link>
          </div>
        </header>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">{error}</p>
        ) : null}

        {loading && !dashboard ? (
          <p className="mt-6 text-sm text-slate-500">Loading coverage…</p>
        ) : null}

        {dashboard ? (
          <>
            <SummaryGrid summary={dashboard.summary} />
            <CoverageTable dashboard={dashboard} search={search} onSearchChange={setSearch} />
          </>
        ) : null}

        <ReferenceTreePanel />
      </div>
    </AppShell>
  );
}
