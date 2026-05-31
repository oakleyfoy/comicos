import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type PullListRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function statusTone(status: string): string {
  switch (status) {
    case "ACTIVE":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "PAUSED":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "COMPLETED":
      return "border-sky-400/30 bg-sky-400/10 text-sky-100";
    case "DROPPED":
      return "border-slate-500/30 bg-slate-500/10 text-slate-200";
    default:
      return "border-white/10 bg-white/5 text-slate-200";
  }
}

export function PullListPage(): JSX.Element {
  const [items, setItems] = useState<PullListRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getPullLists();
        if (!cancelled) setItems(body.items);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load pull lists.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P52-01"
        title="Pull Lists"
        description="Persistent series pull lists and manually attached upcoming releases (read-only overview)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading pull lists…</p>
      ) : (
        <div className="mt-6 space-y-6">
          <Panel title="My Pull Lists">
            {items.length === 0 ? (
              <p className="text-sm text-slate-400">No pull lists yet. Create one via the API to start tracking releases.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm text-slate-200">
                  <thead className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                    <tr>
                      <th className="pb-3 pr-4 font-medium">Series</th>
                      <th className="pb-3 pr-4 font-medium">Publisher</th>
                      <th className="pb-3 pr-4 font-medium">Status</th>
                      <th className="pb-3 font-medium">Upcoming Issues</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((row) => (
                      <tr key={row.id} className="border-t border-white/5">
                        <td className="py-3 pr-4 font-medium text-white">{row.series_name}</td>
                        <td className="py-3 pr-4">{row.publisher}</td>
                        <td className="py-3 pr-4">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(row.status)}`}
                          >
                            {row.status}
                          </span>
                        </td>
                        <td className="py-3">{row.upcoming_issue_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      )}
    </AppShell>
  );
}
