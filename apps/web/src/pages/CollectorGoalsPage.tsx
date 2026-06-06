import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77CollectorGoalRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorGoalsPage(): JSX.Element {
  const [goals, setGoals] = useState<P77CollectorGoalRead[]>([]);
  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("30");
  const [progress, setProgress] = useState("0");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const list = await apiClient.listCollectorProfileGoals({ limit: 50, offset: 0 });
      setGoals(list.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load goals.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addGoal(): Promise<void> {
    if (!title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.createCollectorProfileGoal({
        goal_type: "RUN_COMPLETION",
        title: title.trim(),
        target_value: Number.parseFloat(target) || 0,
        progress_value: Number.parseFloat(progress) || 0,
        metadata: { series_name: title.trim() },
      });
      setTitle("");
      setProgress("0");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-2xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-300">P77-01</p>
          <h1 className="text-xl font-semibold">Collection Goals</h1>
          <CollectorProfileNav />
        </div>
      </header>
      <main className="mx-auto max-w-2xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4 space-y-3">
          <input
            className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
            placeholder="Goal title (e.g. Absolute Batman)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <input
              className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
              placeholder="Target"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            />
            <input
              className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-2"
              placeholder="Progress"
              value={progress}
              onChange={(e) => setProgress(e.target.value)}
            />
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void addGoal()}
            className="w-full rounded-xl bg-sky-600 py-2 font-semibold disabled:opacity-50"
          >
            Add run completion goal
          </button>
        </section>
        <ul className="space-y-3">
          {goals.map((goal) => (
            <li key={goal.id} className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
              <p className="font-medium">{goal.title}</p>
              <p className="text-sm text-slate-400 mt-1">
                {goal.progress_value} / {goal.target_value} · {goal.completion_percent}%
              </p>
              <p className="text-xs text-slate-500 mt-1">{goal.goal_type}</p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
