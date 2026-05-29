import type { OrganizationReviewResponse } from "../../../api/client";

type Props = {
  reviews: OrganizationReviewResponse[];
  selectedReviewId: number | null;
  onSelect: (reviewId: number) => void;
};

export function OrganizationReviewListPanel({ reviews, selectedReviewId, onSelect }: Props): JSX.Element {
  if (!reviews.length) {
    return <p className="text-sm text-slate-500">No organization reviews yet.</p>;
  }
  return (
    <ul className="space-y-2">
      {reviews.map((review) => (
        <li key={review.id}>
          <button
            type="button"
            onClick={() => onSelect(review.id)}
            className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition ${
              selectedReviewId === review.id
                ? "border-cyan-400/40 bg-cyan-500/10 text-white"
                : "border-white/10 bg-slate-950/40 text-slate-200 hover:bg-white/5"
            }`}
          >
            <p className="font-medium">
              Review #{review.id} · copy {review.inventory_item_id}
            </p>
            <p className="text-xs text-slate-500">
              {review.review_type} · {review.review_status}
              {review.approval_queue_name ? ` · ${review.approval_queue_name}` : ""}
            </p>
          </button>
        </li>
      ))}
    </ul>
  );
}
