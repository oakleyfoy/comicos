import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiClient,
  type IndustryPublisherInclusionStatus,
  type IndustryPublisherRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function inclusionClass(status: IndustryPublisherInclusionStatus): string {
  return status === "INCLUDED" ? "text-emerald-300" : "text-slate-400";
}

export function IndustryPublishersPage(): JSX.Element {
  const [items, setItems] = useState<IndustryPublisherRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await apiClient.getIndustryPublishers();
      setItems(list.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load industry publishers.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const includedCount = useMemo(
    () => items.filter((row) => row.inclusion_status === "INCLUDED" && row.scan_enabled).length,
    [items],
  );

  async function patchPublisher(
    publisherId: number,
    body: {
      scan_enabled?: boolean;
      inclusion_status?: IndustryPublisherInclusionStatus;
      scan_priority?: number;
    },
  ) {
    setSavingId(publisherId);
    setMessage(null);
    setError(null);
    try {
      const updated = await apiClient.patchIndustryPublisher(publisherId, body);
      setItems((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      setMessage(`${updated.publisher_name} updated.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update publisher.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="P59-01"
        title="Industry Publishers"
        description="Supported publisher registry and scan configuration for industry-wide release monitoring (registry only — no spec scoring or purchases)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {!loading && items.length > 0 ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Publishers</p>
            <p className="mt-1 text-2xl font-semibold text-white">{items.length}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Scan enabled</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">{includedCount}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Classification</p>
            <p className="mt-1 text-lg font-semibold text-slate-200">STANDARD</p>
          </div>
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading industry publishers…</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-white/10">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Publisher</th>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Inclusion</th>
                <th className="px-4 py-3">Scan</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Mode</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 font-medium text-white">{row.publisher_name}</td>
                  <td className="px-4 py-3 text-slate-400">{row.publisher_code}</td>
                  <td className="px-4 py-3">
                    <select
                      className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-xs text-slate-200"
                      value={row.inclusion_status}
                      disabled={savingId === row.id}
                      onChange={(e) =>
                        void patchPublisher(row.id, {
                          inclusion_status: e.target.value as IndustryPublisherInclusionStatus,
                        })
                      }
                    >
                      <option value="INCLUDED">Included</option>
                      <option value="EXCLUDED">Excluded</option>
                    </select>
                    <span className={`ml-2 text-xs ${inclusionClass(row.inclusion_status)}`}>
                      {row.inclusion_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <label className="inline-flex items-center gap-2 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={row.scan_enabled}
                        disabled={savingId === row.id || row.inclusion_status === "EXCLUDED"}
                        onChange={(e) => void patchPublisher(row.id, { scan_enabled: e.target.checked })}
                      />
                      {row.scan_enabled ? "On" : "Off"}
                    </label>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      className="w-20 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-xs text-slate-200"
                      defaultValue={row.scan_priority}
                      disabled={savingId === row.id}
                      onBlur={(e) => {
                        const next = Number(e.target.value);
                        if (!Number.isFinite(next) || next === row.scan_priority) return;
                        void patchPublisher(row.id, { scan_priority: next });
                      }}
                    />
                  </td>
                  <td className="px-4 py-3 text-slate-400">{row.classification_mode}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
