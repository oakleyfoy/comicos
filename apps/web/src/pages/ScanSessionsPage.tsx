import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanSessionDetail,
  type ScanSessionIngestManifest,
  type ScanSessionItemsListResponse,
  type ScanSessionQaSummaryRead,
  type ScanSessionSummary,
  type ScanQaClassification,
  type ScanQaItemRead,
  type ScanQaRoutingRecommendation,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../auth/AuthContext";

function formatSha(hex: string | null | undefined): string {
  if (!hex) return "—";
  return `${hex.slice(0, 12)}…`;
}

const SCAN_QA_CLASSIFICATIONS: ScanQaClassification[] = [
  "ready_for_ocr",
  "needs_high_res_review",
  "needs_rescan",
  "corrupt_or_unreadable",
  "duplicate_scan",
  "low_resolution",
  "low_contrast",
  "blurry",
  "already_processed",
  "review_required",
];

const SCAN_QA_ROUTINGS: ScanQaRoutingRecommendation[] = [
  "queue_for_ocr",
  "send_to_high_res_review",
  "request_rescan",
  "hold_for_manual_review",
  "no_action_needed",
];

function qaClassChipTone(cls: ScanQaClassification): string {
  switch (cls) {
    case "ready_for_ocr":
    case "already_processed":
      return "border-emerald-400/40 bg-emerald-400/15 text-emerald-100";
    case "duplicate_scan":
      return "border-slate-400/35 bg-slate-500/10 text-slate-100";
    case "needs_high_res_review":
    case "needs_rescan":
    case "low_resolution":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "corrupt_or_unreadable":
      return "border-rose-400/35 bg-rose-500/10 text-rose-100";
    default:
      return "border-violet-400/35 bg-violet-400/10 text-violet-100";
  }
}

function qaRouteChipTone(route: ScanQaRoutingRecommendation): string {
  switch (route) {
    case "queue_for_ocr":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "send_to_high_res_review":
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
    case "request_rescan":
      return "border-orange-400/35 bg-orange-400/15 text-orange-100";
    case "hold_for_manual_review":
      return "border-rose-400/35 bg-rose-500/10 text-rose-100";
    case "no_action_needed":
      return "border-white/15 bg-white/5 text-slate-200";
    default:
      return "border-white/15 bg-white/5 text-slate-200";
  }
}

