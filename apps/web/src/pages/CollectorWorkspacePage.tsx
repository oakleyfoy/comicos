import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type CollectorNarrativeSnapshotRead,
  type CollectorTaskItemRead,
  type CollectorTaskSnapshotRead,
  type NotificationSnapshotRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const TASK_SECTIONS = ["", "BUY", "SELL", "GRADE", "ACQUIRE", "WATCH"] as const;

function filterTasks(items: CollectorTaskItemRead[], section: string): CollectorTaskItemRead[] {
  if (!section) return items;
  return items.filter((t) => t.task_type === section);
}

export function CollectorWorkspacePage(): JSX.Element {
  const [tasks, setTasks] = useState<CollectorTaskSnapshotRead | null>(null);
  const [narratives, setNarratives] = useState<CollectorNarrativeSnapshotRead | null>(null);
  const [notifications, setNotifications] = useState<NotificationSnapshotRead | null>(null);
  const [section, setSection] = useState<(typeof TASK_SECTIONS)[number]>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, n, notif] = await Promise.all([
        apiClient.getCollectorWorkspaceTasksLatest(),
        apiClient.getCollectorNarrativesLatest(),
        apiClient.getNotificationsLatest(),
      ]);
      setTasks(t);
      setNarratives(n);
      setNotifications(notif);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load collector workspace.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleTasks = useMemo(
    () => filterTasks(tasks?.items ?? [], section),
    [tasks?.items, section],
  );

  const opportunityFeed = useMemo(
    () => (tasks?.items ?? []).filter((t) => t.priority_score >= 50).slice(0, 12),
    [tasks?.items],
  );

  const weeklyBriefing = narratives?.items.find((i) => i.narrative_kind === "WEEKLY_BRIEFING");
  const laneNarratives = (narratives?.items ?? []).filter((i) => i.narrative_kind !== "WEEKLY_BRIEFING").slice(0, 20);

  async function refreshAll(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await apiClient.buildCollectorWorkspaceTasks();
      await apiClient.buildCollectorNarratives();
      await apiClient.buildNotifications();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Refresh failed.");
    } finally {
      setBusy(false);
    }
  }

  async function setTaskStatus(taskId: number, status: string): Promise<void> {
    try {
      await apiClient.patchCollectorWorkspaceTask(taskId, status);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Status update failed.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P65"
        title="Collector Workspace"
        description="Action center for buy, sell, grade, acquire, and watch tasks — built from P61–P64 intelligence without changing scores."
        actions={
          <button
            type="button"
            className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            disabled={busy}
            onClick={() => void refreshAll()}
          >
            {busy ? "Refreshing…" : "Refresh workspace"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-slate-400">Loading…</p> : null}

      <div className="mb-6 grid gap-3 sm:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
          <p className="text-slate-500">Tasks</p>
          <p className="text-lg font-semibold text-white">{tasks?.total_items ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
          <p className="text-slate-500">Unread notifications</p>
          <p className="text-lg font-semibold text-white">{notifications?.unread_count ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
          <p className="text-slate-500">Narratives</p>
          <p className="text-lg font-semibold text-white">{narratives?.items.length ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm">
          <p className="text-slate-500">Readiness</p>
          <p className="text-lg font-semibold text-white">{tasks?.readiness_status ?? "—"}</p>
        </div>
      </div>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-white">My Tasks</h2>
        <div className="mb-3 flex flex-wrap gap-2">
          {TASK_SECTIONS.map((s) => (
            <button
              key={s || "all"}
              type="button"
              className={`rounded-lg px-3 py-1 text-sm ${section === s ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300"}`}
              onClick={() => setSection(s)}
            >
              {s || "All"}
            </button>
          ))}
        </div>
        <ul className="space-y-2">
          {visibleTasks.map((t) => (
            <li key={t.id} className="rounded-xl border border-white/10 bg-slate-900/50 p-3 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <span className="mr-2 rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">{t.task_type}</span>
                  <span className="font-medium text-white">{t.title}</span>
                  <p className="mt-1 text-slate-400">{t.explanation || t.action_hint}</p>
                </div>
                <div className="flex gap-1">
                  <button
                    type="button"
                    className="rounded bg-slate-700 px-2 py-1 text-xs text-white"
                    onClick={() => void setTaskStatus(t.id, "IN_PROGRESS")}
                  >
                    Start
                  </button>
                  <button
                    type="button"
                    className="rounded bg-slate-700 px-2 py-1 text-xs text-white"
                    onClick={() => void setTaskStatus(t.id, "COMPLETED")}
                  >
                    Done
                  </button>
                  <button
                    type="button"
                    className="rounded bg-slate-700 px-2 py-1 text-xs text-white"
                    onClick={() => void setTaskStatus(t.id, "DISMISSED")}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </li>
          ))}
          {visibleTasks.length === 0 && !loading ? (
            <li className="text-slate-500">No tasks in this lane. Run Refresh workspace after intelligence builds.</li>
          ) : null}
        </ul>
      </section>

      <div className="grid gap-8 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-lg font-semibold text-white">Notifications</h2>
          <ul className="max-h-80 space-y-2 overflow-y-auto">
            {(notifications?.items ?? []).slice(0, 15).map((n) => (
              <li key={n.id} className="rounded-lg border border-white/10 bg-slate-900/40 p-2 text-sm">
                <p className="font-medium text-white">{n.title}</p>
                <p className="text-slate-400">{n.message}</p>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold text-white">Weekly Briefing</h2>
          <div className="rounded-xl border border-white/10 bg-slate-900/50 p-4 text-sm text-slate-200 whitespace-pre-wrap">
            {narratives?.briefing_markdown || weeklyBriefing?.narrative_text || "No briefing yet."}
          </div>
        </section>
      </div>

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-semibold text-white">Narratives</h2>
        <ul className="space-y-2">
          {laneNarratives.map((n) => (
            <li key={n.id} className="rounded-lg border border-white/10 bg-slate-900/40 p-3 text-sm">
              <p className="text-xs text-slate-500">{n.narrative_kind}</p>
              <p className="font-medium text-white">{n.title}</p>
              <p className="text-slate-300">{n.narrative_text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-semibold text-white">Opportunity Feed</h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {opportunityFeed.map((t) => (
            <li key={`opp-${t.id}`} className="rounded-lg border border-indigo-500/20 bg-indigo-950/30 p-3 text-sm">
              <p className="font-medium text-white">{t.title}</p>
              <p className="text-slate-400">
                {t.task_type} · score {t.priority_score.toFixed(1)}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </AppShell>
  );
}
