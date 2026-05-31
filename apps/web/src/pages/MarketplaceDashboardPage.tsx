import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type MarketplaceDashboardSummaryRead,
  type MarketplaceHealthRead,
  type MarketplaceValidationRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "PASS":
    case "HEALTHY":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAIL":
    case "FAILED":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "DISABLED":
      return "border-slate-500/30 bg-slate-500/10 text-slate-200";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function StatusBadge({ value }: { value: string }): JSX.Element {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(value)}`}>
      {value}
    </span>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function MarketplaceDashboardPage(): JSX.Element {
  const [summary, setSummary] = useState<MarketplaceDashboardSummaryRead | null>(null);
  const [validation, setValidation] = useState<MarketplaceValidationRead | null>(null);
  const [health, setHealth] = useState<MarketplaceHealthRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [dashboard, validationBody, healthBody] = await Promise.all([
          apiClient.getMarketplaceDashboard(),
          apiClient.getMarketplaceDashboardValidation(),
          apiClient.getMarketplaceDashboardHealth(),
        ]);
        if (cancelled) return;
        setSummary(dashboard);
        setValidation(validationBody);
        setHealth(healthBody);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Unable to load marketplace dashboard.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const validationPanels = useMemo(() => {
    const checks = validation?.checks ?? summary?.validation_checks ?? [];
    const byCode = new Map(checks.map((check) => [check.check_code, check]));
    return [
      { title: "Connector Validation", check: byCode.get("connectors") },
      { title: "Publish Validation", check: byCode.get("publish_engine") },
      { title: "Inventory Validation", check: byCode.get("inventory_sync") },
      { title: "Order Validation", check: byCode.get("order_import") },
    ];
  }, [summary?.validation_checks, validation?.checks]);

  const healthPanels = useMemo(() => {
    const components = health?.components ?? summary?.health_components ?? [];
    const byCode = new Map(components.map((component) => [component.component_code, component]));
    return [
      { title: "Connector Health", component: byCode.get("connector_health") },
      { title: "Account Health", component: byCode.get("account_health") },
      { title: "Publish Health", component: byCode.get("publish_health") },
      { title: "Sync Health", component: byCode.get("sync_health") },
    ];
  }, [health?.components, summary?.health_components]);

  const cards = summary?.summary_cards;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Marketplace"
        title="Marketplace Platform"
        description="Validation, health, and readiness for ComicOS marketplace connectors (P46)."
        actions={
          summary ? (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge value={summary.validation_status} />
              <StatusBadge value={summary.health_status} />
              {summary.platform_certified ? (
                <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-100">
                  Certified
                </span>
              ) : null}
            </div>
          ) : null
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading marketplace dashboard…</p> : null}

      {!loading && summary ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Listings" value={String(cards?.listings ?? 0)} />
            <StatCard label="Publish Jobs" value={String(cards?.publish_jobs ?? 0)} />
            <StatCard label="Orders" value={String(cards?.orders ?? 0)} />
            <StatCard label="Reservations" value={String(cards?.reservations ?? 0)} />
            <StatCard label="Sync Plans" value={String(cards?.sync_plans ?? 0)} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Health Panels">
              <ul className="space-y-3">
                {healthPanels.map(({ title, component }) => (
                  <li key={title} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium text-white">{title}</p>
                      <StatusBadge value={component?.health_status ?? "WARNING"} />
                    </div>
                    <p className="mt-2 text-sm text-slate-400">{component?.summary ?? "No health signal yet."}</p>
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel title="Validation Panels">
              <ul className="space-y-3">
                {validationPanels.map(({ title, check }) => (
                  <li key={title} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium text-white">{title}</p>
                      <StatusBadge value={check?.status ?? "WARNING"} />
                    </div>
                    <p className="mt-2 text-sm text-slate-400">{check?.summary ?? "Validation has not run yet."}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
