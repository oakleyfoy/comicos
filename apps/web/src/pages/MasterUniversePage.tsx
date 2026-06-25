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

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }): JSX.Element {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

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
        <StatCard key={card.label} label={card.label} value={card.value} hint={card.hint} />
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
          <h2 className="text-lg font-semibold text-slate-900">Publisher coverage</h2>
          <p className="text-sm text-slate-600">
            What ComicOS knows in catalog, what ComicVine discovery expects, and what you own.
          </p>
        </div>
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Filter publishers…"
          className="w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm"
          aria-label="Filter publishers"
        />
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
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
          <tbody className="divide-y divide-slate-100 text-slate-800">
            {dashboard.rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-slate-500">
                  No publisher rows yet. Import catalog data (ComicVine / GCD) or add comics to your portfolio.
                </td>
              </tr>
            ) : (
              dashboard.rows.map((row) => (
                <tr key={row.publisher} className="hover:bg-slate-50">
                  <td className="px-3 py-2 font-medium text-slate-900">{row.publisher}</td>
                  <td className="px-3 py-2 tabular-nums">{row.inventory_copy_count.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">{row.catalog_issue_count.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">{row.catalog_series_count.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums">{row.universe_issue_ceiling.toLocaleString()}</td>
                  <td className="px-3 py-2 tabular-nums text-amber-800">
                    {row.missing_catalog_issues > 0 ? row.missing_catalog_issues.toLocaleString() : "—"}
                  </td>
                  <td className="px-3 py-2 tabular-nums">{row.universe_volume_count.toLocaleString()}</td>
                  <td className="px-3 py-2 text-slate-600">{row.primary_catalog_source ?? "—"}</td>
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    void apiClient.listMasterUniversePublishers(undefined, 80, 0).then(
      (resp) => {
        setPublishers(resp.items);
        setLoading(false);
      },
      (err) => {
        setError(err instanceof ApiError ? err.message : "Could not load reference tree.");
        setLoading(false);
      },
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

  const emptyTreeMessage =
    loading
      ? "Loading reference tree…"
      : publishers.length === 0
        ? "No P98 reference publishers yet. Universe build jobs populate this tree; use Universe Tree for live catalog browsing."
        : "Select a publisher to drill down.";

  return (
    <section className="mt-10 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">P98 reference tree (variant shells)</h2>
      <p className="mt-1 text-xs text-slate-600">
        Separate from your catalog DB — populated when universe build jobs run. Use{" "}
        <Link to="/catalog-universe" className="font-medium text-patriot-blue hover:underline">Universe Tree</Link> to
        browse catalog + discovery.
      </p>
      {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}
      <p className="mt-2 text-xs text-slate-500">{emptyTreeMessage}</p>
      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-4">
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 p-2 text-sm">
          {publishers.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => void selectPublisher(row)}
                className={`w-full rounded px-2 py-1 text-left hover:bg-slate-100 ${
                  selectedPublisher?.id === row.id ? "bg-blue-50 font-medium text-patriot-navy" : "text-slate-800"
                }`}
              >
                {row.name}
              </button>
            </li>
          ))}
        </ul>
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 p-2 text-sm">
          {volumes.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => void selectVolume(row)}
                className={`w-full rounded px-2 py-1 text-left hover:bg-slate-100 ${
                  selectedVolume?.id === row.id ? "bg-blue-50 font-medium text-patriot-navy" : "text-slate-800"
                }`}
              >
                {row.name}
              </button>
            </li>
          ))}
        </ul>
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 p-2 text-sm">
          {issues.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => void selectIssue(row)}
                className="w-full rounded px-2 py-1 text-left text-slate-800 hover:bg-slate-100"
              >
                #{row.issue_number}
              </button>
            </li>
          ))}
        </ul>
        <ul className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 p-2 text-sm text-slate-700">
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

function LoadingSkeleton(): JSX.Element {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="h-3 w-24 rounded bg-slate-200" />
          <div className="mt-3 h-8 w-16 rounded bg-slate-100" />
        </div>
      ))}
    </div>
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
      setDashboard(null);
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Could not load catalog dashboard. Check that the API is deployed and you are signed in.");
      }
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
      <div className="mx-auto max-w-7xl">
        <header>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Catalog</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Master Universe</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">
            Full catalog command view: what ComicOS has cataloged, what ComicVine discovery expects, what you own, and
            where catalog rows came from (ComicVine, GCD, etc.).
          </p>
          <div className="mt-3 flex flex-wrap gap-3 text-sm">
            <Link to="/catalog-universe" className="font-medium text-patriot-blue hover:underline">
              Open Universe Tree browser →
            </Link>
            <Link to="/catalog/import" className="font-medium text-patriot-blue hover:underline">
              GCD Import Dashboard →
            </Link>
          </div>
        </header>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </p>
        ) : null}

        {loading && !dashboard ? <LoadingSkeleton /> : null}

        {dashboard ? (
          <>
            <SummaryGrid summary={dashboard.summary} />
            <CoverageTable dashboard={dashboard} search={search} onSearchChange={setSearch} />
          </>
        ) : null}

        {!loading && !dashboard && !error ? (
          <p className="mt-4 text-sm text-slate-600">No coverage data returned.</p>
        ) : null}

        <ReferenceTreePanel />
      </div>
    </AppShell>
  );
}
