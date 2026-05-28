import { useEffect, useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { StatusBanner } from "./StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationRulesOpsPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({ rules: 0, failed: 0, drift: 0, actionFailures: 0, paused: 0 });

  useEffect(() => {
    let ignore = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [rules, failures, drift] = await Promise.all([
          apiClient.listOpsAutomationRules({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationRuleFailures({ limit: 100, offset: 0 }),
          apiClient.listOpsAutomationRuleDrift({ limit: 100, offset: 0 }),
        ]);
        if (ignore) return;
        setStats({
          rules: rules.pagination.total_count,
          failed: failures.pagination.total_count,
          drift: drift.pagination.total_count,
          actionFailures: rules.action_failure_count ?? 0,
          paused: rules.paused_rule_count ?? 0,
        });
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation rules ops diagnostics.");
      } finally {
        if (!ignore) setLoading(false);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section id="automation-rules-ops" className="mt-6 rounded-3xl border border-fuchsia-400/35 bg-fuchsia-950/10 p-5 shadow-xl shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Automation rules ops</h2>
          <p className="mt-1 max-w-3xl text-xs text-slate-400">
            Failed evaluations, replay drift diagnostics, action failures, rule conflicts, invalid expressions, and deterministic sequencing visibility.
          </p>
        </div>
        <span className="rounded-full border border-fuchsia-300/35 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-fuchsia-100/90">
          Ops / P41-08
        </span>
      </div>
      {loading ? (
        <p className="mt-4 text-sm text-slate-400">Loading automation rules diagnostics…</p>
      ) : error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Rules" value={String(stats.rules)} />
          <StatCard label="Failed evals" value={String(stats.failed)} />
          <StatCard label="Replay drift" value={String(stats.drift)} />
          <StatCard label="Action failures" value={String(stats.actionFailures)} />
          <StatCard label="Paused rules" value={String(stats.paused)} />
        </div>
      )}
    </section>
  );
}
