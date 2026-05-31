import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type AuditEventRead,
  type DataIntegrityCheckRead,
  type DataIntegrityIssueRead,
  type MigrationSafetyCheckRead,
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
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
}

function StatusBadge({ value }: { value: string }): JSX.Element {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(value)}`}>
      {value}
    </span>
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

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function EmptyState({ message }: { message: string }): JSX.Element {
  return <p className="text-sm text-slate-500">{message}</p>;
}

function issueCount(check: DataIntegrityCheckRead | null): number {
  const raw = check?.summary_json?.issue_count;
  return typeof raw === "number" ? raw : 0;
}

export function DataProtectionPage(): JSX.Element {
  const [checks, setChecks] = useState<DataIntegrityCheckRead[]>([]);
  const [issues, setIssues] = useState<DataIntegrityIssueRead[]>([]);
  const [migrationChecks, setMigrationChecks] = useState<MigrationSafetyCheckRead[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [checksBody, issuesBody, migrationBody, auditBody] = await Promise.all([
          apiClient.getDataIntegrityChecks({ limit: 5 }),
          apiClient.getDataIntegrityIssues({ limit: 5 }),
          apiClient.getMigrationSafetyChecks({ limit: 5 }),
          apiClient.getAuditEvents({ limit: 5 }),
        ]);
        if (cancelled) return;
        setChecks(checksBody.items);
        setIssues(issuesBody.items);
        setMigrationChecks(migrationBody.items);
        setAuditEvents(auditBody.items);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Unable to load data protection dashboard.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const latestCheck = checks[0] ?? null;
  const latestMigrationCheck = migrationChecks[0] ?? null;
  const changeTrackingSummary = useMemo(() => {
    const totalChangedFields = auditEvents.reduce((sum, event) => {
      const changedFieldCount = event.event_payload_json?.changed_field_count;
      return sum + (typeof changedFieldCount === "number" ? changedFieldCount : 0);
    }, 0);
    return {
      recentEvents: auditEvents.length,
      changedFields: totalChangedFields,
    };
  }, [auditEvents]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Data Protection"
        title="Data Protection"
        description="Integrity validation, migration safety, audit history, and change tracking for ComicOS production data."
        actions={
          latestCheck ? (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge value={latestCheck.check_status} />
              {latestMigrationCheck ? <StatusBadge value={latestMigrationCheck.check_status} /> : null}
            </div>
          ) : null
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading data protection dashboard…</p> : null}

      {!loading ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Data Integrity Status" value={latestCheck?.check_status ?? "NOT RUN"} />
            <StatCard label="Latest Integrity Check" value={latestCheck ? new Date(latestCheck.checked_at).toLocaleDateString() : "No checks"} />
            <StatCard label="Open Issues" value={String(issues.length)} />
            <StatCard label="Migration Safety Status" value={latestMigrationCheck?.check_status ?? "NOT RUN"} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Latest Integrity Check">
              {latestCheck ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge value={latestCheck.check_status} />
                    <span className="text-sm text-slate-400">{latestCheck.check_type}</span>
                  </div>
                  <p className="text-sm text-slate-300">Detected {issueCount(latestCheck)} open integrity issue(s) in the latest validation pass.</p>
                </div>
              ) : (
                <EmptyState message="No integrity checks have run yet." />
              )}
            </Panel>

            <Panel title="Open Issues">
              {issues.length ? (
                <ul className="space-y-3">
                  {issues.map((issue) => (
                    <li key={issue.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-white">{issue.issue_type}</p>
                        <StatusBadge value={issue.severity} />
                      </div>
                      <p className="mt-2 text-sm text-slate-400">{issue.issue_message}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState message="No integrity issues are open right now." />
              )}
            </Panel>

            <Panel title="Migration Safety Status">
              {latestMigrationCheck ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge value={latestMigrationCheck.check_status} />
                    <span className="text-sm text-slate-400">{latestMigrationCheck.migration_revision}</span>
                  </div>
                  <p className="text-sm text-slate-300">
                    Validated counts across {Object.keys(latestMigrationCheck.validation_payload_json?.comparison ?? {}).length} tracked entities.
                  </p>
                </div>
              ) : (
                <EmptyState message="No migration safety validations have been recorded yet." />
              )}
            </Panel>

            <Panel title="Change Tracking Summary">
              <div className="grid gap-4 sm:grid-cols-2">
                <StatCard label="Recent Audit Events" value={String(changeTrackingSummary.recentEvents)} />
                <StatCard label="Changed Fields" value={String(changeTrackingSummary.changedFields)} />
              </div>
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Recent Audit Events">
              {auditEvents.length ? (
                <ul className="space-y-3">
                  {auditEvents.map((event) => (
                    <li key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-white">{event.action_type}</p>
                        <span className="text-xs uppercase tracking-[0.12em] text-slate-500">{event.entity_type}</span>
                      </div>
                      <p className="mt-2 text-sm text-slate-400">{event.source}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState message="No audit events have been logged yet." />
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