export function ScanSessionsPage() {
  const { user } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const [sessionIdDraft, setSessionIdDraft] = useState("");
  const [sessions, setSessions] = useState<ScanSessionSummary[]>([]);
  const [itemsPayload, setItemsPayload] = useState<ScanSessionItemsListResponse | null>(null);
  const [lastDetail, setLastDetail] = useState<ScanSessionDetail | null>(null);
  const [manifestJson, setManifestJson] = useState('{\n  "items": []\n}');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [qaSummary, setQaSummary] = useState<ScanSessionQaSummaryRead | null>(null);
  const [qaClassFilter, setQaClassFilter] = useState<ScanQaClassification | "">("");
  const [qaRouteFilter, setQaRouteFilter] = useState<ScanQaRoutingRecommendation | "">("");

  const numericSessionId = useMemo(() => {
    const n = Number(sessionIdDraft.trim());
    return Number.isInteger(n) && n > 0 ? n : null;
  }, [sessionIdDraft]);

  const qaByItemId = useMemo(() => {
    const rows = qaSummary?.items ?? [];
    return new Map<number, ScanQaItemRead>(
      rows.map((row): [number, ScanQaItemRead] => [row.scan_session_item_id, row]),
    );
  }, [qaSummary]);

  const filteredSessionItems = useMemo(() => {
    if (!itemsPayload) return [];
    return itemsPayload.items.filter((it) => {
      const qa = qaByItemId.get(it.id);
      if (!qa) return !(qaClassFilter || qaRouteFilter);
      if (qaClassFilter && qa.qa_classification !== qaClassFilter) return false;
      if (qaRouteFilter && qa.routing_recommendation !== qaRouteFilter) return false;
      return true;
    });
  }, [itemsPayload, qaByItemId, qaClassFilter, qaRouteFilter]);

  const reloadSessions = useCallback(async () => {
    setBusyKey("sessions");
    setError(null);
    try {
      const list = await apiClient.listScanSessions({ limit: 50, offset: 0 });
      setSessions(list.sessions);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "Unable to list scan sessions.");
    } finally {
      setBusyKey(null);
    }
  }, []);

  useEffect(() => {
    void reloadSessions();
  }, [reloadSessions]);

  async function reloadItems(forId?: number): Promise<void> {
    const sid = forId ?? numericSessionId;
    if (!sid) {
      setItemsPayload(null);
      setQaSummary(null);
      return;
    }
    setBusyKey(`items:${sid}`);
    setError(null);
    try {
      const rows = await apiClient.getScanSessionItems(sid, { limit: 500, offset: 0 });
      setItemsPayload(rows);
      const qa = await apiClient.getScanSessionQa(sid);
      setQaSummary(qa);
    } catch (loadError) {
      setItemsPayload(null);
      setQaSummary(null);
      setError(loadError instanceof ApiError ? loadError.message : "Unable to fetch session rows.");
    } finally {
      setBusyKey(null);
    }
  }

  async function runPersistedScanQa(): Promise<void> {
    if (!numericSessionId) {
      setError("Enter a numeric session id before running scan QA.");
      return;
    }
    setBusyKey("qa-run");
    setError(null);
    try {
      const qa = await apiClient.runScanSessionQa(numericSessionId);
      setQaSummary(qa);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "Unable to run scan QA persistence.");
    } finally {
      setBusyKey(null);
    }
  }

  async function createSessionPressed(): Promise<void> {
    setBusyKey("create");
    setError(null);
    try {
      const created = await apiClient.createScanSession({ session_type: "bulk_ingest" });
      setSessionIdDraft(String(created.id));
      await reloadSessions();
      await reloadItems(created.id);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "Unable to create scan session.");
    } finally {
      setBusyKey(null);
    }
  }

  async function ingestFilesSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!numericSessionId) {
      setError("Enter a numeric session id before uploading.");
      return;
    }
    if (selectedFiles.length === 0) {
      setError("Choose at least one scan file.");
      return;
    }
    let manifestParsed: ScanSessionIngestManifest;
    try {
      manifestParsed = JSON.parse(manifestJson) as ScanSessionIngestManifest;
    } catch {
      setError("Manifest must be JSON (see backend ScanSessionIngestManifest).");
      return;
    }
    setBusyKey("ingest");
    setError(null);
    try {
      const refreshed = await apiClient.ingestScanSessionFiles(numericSessionId, selectedFiles, manifestParsed);
      setLastDetail(refreshed);
      await reloadSessions();
      await reloadItems(numericSessionId);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "Ingest rejected.");
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Scan orchestration"
        title="Bulk scan ingest workspace"
        description="Deterministic feeder-style uploads into scan sessions — explicit inventory linkage only, no OCR auto-run, filenames never trusted blindly."
        actions={
          <>
            <Link
              to="/dashboard"
              className="inline-flex rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300/35 hover:bg-white/5"
            >
              Dashboard
            </Link>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-300">
              Signed in as <span className="font-semibold text-white">{user?.email ?? "unknown"}</span>
            </div>
          </>
        }
      />

      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15 xl:col-span-1">
          <h2 className="text-sm font-semibold text-white">Session controls</h2>
          <p className="mt-1 text-xs text-slate-400">
            Create a deterministic bulk session target, paste its numeric id from exports, refresh rows after each ingest batch.
          </p>
          <div className="mt-4 space-y-2">
            <button
              type="button"
              onClick={() => void createSessionPressed()}
              className="w-full rounded-2xl border border-cyan-400/35 bg-cyan-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-cyan-100 transition hover:bg-cyan-400/20 disabled:opacity-60"
              disabled={busyKey === "create"}
            >
              New Fujitsu ingest session
            </button>
            <button
              type="button"
              onClick={() => void reloadSessions()}
              className="w-full rounded-2xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-white/25 disabled:opacity-60"
              disabled={busyKey === "sessions"}
            >
              Reload recent sessions list
            </button>
          </div>
          <div className="mt-6">
            <label className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Active sessions</label>
            <div className="mt-2 max-h-44 space-y-1 overflow-auto rounded-xl border border-white/10 bg-slate-950/40 p-2 text-xs">
              {sessions.length === 0 ? (
                <p className="text-slate-500">No cached sessions loaded yet.</p>
              ) : (
                sessions.map((sess) => (
                  <button
                    key={sess.id}
                    type="button"
                    className={`flex w-full items-center justify-between rounded-lg px-2 py-1 text-left hover:bg-white/5 ${
                      numericSessionId === sess.id ? "bg-cyan-400/15 text-white" : "text-slate-300"
                    }`}
                    onClick={() => {
                      setSessionIdDraft(String(sess.id));
                      void reloadItems(sess.id);
                    }}
                  >
                    <span className="font-mono text-[11px]">#{sess.id}</span>
                    <span className="text-[10px] capitalize text-slate-400">{sess.status.replace(/_/g, " ")}</span>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <label className="flex min-w-[10rem] flex-1 flex-col text-xs font-semibold text-slate-300">
              Session ID
              <input
                className="mt-1 rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 font-mono text-sm text-white"
                value={sessionIdDraft}
                onChange={(e) => setSessionIdDraft(e.target.value)}
              />
            </label>
          </div>
          <button
            type="button"
            onClick={() => void reloadItems()}
            disabled={!numericSessionId || busyKey?.startsWith("items")}
            className="mt-3 w-full rounded-2xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-100 transition hover:border-cyan-300/35 disabled:opacity-50"
          >
            Fetch deterministic item table + rollups
          </button>
        </section>

        <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5 shadow-xl shadow-black/15 xl:col-span-2">
          <h2 className="text-sm font-semibold text-white">Multipart ingest ({selectedFiles.length} files staged)</h2>
          <p className="mt-1 text-xs text-slate-400">
            JSON manifest rows align positionally with multipart file order; omit entries to accept defaults (
            auto-increment sequential indices unless you collide—then ingest records a deterministic failure row).
          </p>
          <form className="mt-4 grid gap-3" onSubmit={(e) => void ingestFilesSubmit(e)}>
            <label className="text-xs font-semibold text-slate-300">
              Manifest JSON
              <textarea
                className="mt-1 h-36 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 font-mono text-[11px] text-emerald-100"
                spellCheck={false}
                value={manifestJson}
                onChange={(e) => setManifestJson(e.target.value)}
              />
            </label>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              multiple
              className="text-xs text-slate-300 file:rounded-lg file:border-0 file:bg-cyan-400/90 file:px-3 file:py-2 file:text-[11px] file:font-semibold file:text-slate-950"
              onChange={(e) => setSelectedFiles(e.target.files ? Array.from(e.target.files) : [])}
            />
            <button
              type="submit"
              disabled={
                busyKey === "ingest" || !numericSessionId || selectedFiles.length === 0
              }
              className="rounded-2xl bg-cyan-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 transition hover:bg-cyan-300 disabled:opacity-45"
            >
              POST /scan-sessions/{`{session}`}/ingest-files
            </button>
          </form>


          {!itemsPayload ? (
            <div className="mt-8">
              <EmptyState
                title="Awaiting deterministic session lookup"
                description="Enter a scan session identifier and reload items from the ingest panel above."
              />
            </div>
          ) : (
            <>
              <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Session #{itemsPayload.scan_session_id} · {itemsPayload.session_type.replace(/_/g, " ")} ·{" "}
                    <span className="capitalize text-slate-300">{itemsPayload.session_status.replace(/_/g, " ")}</span>
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Rollups retained per full session ledger (statistics), table below can be capped by API limit parameter.
                  </p>
                </div>
                <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-xl border border-white/10 px-3 py-2">
                    <p className="text-[10px] uppercase text-slate-500">Review required</p>
                    <p className="font-mono text-lg text-white">{itemsPayload.statistics.review_required}</p>
                  </div>
                  <div className="rounded-xl border border-white/10 px-3 py-2">
                    <p className="text-[10px] uppercase text-slate-500">Failures</p>
                    <p className="font-mono text-lg text-white">{itemsPayload.statistics.failures}</p>
                  </div>
                  <div className="rounded-xl border border-amber-300/35 px-3 py-2">
                    <p className="text-[10px] uppercase text-slate-500">Dup filenames</p>
                    <p className="font-mono text-lg text-white">
                      {itemsPayload.statistics.duplicate_filename_groups} groups / +
                      {itemsPayload.statistics.duplicate_filename_excess_rows} excess
                    </p>
                  </div>
                  <div className="rounded-xl border border-teal-300/35 px-3 py-2">
                    <p className="text-[10px] uppercase text-slate-500">Dup hashes</p>
                    <p className="font-mono text-lg text-white">
                      {itemsPayload.statistics.duplicate_image_hash_groups} groups / +
                      {itemsPayload.statistics.duplicate_image_hash_excess_rows} excess
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-end gap-3 rounded-2xl border border-violet-400/30 bg-violet-950/20 p-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-violet-200">Scan QA (deterministic routing)</p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    Signals only — QA never queues OCR automatically. Persist results for ops aggregates via Run QA snapshot.
                  </p>
                  {qaSummary ? (
                    <p className="mt-2 text-[10px] text-slate-500">
                      Last snapshot {qaSummary.persisted_run ? "(persisted in ledger)" : "(live compute only)"}.
                    </p>
                  ) : null}
                </div>
                <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
                  <span className="font-semibold uppercase tracking-[0.1em]">QA class filter</span>
                  <select
                    value={qaClassFilter}
                    onChange={(e) => setQaClassFilter((e.target.value || "") as ScanQaClassification | "")}
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-2 py-1 text-xs text-slate-100"
                  >
                    <option value="">Any</option>
                    {SCAN_QA_CLASSIFICATIONS.map((c) => (
                      <option key={c} value={c}>
                        {c.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex min-w-[9rem] flex-col gap-1 text-[11px] text-slate-400">
                  <span className="font-semibold uppercase tracking-[0.1em]">Routing filter</span>
                  <select
                    value={qaRouteFilter}
                    onChange={(e) =>
                      setQaRouteFilter((e.target.value || "") as ScanQaRoutingRecommendation | "")
                    }
                    className="rounded-xl border border-white/10 bg-slate-950/80 px-2 py-1 text-xs text-slate-100"
                  >
                    <option value="">Any</option>
                    {SCAN_QA_ROUTINGS.map((r) => (
                      <option key={r} value={r}>
                        {r.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  disabled={busyKey === "qa-run" || !numericSessionId}
                  onClick={() => void runPersistedScanQa()}
                  className="ml-auto rounded-2xl border border-violet-300/35 bg-violet-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-violet-100 transition hover:bg-violet-400/20 disabled:opacity-50"
                >
                  {busyKey === "qa-run" ? "Running QA…" : "Run QA snapshot"}
                </button>
              </div>

              <div className="mt-4 overflow-auto rounded-2xl border border-white/10">
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <tr>
                      <th className="p-3">Seq</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">QA class</th>
                      <th className="p-3">Routing</th>
                      <th className="p-3">Filename</th>
                      <th className="p-3">Dims</th>
                      <th className="p-3">SHA (short)</th>
                      <th className="p-3">Inventory</th>
                      <th className="p-3">Cover</th>
                      <th className="p-3">Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/10 text-slate-200">
                    {filteredSessionItems.map((item) => {
                      const qa = qaByItemId.get(item.id);
                      return (
                        <tr key={item.id} className="align-top hover:bg-white/5">
                          <td className="p-3 font-mono">{item.sequence_index}</td>
                          <td className="p-3 capitalize">{item.ingest_status.replace(/_/g, " ")}</td>
                          <td className="p-3">
                            {qa ? (
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${qaClassChipTone(qa.qa_classification)}`}
                              >
                                {qa.qa_classification.replace(/_/g, " ")}
                              </span>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="p-3">
                            {qa ? (
                              <span
                                className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${qaRouteChipTone(qa.routing_recommendation)}`}
                              >
                                {qa.routing_recommendation.replace(/_/g, " ")}
                              </span>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="p-3">{item.source_filename ?? "—"}</td>
                          <td className="p-3 font-mono text-[11px]">
                            {item.image_width && item.image_height ? `${item.image_width}×${item.image_height}` : "—"}
                          </td>
                          <td className="p-3 font-mono text-[11px]" title={item.image_sha256 ?? ""}>
                            {formatSha(item.image_sha256)}
                          </td>
                          <td className="p-3 font-mono text-[11px]">
                            {item.inventory_copy_id ? (
                              <Link
                                className="text-cyan-200 underline-offset-4 hover:underline"
                                to={`/inventory/${item.inventory_copy_id}`}
                              >
                                #{item.inventory_copy_id}
                              </Link>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="p-3 font-mono text-[11px]">{item.cover_image_id ? `#${item.cover_image_id}` : "—"}</td>
                          <td className="max-w-[16rem] p-3 text-[11px] text-rose-200/95">{item.ingest_error ?? "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <p className="mt-2 text-[11px] text-slate-500">
                Showing {filteredSessionItems.length} of {itemsPayload.items.length} rows after QA filters ({itemsPayload.items.length} deterministic rows from API). Last ingest summary refreshed{" "}
                {lastDetail?.updated_at ? new Date(lastDetail.updated_at).toLocaleString() : "—"}
              </p>
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}
