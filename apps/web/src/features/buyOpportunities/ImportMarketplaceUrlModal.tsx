import { useState } from "react";

import { ApiError, apiClient } from "../../api/client";

type Props = {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  opportunityId?: number;
};

export function ImportMarketplaceUrlModal({ open, onClose, onSuccess, opportunityId }: Props): JSX.Element | null {
  const [url, setUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!open) {
    return null;
  }

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.importBuyOpportunityUrl({
        url: url.trim(),
        notes: notes.trim(),
        opportunity_id: opportunityId,
      });
      setUrl("");
      setNotes("");
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not import marketplace URL.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div
        className="w-full max-w-lg rounded-lg bg-white p-5 text-blue-950 shadow-xl"
        role="dialog"
        aria-labelledby="import-marketplace-url-title"
      >
        <h2 id="import-marketplace-url-title" className="text-lg font-semibold">
          Import Marketplace URL
        </h2>
        <p className="mt-1 text-sm text-blue-800">
          Paste a supported marketplace listing link. ComicOS will store the source for future buy workflows.
        </p>
        <form className="mt-4 space-y-3" onSubmit={(e) => void handleSubmit(e)}>
          <label className="block text-sm">
            <span className="font-medium">Marketplace URL</span>
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="mt-1 w-full rounded border border-blue-300 px-3 py-2 text-sm"
              placeholder="https://www.ebay.com/itm/..."
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium">Notes</span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="mt-1 w-full rounded border border-blue-300 px-3 py-2 text-sm"
              rows={2}
              placeholder="Optional"
            />
          </label>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              className="rounded border border-blue-300 px-3 py-1.5 text-sm"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-60"
              disabled={submitting}
            >
              {submitting ? "Importing…" : "Import"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
