import { useEffect, useState } from "react";

import { apiClient, type ImportLineCoverCandidateRead } from "../../api/client";

type ImportLineCoverPickerProps = {
  importId: number;
  lineIndex: number;
  open: boolean;
  onClose: () => void;
  onSelected: () => void;
};

export function ImportLineCoverPicker({
  importId,
  lineIndex,
  open,
  onClose,
  onSelected,
}: ImportLineCoverPickerProps): JSX.Element | null {
  const [candidates, setCandidates] = useState<ImportLineCoverCandidateRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void apiClient
      .listImportLineCoverCandidates(importId, lineIndex)
      .then((rows) => {
        if (!cancelled) {
          setCandidates(rows);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Could not load catalog covers for this line.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [importId, lineIndex, open]);

  if (!open) {
    return null;
  }

  async function pickCandidate(variantId: number): Promise<void> {
    setBusyId(variantId);
    try {
      await apiClient.selectImportLineCoverCandidate(importId, lineIndex, variantId);
      onSelected();
      onClose();
    } catch {
      setError("Could not apply that cover. Try again or upload a scan.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="Choose catalog cover"
    >
      <div className="max-h-[80vh] w-full max-w-lg overflow-hidden rounded-2xl border border-slate-600 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-700 px-4 py-3">
          <h3 className="text-sm font-semibold text-white">Choose catalog cover</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
          >
            Close
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto p-4">
          {loading ? <p className="text-sm text-slate-400">Loading variants…</p> : null}
          {error ? <p className="text-sm text-rose-300">{error}</p> : null}
          {!loading && !error && candidates.length === 0 ? (
            <p className="text-sm text-slate-400">No catalog variants found for this line yet.</p>
          ) : null}
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {candidates.map((row) => {
              const label =
                row.cover_label ||
                row.variant_name ||
                (row.cover_letter ? `Cover ${row.cover_letter.toUpperCase()}` : "Variant");
              return (
                <li key={row.external_variant_id}>
                  <button
                    type="button"
                    disabled={busyId !== null}
                    onClick={() => void pickCandidate(row.external_variant_id)}
                    className="w-full rounded-xl border border-slate-600 bg-slate-950 p-2 text-left transition hover:border-cyan-400/50 disabled:opacity-50"
                  >
                    {row.image_url ? (
                      <img
                        src={row.image_url}
                        alt=""
                        className="mx-auto h-24 w-16 rounded object-cover bg-slate-800"
                      />
                    ) : (
                      <div className="mx-auto flex h-24 w-16 items-center justify-center rounded bg-slate-800 text-[10px] text-slate-500">
                        No art
                      </div>
                    )}
                    <p className="mt-2 truncate text-xs font-medium text-white">{label}</p>
                    {row.artist ? (
                      <p className="truncate text-[10px] text-slate-400">{row.artist}</p>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
