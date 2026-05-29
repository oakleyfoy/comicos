import type { OrganizationReviewDecisionResponse, OrganizationReviewResponse } from "../../../api/client";

type Props = {
  review: OrganizationReviewResponse | null;
  decisions: OrganizationReviewDecisionResponse[];
  canManage: boolean;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onAssign: () => void;
};

export function OrganizationReviewDetailPanel({
  review,
  decisions,
  canManage,
  busy,
  onApprove,
  onReject,
  onAssign,
}: Props): JSX.Element {
  if (!review) {
    return <p className="text-sm text-slate-500">Select a review to inspect approval state.</p>;
  }
  const terminal = review.review_status === "APPROVED" || review.review_status === "REJECTED" || review.review_status === "COMPLETED";
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-5 space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-white">Review #{review.id}</h3>
        <p className="text-sm text-slate-400">
          Copy {review.inventory_item_id} · {review.review_type} · {review.review_status}
        </p>
      </div>
      {canManage && !terminal ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onAssign}
            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-200 hover:bg-white/5 disabled:opacity-50"
          >
            Assign
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onApprove}
            className="rounded-lg border border-emerald-500/30 px-3 py-1.5 text-xs text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-50"
          >
            Approve
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onReject}
            className="rounded-lg border border-rose-500/30 px-3 py-1.5 text-xs text-rose-200 hover:bg-rose-500/10 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      ) : null}
      <div>
        <h4 className="text-xs uppercase tracking-[0.16em] text-slate-500">Decision lineage</h4>
        {!decisions.length ? <p className="mt-2 text-sm text-slate-500">No decisions recorded.</p> : null}
        <ul className="mt-2 space-y-2 text-sm">
          {decisions.map((row) => (
            <li key={row.id} className="rounded-lg border border-white/10 px-3 py-2">
              <p className="font-medium text-white">{row.decision_type}</p>
              <p className="text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
