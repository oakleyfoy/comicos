import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AutomationRuleRead } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationRulesSummaryCard() {
  const [latest, setLatest] = useState<AutomationRuleRead | null>(null);
  const [stats, setStats] = useState({ active: 0, failed: 0, drift: 0, actionFailures: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const rules = await apiClient.listAutomationRules({ limit: 12, offset: 0 });
        if (ignore) return;
        setLatest((rules.items[0] as AutomationRuleRead | undefined) ?? null);
        setStats({
          active: rules.active_rule_count ?? 0,
          failed: rules.failed_evaluation_count ?? 0,
          drift: rules.replay_drift_count ?? 0,
          actionFailures: rules.action_failure_count ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation rules summary.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  if (!loading && !error && !latest) return null;

  return (
    <section className="mt-6 rounded-3xl border border-fuchsia-400/25 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/15">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-fuchsia-200/70">Automation rules</p>
          <h2 className="mt-1 text-lg font-semibold text-white">Deterministic automation policies</h2>
          <p className="mt-1 max-w-prose text-sm text-slate-400">Rule counts, evaluation failures, replay drift, and action failure visibility.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/automation-rules" className="rounded-full border border-fuchsia-400/35 px-3 py-1.5 text-xs font-semibold text-fuchsia-100">
            Open rules engine
          </Link>
          <Link to="/ops#automation-rules-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops
          </Link>
        </div>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation rules summary…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : latest ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Latest rule" value={`${latest.rule_name}`} />
          <StatCard label="Active rules" value={String(stats.active)} />
          <StatCard label="Failed eval / drift" value={`${stats.failed} / ${stats.drift}`} />
          <StatCard label="Action failures" value={String(stats.actionFailures)} />
        </div>
      ) : null}
    </section>
  );
}
