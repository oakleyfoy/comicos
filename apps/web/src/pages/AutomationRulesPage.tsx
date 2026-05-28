import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationRuleActionRead,
  type AutomationRuleEvaluationRead,
  type AutomationRuleIssueRead,
  type AutomationRuleRead,
  type AutomationRuleVersionRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export function AutomationRulesPage() {
  const [rules, setRules] = useState<AutomationRuleRead[]>([]);
  const [versions, setVersions] = useState<AutomationRuleVersionRead[]>([]);
  const [evaluations, setEvaluations] = useState<AutomationRuleEvaluationRead[]>([]);
  const [actions, setActions] = useState<AutomationRuleActionRead[]>([]);
  const [issues, setIssues] = useState<AutomationRuleIssueRead[]>([]);
  const [selected, setSelected] = useState<AutomationRuleRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh(ruleId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [ruleResponse, issueResponse] = await Promise.all([
        apiClient.listAutomationRules({ limit: 50, offset: 0 }),
        apiClient.listAutomationRuleIssues({ limit: 50, offset: 0 }),
      ]);
      const nextRules = ruleResponse.items as AutomationRuleRead[];
      setRules(nextRules);
      setIssues(issueResponse.items as AutomationRuleIssueRead[]);
      const nextId = ruleId ?? nextRules[0]?.id ?? null;
      if (!nextId) {
        setSelected(null);
        setVersions([]);
        setEvaluations([]);
        setActions([]);
        return;
      }

      const [detail, versionResponse, evaluationResponse, actionResponse] = await Promise.all([
        apiClient.getAutomationRule(nextId),
        apiClient.listAutomationRuleVersions(nextId, { limit: 50, offset: 0 }),
        apiClient.listAutomationRuleEvaluations(nextId, { limit: 50, offset: 0 }),
        apiClient.listAutomationRuleActions(nextId, { limit: 50, offset: 0 }),
      ]);
      setSelected(detail);
      setVersions(versionResponse.items as AutomationRuleVersionRead[]);
      setEvaluations(evaluationResponse.items as AutomationRuleEvaluationRead[]);
      setActions(actionResponse.items as AutomationRuleActionRead[]);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation rules workspace.");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    return {
      activeRules: rules.filter((row) => row.rule_status === "ACTIVE").length,
      failedEvaluations: evaluations.filter((row) => row.evaluation_status === "FAILED").length,
      replayDriftWarnings: issues.filter((row) => row.issue_type === "REPLAY_RULE_DRIFT" || row.issue_type === "RULE_CHECKSUM_MISMATCH").length,
      actionFailures: actions.filter((row) => row.action_status === "FAILED").length,
      pausedRules: rules.filter((row) => row.rule_status === "PAUSED").length,
    };
  }, [actions, evaluations, issues, rules]);

  const manifestPreview = useMemo(() => {
    const latest = evaluations[0];
    const manifest = latest?.evaluation_result_json?.manifest;
    return manifest && typeof manifest === "object" ? JSON.stringify(manifest, null, 2) : null;
  }, [evaluations]);

  const timelineRows = useMemo(() => {
    const events = [
      ...versions.map((row) => ({ id: `v-${row.id}`, label: `Version ${row.version_number} ${row.version_status}`, created_at: row.created_at })),
      ...evaluations.map((row) => ({ id: `e-${row.id}`, label: `Evaluation ${row.evaluation_status}`, created_at: row.created_at })),
      ...actions.map((row) => ({ id: `a-${row.id}`, label: `Action ${row.action_type} ${row.action_status}`, created_at: row.created_at })),
    ];
    return events.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  }, [actions, evaluations, versions]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-08"
        title="Automation Rules Engine"
        description="Deterministic replay-safe automation policy infrastructure."
        actions={
          <Link to="/ops#automation-rules-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops diagnostics
          </Link>
        }
      />
      {error ? <div className="mt-4"><StatusBanner tone="error">{error}</StatusBanner></div> : null}
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading automation rules workspace…</p>
      ) : !rules.length ? (
        <EmptyState title="No automation rules yet" description="Rules appear here after an ops administrator creates deterministic automation policies." />
      ) : (
        <div className="mt-6 space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Active rules" value={String(summary.activeRules)} />
            <StatCard label="Failed evaluations" value={String(summary.failedEvaluations)} />
            <StatCard label="Replay drift" value={String(summary.replayDriftWarnings)} />
            <StatCard label="Action failures" value={String(summary.actionFailures)} />
            <StatCard label="Paused rules" value={String(summary.pausedRules)} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Rule ledger">
              <ul className="space-y-2 text-sm text-slate-300">
                {rules.map((row) => (
                  <li key={row.id}>
                    <button
                      type="button"
                      className={`w-full rounded-2xl border px-3 py-2 text-left ${selected?.id === row.id ? "border-cyan-400/40 bg-cyan-500/10" : "border-white/5 bg-slate-950/40"}`}
                      onClick={() => void refresh(row.id)}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-semibold text-white">{row.rule_name}</span>
                        <span className="text-xs text-slate-400">{row.rule_category} / {row.rule_status}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{row.rule_key}</p>
                    </button>
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel title="Rule version panel">
              {versions.length ? (
                <ul className="space-y-2 text-xs text-slate-300">
                  {versions.map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <span>Version {row.version_number}</span>
                        <span>{row.version_status}</span>
                      </div>
                      <p className="mt-1 text-slate-400">{row.condition_expression}</p>
                      <p className="mt-1 font-mono text-[11px] text-slate-500">{row.version_checksum.slice(0, 24)}…</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No versions available.</p>
              )}
            </Panel>

            <Panel title="Evaluation panel">
              {evaluations.length ? (
                <ul className="space-y-2 text-xs text-slate-300">
                  {evaluations.map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <span>{row.evaluation_type}</span>
                        <span>{row.evaluation_status}</span>
                      </div>
                      <p className="mt-1 text-slate-400">matched: {row.matched ? "yes" : "no"} · rank: {row.evaluation_rank}</p>
                      <p className="mt-1 font-mono text-[11px] text-slate-500">{row.evaluation_checksum.slice(0, 24)}…</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No evaluations recorded.</p>
              )}
            </Panel>

            <Panel title="Action sequencing panel">
              {actions.length ? (
                <ul className="space-y-2 text-xs text-slate-300">
                  {actions.map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                      #{row.action_rank} · {row.action_type} · {row.action_status} · {row.target_scope}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No actions recorded.</p>
              )}
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Drift / replay panel">
              {issues.length ? (
                <ul className="space-y-2 text-xs text-slate-300">
                  {issues
                    .filter((row) => row.issue_type === "REPLAY_RULE_DRIFT" || row.issue_type === "RULE_CHECKSUM_MISMATCH" || row.issue_type === "RULE_VERSION_CONFLICT")
                    .slice(0, 12)
                    .map((row) => (
                      <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                        {row.issue_type} · {row.severity} · {row.issue_message}
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No replay drift warnings detected.</p>
              )}
            </Panel>

            <Panel title="Issues panel">
              {issues.length ? (
                <ul className="space-y-2 text-xs text-slate-300">
                  {issues.slice(0, 12).map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                      {row.issue_type} · {row.severity} · {row.issue_message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No rule issues detected.</p>
              )}
            </Panel>

            <Panel title="Artifact panel">
              {manifestPreview ? (
                <pre className="max-h-80 overflow-auto rounded-2xl border border-white/5 bg-slate-950/50 p-3 text-[11px] text-slate-300">{manifestPreview}</pre>
              ) : (
                <p className="text-sm text-slate-500">Evaluation manifests appear after the first rule evaluation.</p>
              )}
            </Panel>

            <Panel title="History timeline">
              {timelineRows.length ? (
                <ul className="space-y-2 text-xs text-slate-300">
                  {timelineRows.slice(0, 16).map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                      {formatDateTime(row.created_at)} · {row.label}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No rule history yet.</p>
              )}
            </Panel>
          </div>
        </div>
      )}
    </AppShell>
  );
}
