import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  scannerRecommendedUseLabel,
  type ScannerProfileCreatePayload,
  type ScannerProfileHardwareType,
  type ScannerProfileRead,
  type ScannerRecommendedUse,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../auth/AuthContext";

function defaultCreatePayload(): ScannerProfileCreatePayload {
  return {
    profile_name: "",
    scanner_type: "generic_flatbed",
    dpi: null,
    color_mode: "color",
    file_format: "png",
    duplex_enabled: false,
    feeder_enabled: false,
    recommended_use: "bulk_ingest",
    is_default: false,
    notes: "",
  };
}

export function ScannerProfilesPage() {
  const { user } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState<ScannerProfileRead[]>([]);
  const [createDraft, setCreateDraft] = useState<ScannerProfileCreatePayload>(() => defaultCreatePayload());
  const [editing, setEditing] = useState<ScannerProfileRead | null>(null);
  const [editDraft, setEditDraft] = useState<ScannerProfileCreatePayload>(() => defaultCreatePayload());

  const sortedItems = useMemo(() => [...items], [items]);

  const reload = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const rsp = await apiClient.listScannerProfiles();
      setItems(rsp.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to load scanner profiles.");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function submitCreate(ev: FormEvent): Promise<void> {
    ev.preventDefault();
    if (!createDraft.profile_name.trim()) {
      setError("Profile name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiClient.createScannerProfile({
        ...createDraft,
        profile_name: createDraft.profile_name.trim(),
        dpi: createDraft.dpi === null || createDraft.dpi === undefined ? null : Number(createDraft.dpi),
        notes: createDraft.notes?.trim() || null,
      });
      setCreateDraft(defaultCreatePayload());
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to create profile.");
    } finally {
      setBusy(false);
    }
  }

  async function duplicateProfile(row: ScannerProfileRead): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await apiClient.createScannerProfile({
        profile_name: `${row.profile_name} copy`,
        scanner_type: row.scanner_type,
        dpi: row.dpi,
        color_mode: row.color_mode,
        file_format: row.file_format,
        duplex_enabled: row.duplex_enabled,
        feeder_enabled: row.feeder_enabled,
        recommended_use: row.recommended_use as ScannerRecommendedUse,
        notes: row.notes,
        is_default: false,
      });
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to duplicate profile.");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(ev: FormEvent): Promise<void> {
    ev.preventDefault();
    if (!editing) return;
    if (!editDraft.profile_name.trim()) {
      setError("Profile name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiClient.updateScannerProfile(editing.id, {
        ...editDraft,
        profile_name: editDraft.profile_name.trim(),
        dpi: editDraft.dpi === null || editDraft.dpi === undefined ? null : Number(editDraft.dpi),
        notes: editDraft.notes?.trim() ? editDraft.notes.trim() : null,
      });
      setEditing(null);
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to update profile.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteProfile(row: ScannerProfileRead): Promise<void> {
    if (row.owner_user_id === null) return;
    if (!window.confirm(`Delete preset “${row.profile_name}”?`)) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.deleteScannerProfile(row.id);
      if (editing?.id === row.id) setEditing(null);
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to delete profile.");
    } finally {
      setBusy(false);
    }
  }

  function beginEdit(row: ScannerProfileRead): void {
    if (row.owner_user_id === null) return;
    setEditing(row);
    setEditDraft({
      profile_name: row.profile_name,
      scanner_type: row.scanner_type as ScannerProfileHardwareType,
      dpi: row.dpi,
      color_mode: row.color_mode,
      file_format: row.file_format,
      duplex_enabled: row.duplex_enabled,
      feeder_enabled: row.feeder_enabled,
      recommended_use: row.recommended_use as ScannerRecommendedUse,
      is_default: row.is_default,
      notes: row.notes ?? "",
    });
    setError(null);
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Settings"
        title="Scanner presets"
        description="Metadata-only profiles for documenting capture intent (drivers are configured outside ComicOS)."
        actions={
          <div className="flex flex-wrap gap-3">
            <Link
              to="/scan-sessions"
              className="inline-flex rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300/35 hover:bg-white/5"
            >
              Scan sessions
            </Link>
            <Link
              to="/settings/integrations"
              className="inline-flex rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300/35 hover:bg-white/5"
            >
              Integrations
            </Link>
            <span className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-xs text-slate-400">
              {user?.email}
            </span>
          </div>
        }
      />

      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-6">
          <h2 className="text-lg font-semibold text-slate-900">Add custom preset</h2>
          <p className="mt-2 text-xs text-slate-400">
            Stored as configuration notes only — ComicOS never talks to scanners or modifies images automatically.
          </p>
          <form className="mt-6 space-y-4" onSubmit={(e) => void submitCreate(e)}>
            <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Name
              <input
                required
                className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/65 px-3 py-2 text-sm text-white"
                value={createDraft.profile_name}
                onChange={(e) => setCreateDraft({ ...createDraft, profile_name: e.target.value })}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                Scanner type
                <select
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/65 px-3 py-2 text-sm text-white"
                  value={createDraft.scanner_type}
                  onChange={(e) =>
                    setCreateDraft({ ...createDraft, scanner_type: e.target.value as ScannerProfileHardwareType })
                  }
                >
                  <option value="fujitsu_bulk">Fujitsu bulk</option>
                  <option value="epson_high_res">Epson high-res</option>
                  <option value="generic_flatbed">Generic flatbed</option>
                  <option value="manual_upload">Manual upload</option>
                </select>
              </label>
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                DPI (optional)
                <input
                  type="number"
                  min={72}
                  max={9600}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/65 px-3 py-2 text-sm text-white"
                  value={createDraft.dpi ?? ""}
                  onChange={(e) =>
                    setCreateDraft({
                      ...createDraft,
                      dpi: e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                />
              </label>
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                Format
                <select
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/65 px-3 py-2 text-sm text-white"
                  value={createDraft.file_format}
                  onChange={(e) => setCreateDraft({ ...createDraft, file_format: e.target.value as ScannerProfileCreatePayload["file_format"] })}
                >
                  <option value="png">PNG</option>
                  <option value="jpg">JPEG</option>
                  <option value="tif">TIFF</option>
                </select>
              </label>
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                Color mode
                <select
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/65 px-3 py-2 text-sm text-white"
                  value={createDraft.color_mode}
                  onChange={(e) => setCreateDraft({ ...createDraft, color_mode: e.target.value as ScannerProfileCreatePayload["color_mode"] })}
                >
                  <option value="color">Color</option>
                  <option value="grayscale">Grayscale</option>
                  <option value="black_and_white">Black & white</option>
                </select>
              </label>
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                Recommended use
                <select
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-950/65 px-3 py-2 text-sm text-white"
                  value={createDraft.recommended_use}
                  onChange={(e) =>
                    setCreateDraft({
                      ...createDraft,
                      recommended_use: e.target.value as ScannerRecommendedUse,
                    })
                  }
                >
                  <option value="bulk_ingest">Bulk ingest</option>
                  <option value="high_res_review">High-res review</option>
                  <option value="intake_receiving">Intake receiving</option>
                  <option value="archival_scan">Archival scan</option>
                </select>
              </label>
              <label className="flex items-center gap-2 pt-8 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(createDraft.is_default)}
                  onChange={(e) => setCreateDraft({ ...createDraft, is_default: e.target.checked })}
                />
                Primary default preset for my account
              </label>
            </div>
            <div className="flex gap-6 text-xs text-slate-300">
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={Boolean(createDraft.duplex_enabled)}
                  onChange={(e) => setCreateDraft({ ...createDraft, duplex_enabled: e.target.checked })}
                />
                Duplex
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={Boolean(createDraft.feeder_enabled)}
                  onChange={(e) => setCreateDraft({ ...createDraft, feeder_enabled: e.target.checked })}
                />
                Feeder
              </label>
            </div>
            <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Notes
              <textarea
                className="mt-2 min-h-[4rem] w-full rounded-2xl border border-white/10 bg-slate-950/65 px-3 py-2 text-sm text-white"
                value={createDraft.notes ?? ""}
                onChange={(e) => setCreateDraft({ ...createDraft, notes: e.target.value })}
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-2xl border border-cyan-400/35 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:opacity-50"
            >
              Save preset
            </button>
          </form>
        </section>

        <section className="rounded-3xl border border-white/10 bg-slate-900/55 p-6">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-slate-900">Library</h2>
            <button
              type="button"
              onClick={() => void reload()}
              className="rounded-2xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-200 hover:border-white/25 disabled:opacity-50"
              disabled={busy}
            >
              Reload
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {sortedItems.length === 0 ? (
              <p className="text-sm text-slate-600">Loading presets…</p>
            ) : (
              sortedItems.map((row) => (
                <div
                  key={row.id}
                  className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-200"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-white">{row.profile_name}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        <span className="rounded-lg border border-white/15 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">
                          {scannerRecommendedUseLabel(row.recommended_use)}
                        </span>
                        {" · "}
                        {row.dpi ? `${row.dpi} dpi` : "dpi unstated"}
                        {" · "}
                        {row.file_format.toUpperCase()}
                      </p>
                      {row.notes ? <p className="mt-2 text-xs italic text-slate-500">{row.notes}</p> : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-xl border border-violet-400/35 bg-violet-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-violet-100">
                        {row.owner_user_id === null ? "Suggested" : row.is_default ? "Default" : "Custom"}
                      </span>
                      <button
                        type="button"
                        className="rounded-xl border border-white/15 px-3 py-1 text-[11px] font-semibold text-slate-200 hover:border-white/30 disabled:opacity-40"
                        onClick={() => void duplicateProfile(row)}
                        disabled={busy}
                      >
                        Duplicate
                      </button>
                      {row.owner_user_id !== null ? (
                        <>
                          <button
                            type="button"
                            className="rounded-xl border border-white/15 px-3 py-1 text-[11px] font-semibold text-slate-200 hover:border-white/30 disabled:opacity-40"
                            onClick={() => beginEdit(row)}
                            disabled={busy}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="rounded-xl border border-rose-400/30 px-3 py-1 text-[11px] font-semibold text-rose-100 hover:bg-rose-500/15 disabled:opacity-40"
                            onClick={() => void deleteProfile(row)}
                            disabled={busy}
                          >
                            Delete
                          </button>
                        </>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {editing ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/65 p-4">
          <div className="max-h-[90vh] w-full max-w-xl overflow-auto rounded-3xl border border-white/15 bg-slate-950 p-6 shadow-2xl">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-slate-900">Edit preset</h3>
              <button type="button" className="text-sm text-slate-400 underline" onClick={() => setEditing(null)}>
                Close
              </button>
            </div>
            <form className="mt-6 space-y-4" onSubmit={(e) => void saveEdit(e)}>
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                Name
                <input
                  required
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                  value={editDraft.profile_name}
                  onChange={(e) => setEditDraft({ ...editDraft, profile_name: e.target.value })}
                />
              </label>
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                Scanner type
                <select
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                  value={editDraft.scanner_type}
                  onChange={(e) =>
                    setEditDraft({ ...editDraft, scanner_type: e.target.value as ScannerProfileHardwareType })
                  }
                >
                  <option value="fujitsu_bulk">Fujitsu bulk</option>
                  <option value="epson_high_res">Epson high-res</option>
                  <option value="generic_flatbed">Generic flatbed</option>
                  <option value="manual_upload">Manual upload</option>
                </select>
              </label>
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                DPI
                <input
                  type="number"
                  min={72}
                  max={9600}
                  className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white"
                  value={editDraft.dpi ?? ""}
                  onChange={(e) =>
                    setEditDraft({
                      ...editDraft,
                      dpi: e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                />
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(editDraft.is_default)}
                  onChange={(e) => setEditDraft({ ...editDraft, is_default: e.target.checked })}
                />
                Primary default preset for my account
              </label>
              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  className="rounded-2xl border border-white/10 px-4 py-2 text-sm text-slate-200"
                  onClick={() => setEditing(null)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-2xl border border-cyan-400/35 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
                >
                  Save changes
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
