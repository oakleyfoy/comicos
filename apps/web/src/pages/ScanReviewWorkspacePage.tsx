import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ScanReviewSessionDetail,
  type ScanVisualEvidenceRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ScanReviewWorkspacePage() {
  const [visualRuns, setVisualRuns] = useState<ScanVisualEvidenceRunRead[]>([]);
  const [selectedVisualRunId, setSelectedVisualRunId] = useState<number | null>(null);
  const [run, setRun] = useState<ScanReviewSessionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [decisionType, setDecisionType] = useState("IDENTITY_CONFIRMATION");
  const [decisionStatus, setDecisionStatus] = useState("ACCEPTED");
  const [decisionValue, setDecisionValue] = useState("CONFIRMED");
  const [decisionReason, setDecisionReason] = useState("Reviewed current evidence package.");

  const [noteType, setNoteType] = useState("GENERAL");
  const [noteText, setNoteText] = useState("Reviewer note.");

  const [actionType, setActionType] = useState("MARK_REVIEWED");
  const [actionStatus, setActionStatus] = useState("ACTIVE");
  const [actionReason, setActionReason] = useState("Reviewed during workspace session.");

  useEffect(() => {
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanVisualEvidenceRuns({ limit: 20, offset: 0 });
        if (ignore) return;
        const complete = response.items.filter((row) => row.evidence_status === "COMPLETE");
        setVisualRuns(complete);
        setSelectedVisualRunId(complete[0]?.id ?? null);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load visual evidence runs.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    const selected = visualRuns.find((row) => row.id === selectedVisualRunId);
    if (!selected) {
      setRun(null);
      return;
    }
    let ignore = false;
    void (async () => {
      try {
        const response = await apiClient.listScanReviewSessions({ scan_image_id: selected.scan_image_id, limit: 1, offset: 0 });
        if (ignore || !response.items[0]) {
          if (!ignore) setRun(null);
          return;
        }
        const detail = await apiClient.getScanReviewSession(response.items[0].id);
        if (!ignore) setRun(detail);
      } catch (loadErr) {
        if (!ignore) setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load review sessions.");
      }
    })();
    return () => {
      ignore = true;
    };
  }, [selectedVisualRunId, visualRuns]);

  const selectedVisualRun = useMemo(
    () => visualRuns.find((row) => row.id === selectedVisualRunId) ?? null,
    [selectedVisualRunId, visualRuns],
  );

  async function createSession(): Promise<void> {
    if (!selectedVisualRun) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await apiClient.createScanReviewSession({
        scan_image_id: selectedVisualRun.scan_image_id,
        visual_evidence_run_id: selectedVisualRun.id,
        grading_assistance_run_id: selectedVisualRun.grading_assistance_run_id ?? null,
      });
      setRun(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create review session.");
    } finally {
      setLoading(false);
    }
  }

  async function submitDecision(): Promise<void> {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await apiClient.recordScanReviewDecision(run.id, {
        decision_type: decisionType,
        decision_status: decisionStatus,
        decision_value: decisionValue,
        reason_text: decisionReason,
        metadata_json: {},
      });
      setRun(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to record review decision.");
    } finally {
      setLoading(false);
    }
  }

  async function submitNote(): Promise<void> {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await apiClient.recordScanReviewNote(run.id, {
        note_type: noteType,
        note_text: noteText,
        metadata_json: {},
      });
      setRun(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to record review note.");
    } finally {
      setLoading(false);
    }
  }

  async function submitEvidenceAction(): Promise<void> {
    if (!run) return;
    const target = (run.review_snapshot.visual_evidence_summary as Record<string, unknown> | undefined)?.visual_evidence_run_id;
    setLoading(true);
    setError(null);
    try {
      const detail = await apiClient.recordScanReviewEvidenceAction(run.id, {
        source_system: "P40_13_VISUAL_EVIDENCE",
        source_record_id: Number(target ?? 1),
        action_type: actionType,
        action_status: actionStatus,
        reason_text: actionReason,
        metadata_json: {},
      });
      setRun(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to record evidence action.");
    } finally {
      setLoading(false);
    }
  }

  async function completeSession(): Promise<void> {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await apiClient.completeScanReviewSession(run.id);
      setRun(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to complete review session.");
    } finally {
      setLoading(false);
    }
  }

  const visualSummary = (run?.review_snapshot.visual_evidence_summary as Record<string, unknown> | undefined) ?? {};
  const gradingSummary = (run?.review_snapshot.grading_assistance_summary as Record<string, unknown> | undefined) ?? {};
  const reconciliationSummary = (run?.review_snapshot.reconciliation_summary as Record<string, unknown> | undefined) ?? {};

  return (
    <AppShell>
      <PageHeader
        eyebrow="P40-14"
        title="Review Workspace"
        description="Human review layer for scan intelligence, evidence, and grading support."
        actions={
          <div className="flex gap-2">
            <Link to="/scan-visual-evidence" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Visual evidence
            </Link>
            <Link to="/ops#scan-review-ops" className="rounded-2xl border border-amber-400/35 px-4 py-2 text-sm font-semibold text-amber-100">
              Ops diagnostics
            </Link>
          </div>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5">
        <div className="grid gap-4 xl:grid-cols-[1fr,1.2fr]">
          <div className="space-y-4">
            <label className="block text-xs font-semibold text-slate-300">
              Visual evidence run
              <select
                value={selectedVisualRunId ?? ""}
                onChange={(event) => setSelectedVisualRunId(Number(event.target.value) || null)}
                className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
              >
                {visualRuns.map((visualRun) => (
                  <option key={visualRun.id} value={visualRun.id}>
                    Scan #{visualRun.scan_image_id} · visual #{visualRun.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={loading || !selectedVisualRun}
              onClick={() => void createSession()}
              className="rounded-2xl bg-amber-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45"
            >
              {loading ? "Working…" : "Create / load review session"}
            </button>
            {run ? (
              <p className="text-xs text-slate-400">
                Status <span className="font-semibold text-white">{run.review_status}</span> · reviewer{" "}
                <span className="font-semibold text-white">{run.reviewer_user_id ?? "—"}</span>
              </p>
            ) : null}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <PreviewCard title="Source preview" src={run?.source_preview_data_url ?? null} />
            <PreviewCard
              title="Review preview"
              src={run?.artifacts.find((artifact) => artifact.artifact_type === "REVIEW_DEBUG_PREVIEW")?.preview_data_url ?? null}
            />
          </div>
        </div>
      </section>

      {!run ? (
        <div className="mt-6">
          <EmptyState
            title="No review session loaded"
            description="Create a review session from an existing visual evidence run to inspect evidence, add notes, record reviewer decisions, and complete the session without mutating upstream evidence."
          />
        </div>
      ) : (
        <>
          <section className="mt-6 grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
            <Panel title="Evidence viewer">
              <p className="text-sm text-slate-300">
                Visual evidence run #{String(visualSummary.visual_evidence_run_id ?? "—")} · package count {String(visualSummary.package_count ?? 0)} · issues {String(visualSummary.issue_count ?? 0)}
              </p>
              <p className="mt-2 text-xs text-slate-400">Review snapshot is deterministic and always reflects immutable upstream evidence plus append-only reviewer records.</p>
            </Panel>
            <Panel title="Identity review panel">
              <p className="text-sm text-slate-300">
                Reconciliation run #{String(reconciliationSummary.reconciliation_run_id ?? "—")} · status {String(reconciliationSummary.reconciliation_status ?? "missing")}
              </p>
              <p className="mt-2 text-xs text-slate-400">
                Final confidence {Number(reconciliationSummary.final_confidence_score ?? 0).toFixed(3)}
              </p>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,1fr]">
            <Panel title="Grading support review panel">
              <p className="text-sm text-slate-300">
                Grading run #{String(gradingSummary.grading_assistance_run_id ?? "—")} · status {String(gradingSummary.assistance_status ?? "missing")}
              </p>
              <pre className="mt-3 max-h-64 overflow-auto rounded-xl border border-white/10 bg-slate-950/50 p-3 text-[10px] text-amber-100">
                {JSON.stringify(gradingSummary.overall_support ?? {}, null, 2)}
              </pre>
            </Panel>
            <Panel title="Review checklist">
              <ul className="space-y-2 text-xs text-slate-200">
                <li>Identity reviewed: {run.decisions.some((d) => d.decision_type === "IDENTITY_CONFIRMATION") ? "yes" : "no"}</li>
                <li>Evidence reviewed: {run.evidence_actions.length > 0 ? "yes" : "no"}</li>
                <li>Scan quality reviewed: {run.decisions.some((d) => d.decision_type === "SCAN_QUALITY_DECISION") ? "yes" : "no"}</li>
                <li>Grading support reviewed: {run.decisions.some((d) => d.decision_type.includes("SUPPORT_RANGE")) ? "yes" : "no"}</li>
                <li>Open issues: {run.issues.length}</li>
              </ul>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-3">
            <Panel title="Decision recorder">
              <FormSelect label="Type" value={decisionType} onChange={setDecisionType} options={["IDENTITY_CONFIRMATION", "REVIEW_REQUIRED_CLEARANCE", "SUPPORT_RANGE_ACCEPTANCE", "SCAN_QUALITY_DECISION"]} />
              <FormSelect label="Status" value={decisionStatus} onChange={setDecisionStatus} options={["ACCEPTED", "REJECTED", "OVERRIDDEN", "NEEDS_REVIEW", "NOT_APPLICABLE"]} />
              <FormInput label="Value" value={decisionValue} onChange={setDecisionValue} />
              <FormArea label="Reason" value={decisionReason} onChange={setDecisionReason} />
              <ActionButton onClick={() => void submitDecision()} disabled={loading}>Record decision</ActionButton>
            </Panel>
            <Panel title="Notes panel">
              <FormSelect label="Type" value={noteType} onChange={setNoteType} options={["GENERAL", "IDENTITY", "CONDITION", "SCAN_QUALITY", "GRADING_SUPPORT", "AUTHENTICATION_PREP"]} />
              <FormArea label="Note" value={noteText} onChange={setNoteText} />
              <ActionButton onClick={() => void submitNote()} disabled={loading}>Add note</ActionButton>
            </Panel>
            <Panel title="Evidence actions panel">
              <FormSelect label="Action" value={actionType} onChange={setActionType} options={["MARK_REVIEWED", "FLAG_EVIDENCE", "CLEAR_FLAG", "REQUEST_RESCAN", "ACCEPT_EVIDENCE", "REJECT_EVIDENCE"]} />
              <FormSelect label="Status" value={actionStatus} onChange={setActionStatus} options={["ACTIVE", "SUPERSEDED", "CLEARED"]} />
              <FormArea label="Reason" value={actionReason} onChange={setActionReason} />
              <ActionButton onClick={() => void submitEvidenceAction()} disabled={loading}>Record action</ActionButton>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Decision history">
              <ul className="space-y-2 text-xs text-slate-200">
                {run.decisions.map((decision) => (
                  <li key={decision.id} className="rounded-xl border border-white/10 px-3 py-2">
                    <span className="font-semibold text-amber-100">{decision.decision_type}</span> · {decision.decision_status} · {decision.decision_value}
                    <p className="mt-1 text-slate-400">{decision.reason_text}</p>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Notes history">
              <ul className="space-y-2 text-xs text-slate-200">
                {run.notes.map((note) => (
                  <li key={note.id} className="rounded-xl border border-white/10 px-3 py-2">
                    <span className="font-semibold text-amber-100">{note.note_type}</span>
                    <p className="mt-1 text-slate-400">{note.note_text}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-2">
            <Panel title="Issues panel">
              <ul className="space-y-2 text-xs text-slate-200">
                {run.issues.map((issue) => (
                  <li key={issue.id} className="rounded-xl border border-white/10 px-3 py-2">
                    <span className="font-semibold text-amber-100">{issue.issue_type}</span> · {issue.severity} · {issue.issue_message}
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Lineage panel">
              <ChecksumRow label="Snapshot checksum" value={run.snapshot_checksum} />
              <ChecksumRow label="Review checksum" value={run.review_checksum} />
              <ChecksumRow label="Visual evidence checksum" value={run.visual_evidence_checksum ?? "—"} />
              <ChecksumRow label="Grading assistance checksum" value={run.grading_assistance_checksum ?? "—"} />
            </Panel>
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1fr,0.4fr]">
            <Panel title="History timeline">
              <ul className="space-y-2 text-xs text-slate-300">
                {run.history.map((event) => (
                  <li key={event.id} className="rounded-xl border border-white/10 px-3 py-2">
                    <p className="font-semibold text-white">{event.event_type}</p>
                    <p>{event.event_message}</p>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Completion">
              <ActionButton onClick={() => void completeSession()} disabled={loading || run.review_status === "REVIEW_COMPLETE"}>
                Complete review
              </ActionButton>
            </Panel>
          </section>
        </>
      )}
    </AppShell>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function PreviewCard({ title, src }: { title: string; src: string | null }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-xs font-semibold text-white">{title}</p>
      {src ? (
        <img src={src} alt={title} className="mt-2 h-32 w-full rounded-xl border border-white/10 object-contain bg-slate-950/50" />
      ) : (
        <p className="mt-2 text-xs text-slate-500">Preview unavailable.</p>
      )}
    </div>
  );
}

function ChecksumRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="mb-2 rounded-xl border border-white/10 bg-slate-950/40 p-2">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 break-all font-mono text-[10px] text-white">{value}</p>
    </div>
  );
}

function FormSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}): JSX.Element {
  return (
    <label className="mb-3 block text-xs font-semibold text-slate-300">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white">
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function FormInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }): JSX.Element {
  return (
    <label className="mb-3 block text-xs font-semibold text-slate-300">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white" />
    </label>
  );
}

function FormArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }): JSX.Element {
  return (
    <label className="mb-3 block text-xs font-semibold text-slate-300">
      {label}
      <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={4} className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white" />
    </label>
  );
}

function ActionButton({ onClick, disabled, children }: { onClick: () => void; disabled: boolean; children: ReactNode }): JSX.Element {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className="rounded-2xl bg-amber-400 px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-950 disabled:opacity-45">
      {children}
    </button>
  );
}

