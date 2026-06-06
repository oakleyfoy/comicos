import { useCallback, useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type FutureReleaseActionRead,
  type FutureReleaseDashboardRead,
  type FutureReleaseMatchRead,
  type NextIssueRead,
  type WatchlistMatchRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import {
  futureReleaseActionBadge,
  lightSectionTitle,
  lightStatCardLg,
  lightStatLabelSm,
  lightStatValueXl,
  lightTable,
  lightTableCell,
  lightTableCellMuted,
  lightTableCellPrimary,
  lightTableEmpty,
  lightTableHead,
  lightTableRow,
  lightTableWrap,
} from "../lib/lightSurfaceUi";

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

function SectionTable({
  title,
  empty,
  children,
}: {
  title: string;
  empty: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className="mt-8">
      <h2 className={lightSectionTitle}>{title}</h2>
      <div className={`mt-3 ${lightTableWrap}`}>{children}</div>
      {!children ? <p className="mt-2 text-sm text-slate-500">{empty}</p> : null}
    </section>
  );
}

export function FutureReleaseDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<FutureReleaseDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getFutureReleaseDashboard();
      setDash(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load future release dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const summary = dash?.summary;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P58-05"
        title="Future Release Dashboard"
        description="One view of next issues, FOC timing, preorder actions, and watchlist matches."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      {loading ? (
        <p className="mt-8 text-slate-600">Loading dashboard…</p>
      ) : summary ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[
              { label: "Active runs", value: summary.active_runs },
              { label: "Upcoming issues", value: summary.upcoming_issues },
              { label: "FOC this week", value: summary.foc_this_week },
              { label: "Preorder now", value: summary.preorder_now },
              { label: "Missed FOC", value: summary.missed_foc },
            ].map((card) => (
              <div key={card.label} className={lightStatCardLg}>
                <p className={lightStatLabelSm}>{card.label}</p>
                <p className={lightStatValueXl}>{card.value}</p>
              </div>
            ))}
          </div>

          <SectionTable title="Next issues" empty="">
            <table className={lightTable}>
              <thead className={lightTableHead}>
                <tr>
                  <th className="px-4 py-2">Series</th>
                  <th className="px-4 py-2">Current</th>
                  <th className="px-4 py-2">Next</th>
                  <th className="px-4 py-2">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {(dash?.next_issues ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className={lightTableEmpty}>
                      No next issues detected.
                    </td>
                  </tr>
                ) : (
                  (dash?.next_issues ?? []).map((row: NextIssueRead) => (
                    <tr key={row.id} className={lightTableRow}>
                      <td className={lightTableCellPrimary}>{row.series_name}</td>
                      <td className={lightTableCell}>#{row.current_issue}</td>
                      <td className={lightTableCell}>#{row.next_issue}</td>
                      <td className={lightTableCell}>{row.confidence.toFixed(2)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </SectionTable>

          <SectionTable title="Upcoming FOC" empty="">
            <FocMatchTable rows={dash?.upcoming_foc ?? []} />
          </SectionTable>

          <SectionTable title="Preorder now" empty="">
            <ActionTable rows={dash?.preorder_now ?? []} />
          </SectionTable>

          <SectionTable title="This week" empty="">
            <ActionTable rows={dash?.this_week ?? []} />
          </SectionTable>

          <SectionTable title="Missed FOC" empty="">
            <ActionTable rows={dash?.missed_foc ?? []} />
          </SectionTable>

          <SectionTable title="Watchlist" empty="">
            <WatchlistTable rows={dash?.watchlist ?? []} />
          </SectionTable>
        </>
      ) : null}
    </AppShell>
  );
}

function FocMatchTable({ rows }: { rows: FutureReleaseMatchRead[] }): JSX.Element {
  return (
    <table className={lightTable}>
      <thead className={lightTableHead}>
        <tr>
          <th className="px-4 py-2">Series</th>
          <th className="px-4 py-2">Issue</th>
          <th className="px-4 py-2">FOC</th>
          <th className="px-4 py-2">Release</th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={4} className={lightTableEmpty}>
              No upcoming FOC rows.
            </td>
          </tr>
        ) : (
          rows.map((row) => (
            <tr key={row.id} className={lightTableRow}>
              <td className={lightTableCellPrimary}>{row.series_name}</td>
              <td className={lightTableCell}>#{row.issue_number}</td>
              <td className={lightTableCell}>{formatDate(row.foc_date)}</td>
              <td className={lightTableCell}>{formatDate(row.release_date)}</td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}

function ActionTable({ rows }: { rows: FutureReleaseActionRead[] }): JSX.Element {
  return (
    <table className={lightTable}>
      <thead className={lightTableHead}>
        <tr>
          <th className="px-4 py-2">Series</th>
          <th className="px-4 py-2">Issue</th>
          <th className="px-4 py-2">Action</th>
          <th className="px-4 py-2">Priority</th>
          <th className="px-4 py-2">FOC</th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={5} className={lightTableEmpty}>
              None in this lane.
            </td>
          </tr>
        ) : (
          rows.map((row) => (
            <tr key={row.id} className={lightTableRow}>
              <td className={lightTableCellPrimary}>{row.series_name}</td>
              <td className={lightTableCell}>#{row.issue_number}</td>
              <td className="px-4 py-2">
                <span className={futureReleaseActionBadge(row.action_type)}>{row.action_type}</span>
              </td>
              <td className={lightTableCell}>{row.priority_score.toFixed(1)}</td>
              <td className={lightTableCellMuted}>{formatDate(row.foc_date)}</td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}

function WatchlistTable({ rows }: { rows: WatchlistMatchRead[] }): JSX.Element {
  return (
    <table className={lightTable}>
      <thead className={lightTableHead}>
        <tr>
          <th className="px-4 py-2">Watchlist</th>
          <th className="px-4 py-2">Issue</th>
          <th className="px-4 py-2">FOC</th>
          <th className="px-4 py-2">Release</th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={4} className={lightTableEmpty}>
              No upcoming watchlist matches.
            </td>
          </tr>
        ) : (
          rows.map((row, idx) => (
            <tr key={`${row.watchlist.id}-${row.release_issue.id}-${idx}`} className={lightTableRow}>
              <td className={lightTableCellPrimary}>{row.watchlist.watchlist_name}</td>
              <td className={lightTableCell}>
                {row.release_issue.title || `#${row.release_issue.issue_number}`}
              </td>
              <td className={lightTableCellMuted}>{formatDate(row.release_issue.foc_date as string | null)}</td>
              <td className={lightTableCellMuted}>{formatDate(row.release_issue.release_date as string | null)}</td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
