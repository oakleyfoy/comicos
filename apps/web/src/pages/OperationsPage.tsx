import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type OpsDashboardResponse } from "../api/client";
import { AppShell } from "../components/AppShell";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
    </article>
  );
}

function TableSection({
  title,
  description,
  headers,
  rows,
}: {
  title: string;
  description: string;
  headers: string[];
  rows: Array<Array<string | JSX.Element>>;
}) {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/70 shadow-xl shadow-black/20">
      <div className="border-b border-white/10 px-5 py-4">
        <h2 className="text-xl font-semibold text-white">{title}</h2>
        <p className="mt-2 text-sm text-slate-400">{description}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/10">
          <thead className="bg-slate-950/60">
            <tr>
              {headers.map((header) => (
                <th
                  key={header}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-slate-500"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.length > 0 ? (
              rows.map((row, rowIndex) => (
                <tr key={`${title}-${rowIndex}`} className="align-top">
                  {row.map((cell, cellIndex) => (
                    <td key={`${title}-${rowIndex}-${cellIndex}`} className="px-4 py-3 text-sm text-slate-200">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={headers.length} className="px-4 py-6 text-sm text-slate-400">
                  No recent records.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function OperationsPage() {
  const [dashboard, setDashboard] = useState<OpsDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function loadDashboard() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.getOpsDashboard();
        if (!ignore) {
          setDashboard(response);
        }
      } catch (loadError) {
        if (!ignore) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load operations dashboard.",
          );
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    void loadDashboard();
    return () => {
      ignore = true;
    };
  }, []);

  if (isLoading) {
    return (
      <AppShell>
        <LoadingState
          title="Loading operations dashboard"
          description="Refreshing Gmail syncs, parse jobs, imports, queue health, and operational events."
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="Ingestion Monitoring"
        description="Lightweight operational visibility for Gmail ingestion, parser activity, queue health, and import lifecycle state."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {dashboard ? (
        <>
          <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Recent Gmail Sync Jobs"
              value={String(dashboard.recent_gmail_sync_jobs.length)}
            />
            <StatCard
              label="Recent AI Parse Jobs"
              value={String(dashboard.recent_ai_parse_jobs.length)}
            />
            <StatCard
              label="Parser Failures"
              value={String(dashboard.parser_failures.length)}
            />
            <StatCard
              label="Duplicate Skips"
              value={String(dashboard.duplicate_skip_events.length)}
            />
          </section>

          <div className="mt-6 space-y-6">
            <TableSection
              title="Queue Health"
              description="Current RQ queue depth, started jobs, failed jobs, and the most recent job result."
              headers={["Queue", "Queued", "Started", "Failed", "Most Recent Result"]}
              rows={dashboard.queue_health.map((queue) => [
                queue.queue_name,
                String(queue.queued_jobs),
                String(queue.started_jobs),
                String(queue.failed_jobs),
                queue.most_recent_job_result ?? "None",
              ])}
            />

            <TableSection
              title="Gmail Sync Visibility"
              description="Latest Gmail sync state, counts, and failure details by connected account."
              headers={[
                "User",
                "Gmail",
                "Status",
                "Started",
                "Completed",
                "Processed",
                "Created",
                "Duplicates",
                "Last Error",
              ]}
              rows={dashboard.gmail_sync_statuses.map((row) => [
                `${row.user_email} (#${row.user_id})`,
                row.gmail_email,
                row.last_sync_status ?? "Never run",
                formatDateTime(row.last_sync_started_at),
                formatDateTime(row.last_sync_completed_at),
                row.processed_messages === null ? "Unknown" : String(row.processed_messages),
                row.created_draft_imports === null ? "Unknown" : String(row.created_draft_imports),
                row.skipped_duplicates === null ? "Unknown" : String(row.skipped_duplicates),
                row.last_error_message ?? "None",
              ])}
            />

            <TableSection
              title="Recent Draft Imports"
              description="Draft lifecycle state, user ownership, confidence, warnings, and linked orders."
              headers={[
                "Draft",
                "User",
                "Retailer",
                "Status",
                "Confidence",
                "Warnings",
                "Created",
                "Linked Order",
              ]}
              rows={dashboard.recent_draft_imports.map((row) => [
                String(row.draft_id),
                `${row.user_email} (#${row.user_id})`,
                row.retailer ?? "Unknown",
                row.status,
                row.confidence,
                String(row.warning_count),
                formatDateTime(row.created_at),
                row.linked_order_id ? (
                  <Link className="text-cyan-200 hover:text-cyan-100" to={`/orders/${row.linked_order_id}`}>
                    Order #{row.linked_order_id}
                  </Link>
                ) : (
                  "None"
                ),
              ])}
            />

            <TableSection
              title="Recent Gmail Sync Jobs"
              description="Recent Gmail sync job activity and result summaries."
              headers={["Job", "Queue", "Status", "User", "Started", "Ended", "Result", "Error"]}
              rows={dashboard.recent_gmail_sync_jobs.map((row) => [
                row.job_id,
                row.queue_name,
                row.status,
                row.user_email ?? "Unknown",
                formatDateTime(row.started_at),
                formatDateTime(row.ended_at),
                row.result_summary ?? "None",
                row.error ?? "None",
              ])}
            />

            <TableSection
              title="Recent AI Parse Jobs"
              description="Recent AI parser job activity and surfaced failures."
              headers={["Job", "Queue", "Status", "User", "Started", "Ended", "Result", "Error"]}
              rows={dashboard.recent_ai_parse_jobs.map((row) => [
                row.job_id,
                row.queue_name,
                row.status,
                row.user_email ?? "Unknown",
                formatDateTime(row.started_at),
                formatDateTime(row.ended_at),
                row.result_summary ?? "None",
                row.error ?? "None",
              ])}
            />

            <TableSection
              title="Parser Failures"
              description="Quota, malformed receipt, unsupported provider, and validation failures surfaced without log inspection."
              headers={["When", "Type", "User", "Draft", "External Message", "Message"]}
              rows={dashboard.parser_failures.map((row) => [
                formatDateTime(row.created_at),
                row.event_type,
                row.user_email ?? "Unknown",
                row.draft_import_id ? String(row.draft_import_id) : "None",
                row.external_message_id ?? "None",
                row.message ?? "None",
              ])}
            />

            <TableSection
              title="Duplicate Skips"
              description="Duplicate Gmail imports that were safely skipped."
              headers={["When", "User", "External Message", "Original Import", "Draft"]}
              rows={dashboard.duplicate_skip_events.map((row) => [
                formatDateTime(row.created_at),
                row.user_email ?? "Unknown",
                row.external_message_id ?? "None",
                typeof row.details.original_imported_at === "string"
                  ? formatDateTime(row.details.original_imported_at)
                  : "Unknown",
                row.draft_import_id ? String(row.draft_import_id) : "None",
              ])}
            />

            <TableSection
              title="Confirm Events"
              description="Recent confirm successes and failures for the import lifecycle."
              headers={["When", "Status", "User", "Draft", "Order", "Message"]}
              rows={dashboard.confirm_events.map((row) => [
                formatDateTime(row.created_at),
                row.status,
                row.user_email ?? "Unknown",
                row.draft_import_id ? String(row.draft_import_id) : "None",
                row.order_id ? (
                  <Link className="text-cyan-200 hover:text-cyan-100" to={`/orders/${row.order_id}`}>
                    Order #{row.order_id}
                  </Link>
                ) : (
                  "None"
                ),
                row.message ?? "None",
              ])}
            />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
