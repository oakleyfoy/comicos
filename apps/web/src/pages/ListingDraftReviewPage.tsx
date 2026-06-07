import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError, apiClient, type P89ListingDraftRead } from "../api/client";
import { PatriotPageLayout } from "../components/PatriotPageLayout";

async function copyText(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

export function ListingDraftReviewPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const draftId = Number(id);
  const [draft, setDraft] = useState<P89ListingDraftRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!Number.isFinite(draftId)) return;
    setLoading(true);
    setError(null);
    try {
      setDraft(await apiClient.getListingDraft(draftId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Draft not found.");
    } finally {
      setLoading(false);
    }
  }, [draftId]);

  useEffect(() => {
    void load();
  }, [load]);

  function updateField<K extends keyof P89ListingDraftRead>(key: K, value: P89ListingDraftRead[K]) {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function save() {
    if (!draft) return;
    setSaving(true);
    setMessage(null);
    try {
      const updated = await apiClient.patchListingDraft(draft.id, {
        title: draft.title,
        description: draft.description,
        condition_notes: draft.condition_notes,
        shipping_notes: draft.shipping_notes,
        suggested_price: draft.suggested_price ?? undefined,
        minimum_price: draft.minimum_price ?? undefined,
        premium_price: draft.premium_price ?? undefined,
      });
      setDraft(updated);
      setMessage("Draft saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save draft.");
    } finally {
      setSaving(false);
    }
  }

  async function markReviewed() {
    if (!draft) return;
    const updated = await apiClient.markListingDraftReviewed(draft.id);
    setDraft(updated);
    setMessage("Marked as reviewed.");
  }

  async function archiveDraft() {
    if (!draft) return;
    await apiClient.patchListingDraft(draft.id, { status: "ARCHIVED" });
    void navigate("/listing-drafts");
  }

  if (loading) {
    return (
      <PatriotPageLayout eyebrow="Sell" title="Listing draft" showExpansionNav>
        <p className="text-sm text-blue-100">Loading…</p>
      </PatriotPageLayout>
    );
  }

  if (!draft) {
    return (
      <PatriotPageLayout eyebrow="Sell" title="Listing draft" error={error} showExpansionNav>
        <Link to="/listing-drafts" className="text-blue-200 underline">
          Back to drafts
        </Link>
      </PatriotPageLayout>
    );
  }

  return (
    <PatriotPageLayout
      eyebrow="Sell"
      title="Review listing draft"
      description={draft.comic_title}
      showExpansionNav
      error={error}
      headerActions={
        <Link to="/listing-drafts" className="text-sm text-blue-100 underline">
          All drafts
        </Link>
      }
    >
      {message ? <p className="mb-4 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{message}</p> : null}
      {draft.pricing_unavailable ? (
        <p className="mb-4 text-sm text-amber-100">Pricing unavailable.</p>
      ) : null}
      <div className="space-y-4 rounded-lg border border-blue-800 bg-white p-4 text-blue-950">
        <label className="block text-sm">
          Title
          <input
            className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
            value={draft.title}
            onChange={(e) => updateField("title", e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Description
          <textarea
            className="mt-1 min-h-40 w-full rounded border border-blue-200 px-2 py-1.5"
            value={draft.description}
            onChange={(e) => updateField("description", e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Condition notes
          <textarea
            className="mt-1 min-h-20 w-full rounded border border-blue-200 px-2 py-1.5"
            value={draft.condition_notes}
            onChange={(e) => updateField("condition_notes", e.target.value)}
          />
        </label>
        <label className="block text-sm">
          Shipping notes
          <textarea
            className="mt-1 min-h-16 w-full rounded border border-blue-200 px-2 py-1.5"
            value={draft.shipping_notes}
            onChange={(e) => updateField("shipping_notes", e.target.value)}
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block text-sm">
            Suggested price
            <input
              type="number"
              step="0.01"
              className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
              value={draft.suggested_price ?? ""}
              onChange={(e) => updateField("suggested_price", e.target.value ? Number(e.target.value) : null)}
            />
          </label>
          <label className="block text-sm">
            Minimum price
            <input
              type="number"
              step="0.01"
              className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
              value={draft.minimum_price ?? ""}
              onChange={(e) => updateField("minimum_price", e.target.value ? Number(e.target.value) : null)}
            />
          </label>
          <label className="block text-sm">
            Premium price
            <input
              type="number"
              step="0.01"
              className="mt-1 w-full rounded border border-blue-200 px-2 py-1.5"
              value={draft.premium_price ?? ""}
              onChange={(e) => updateField("premium_price", e.target.value ? Number(e.target.value) : null)}
            />
          </label>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-red-800" onClick={() => void save()} disabled={saving}>
          Save changes
        </button>
        <button type="button" className="rounded-md border border-white/40 px-3 py-1.5 text-sm text-white" onClick={() => void copyText(draft.title).then(() => setMessage("Title copied."))}>
          Copy Title
        </button>
        <button type="button" className="rounded-md border border-white/40 px-3 py-1.5 text-sm text-white" onClick={() => void copyText(draft.description).then(() => setMessage("Description copied."))}>
          Copy Description
        </button>
        <button type="button" className="rounded-md border border-white/40 px-3 py-1.5 text-sm text-white" onClick={() => void copyText(draft.full_listing_text).then(() => setMessage("Full listing copied."))}>
          Copy Full Listing
        </button>
        <button type="button" className="rounded-md border border-emerald-300 px-3 py-1.5 text-sm text-emerald-100" onClick={() => void markReviewed()}>
          Mark Reviewed
        </button>
        <button type="button" className="rounded-md border border-slate-400 px-3 py-1.5 text-sm text-slate-200" onClick={() => void archiveDraft()}>
          Archive
        </button>
      </div>
    </PatriotPageLayout>
  );
}
