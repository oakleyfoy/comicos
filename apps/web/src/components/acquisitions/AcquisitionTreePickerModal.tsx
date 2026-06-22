import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type CatalogUniverseIssueNode,
  type CatalogUniversePublisherNode,
  type CatalogUniverseVolumeNode,
  type PlaceholderRangePreviewResponse,
  type VariantOption,
} from "../../api/client";

const VARIANT_PRESETS = [
  { label: "None", value: "" },
  { label: "Unknown Variant", value: "Unknown Variant" },
  { label: "Cover A", value: "Cover A", cover_type: "Cover A" },
  { label: "Cover B", value: "Cover B", cover_type: "Cover B" },
  { label: "Newsstand", value: "Newsstand", cover_type: "Newsstand" },
  { label: "Direct", value: "Direct", cover_type: "Direct" },
  { label: "Foil", value: "Foil", cover_type: "Foil" },
  { label: "Ratio Variant", value: "Ratio Variant", ratio_variant: "1:25" },
  { label: "Other / Notes", value: "Other" },
] as const;

type Props = {
  acquisitionId: number;
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  /** When true, renders inline on the page instead of a fullscreen modal. */
  embedded?: boolean;
};

type Mode = "single" | "bulk";

function flowErrorMessage(err: unknown, fallback: string): string | null {
  if (err instanceof ApiError && err.status === 401) return null;
  return err instanceof ApiError ? err.message : fallback;
}

export function AcquisitionTreePickerModal({
  acquisitionId,
  open,
  onClose,
  onCreated,
  embedded = false,
}: Props): JSX.Element | null {
  const [mode, setMode] = useState<Mode>("single");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [publisherSearch, setPublisherSearch] = useState("");
  const [publishers, setPublishers] = useState<CatalogUniversePublisherNode[]>([]);
  const [selectedPublisher, setSelectedPublisher] = useState<string | null>(null);

  const [volumeSearch, setVolumeSearch] = useState("");
  const [volumes, setVolumes] = useState<CatalogUniverseVolumeNode[]>([]);
  const [selectedVolume, setSelectedVolume] = useState<CatalogUniverseVolumeNode | null>(null);

  const [issueFilter, setIssueFilter] = useState("");
  const [issues, setIssues] = useState<CatalogUniverseIssueNode[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<CatalogUniverseIssueNode | null>(null);
  const [variantOptions, setVariantOptions] = useState<VariantOption[]>([]);
  const [selectedVariant, setSelectedVariant] = useState<VariantOption | null>(null);
  const [quantity, setQuantity] = useState("1");

  const [bulkStart, setBulkStart] = useState("186");
  const [bulkEnd, setBulkEnd] = useState("300");
  const [bulkExclude, setBulkExclude] = useState("221,244");
  const [bulkQty, setBulkQty] = useState("1");
  const [bulkNotes, setBulkNotes] = useState("");
  const [variantPreset, setVariantPreset] = useState("");
  const [variantNotes, setVariantNotes] = useState("");
  const [preview, setPreview] = useState<PlaceholderRangePreviewResponse | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setPreview(null);
    setSelectedIssue(null);
    setVariantOptions([]);
    setSelectedVariant(null);
  }, [open]);

  const selectIssue = useCallback(
    async (row: CatalogUniverseIssueNode) => {
      setSelectedIssue(row);
      setSelectedVariant(null);
      setVariantOptions([]);
      if (!row.has_variants || !selectedVolume) {
        return;
      }
      setBusy(true);
      setError(null);
      try {
        const resp = await apiClient.listCatalogUniverseIssueVariants(
          selectedVolume.volume_id,
          row.issue_number,
          acquisitionId,
        );
        setVariantOptions(resp.options);
      } catch (err) {
        const message = flowErrorMessage(err, "Could not load covers for this issue.");
        if (message) setError(message);
      } finally {
        setBusy(false);
      }
    },
    [acquisitionId, selectedVolume],
  );

  const loadPublishers = useCallback(async () => {
    if (!open) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogUniversePublishers(publisherSearch || undefined);
      setPublishers(resp.items);
    } catch (err) {
      const message = flowErrorMessage(err, "Could not load publishers.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, [open, publisherSearch]);

  const loadVolumes = useCallback(async () => {
    if (!open || !selectedPublisher) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogUniverseVolumes(
        selectedPublisher,
        volumeSearch || undefined,
      );
      setVolumes(resp.items);
    } catch (err) {
      const message = flowErrorMessage(err, "Could not load volumes.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, [open, selectedPublisher, volumeSearch]);

  const loadIssues = useCallback(async () => {
    if (!open || !selectedVolume) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogUniverseIssues(
        selectedVolume.volume_id,
        issueFilter || undefined,
      );
      setIssues(resp.items);
    } catch (err) {
      const message = flowErrorMessage(err, "Could not load issues.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, [issueFilter, open, selectedVolume]);

  useEffect(() => {
    const t = window.setTimeout(() => void loadPublishers(), 250);
    return () => window.clearTimeout(t);
  }, [loadPublishers]);

  useEffect(() => {
    const t = window.setTimeout(() => void loadVolumes(), 250);
    return () => window.clearTimeout(t);
  }, [loadVolumes]);

  useEffect(() => {
    const t = window.setTimeout(() => void loadIssues(), 250);
    return () => window.clearTimeout(t);
  }, [loadIssues]);

  const createSingle = async () => {
    if (!selectedPublisher || !selectedVolume || !selectedIssue) return;
    const qty = Math.min(100, Math.max(1, Number(quantity) || 1));
    const catalogIssueId =
      selectedVariant?.catalog_issue_id ??
      (!selectedIssue.has_variants ? selectedIssue.catalog_issue_id : null);
    setBusy(true);
    setError(null);
    try {
      if (catalogIssueId != null) {
        await apiClient.addAcquisitionItems(acquisitionId, [{ catalog_issue_id: catalogIssueId, quantity: qty }]);
      } else {
        const issueTitle = selectedVariant?.variant_label ?? selectedVariant?.title ?? selectedIssue.issue_title;
        await apiClient.createTreePlaceholderIssue(acquisitionId, {
          publisher: selectedPublisher,
          volume_id: selectedVolume.volume_id,
          issue_number: selectedIssue.issue_number,
          quantity: qty,
          issue_title: issueTitle,
          source_issue_id:
            selectedIssue.comicvine_issue_id != null
              ? String(selectedIssue.comicvine_issue_id)
              : catalogIssueId != null
                ? String(catalogIssueId)
                : null,
        });
      }
      onCreated();
      if (!embedded) {
        onClose();
      }
    } catch (err) {
      const message = flowErrorMessage(err, "Could not add book.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  };

  const createUnknown = async () => {
    if (!selectedPublisher || !selectedVolume) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.createTreeUnknownPlaceholder(acquisitionId, {
        publisher: selectedPublisher,
        volume_id: selectedVolume.volume_id,
        quantity: Math.min(100, Math.max(1, Number(quantity) || 1)),
      });
      onCreated();
      if (!embedded) {
        onClose();
      }
    } catch (err) {
      const message = flowErrorMessage(err, "Could not create unknown issue placeholder.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  };

  const buildRangePayload = () => {
    const preset = VARIANT_PRESETS.find((row) => row.value === variantPreset);
    const exclude = bulkExclude
      .split(/[,;\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    return {
      publisher: selectedPublisher!,
      volume_id: selectedVolume!.volume_id,
      start_issue: Number(bulkStart),
      end_issue: Number(bulkEnd),
      exclude_issues: exclude,
      quantity_per_issue: Math.min(100, Math.max(1, Number(bulkQty) || 1)),
      notes: bulkNotes || null,
      prefer_catalog: true,
      variant_label: variantPreset || null,
      cover_type: preset && "cover_type" in preset ? preset.cover_type : null,
      ratio_variant: preset && "ratio_variant" in preset ? preset.ratio_variant : null,
      raw_variant_notes: variantNotes || null,
    };
  };

  const runPreview = async () => {
    if (!selectedPublisher || !selectedVolume) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.previewPlaceholderRange(acquisitionId, buildRangePayload());
      setPreview(resp);
    } catch (err) {
      const message = flowErrorMessage(err, "Could not preview range.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  };

  const createRange = async () => {
    if (!selectedPublisher || !selectedVolume || !preview) return;
    const toCreate = preview.catalog_items_to_add + preview.placeholders_to_create;
    const skipped = preview.skipped_duplicates;
    const ok = window.confirm(`Create ${toCreate} items, skip ${skipped} duplicates?`);
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.createPlaceholderRange(acquisitionId, buildRangePayload());
      onCreated();
      if (!embedded) {
        onClose();
      }
    } catch (err) {
      const message = flowErrorMessage(err, "Could not create range items.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  };

  if (!embedded && !open) return null;

  const panel = (
    <div
      role={embedded ? undefined : "dialog"}
      aria-label="Universe tree picker"
      className={
        embedded
          ? "flex w-full flex-col rounded-2xl border border-white/10 bg-slate-900/70 shadow-xl"
          : "flex max-h-[90vh] w-full max-w-6xl flex-col rounded-2xl border border-slate-700 bg-slate-950 shadow-xl"
      }
    >
        <header
          className={`flex items-center justify-between border-b px-4 py-3 ${embedded ? "border-white/10" : "border-slate-800"}`}
        >
          <div>
            <h2 className="text-lg font-semibold text-white">Catalog universe tree</h2>
            <p className="text-xs text-slate-400">
              Publisher → volume → issue # → cover variant (local catalog)
            </p>
          </div>
          {!embedded ? (
            <button type="button" onClick={onClose} className="text-sm text-slate-400 hover:text-white">
              Close
            </button>
          ) : null}
        </header>

        <div className="flex gap-2 border-b border-slate-800 px-4 py-2">
          <button
            type="button"
            onClick={() => setMode("single")}
            className={`rounded-lg px-3 py-1.5 text-sm ${mode === "single" ? "bg-sky-600 text-white" : "text-slate-300"}`}
          >
            Single issue
          </button>
          <button
            type="button"
            onClick={() => setMode("bulk")}
            className={`rounded-lg px-3 py-1.5 text-sm ${mode === "bulk" ? "bg-sky-600 text-white" : "text-slate-300"}`}
          >
            Bulk range
          </button>
        </div>

        {error ? (
          <p role="alert" className="mx-4 mt-3 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
            {error}
          </p>
        ) : null}

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden p-4 lg:grid-cols-3 xl:grid-cols-4">
          <section className="flex min-h-[280px] flex-col rounded-xl border border-slate-800">
            <div className="border-b border-slate-800 p-2">
              <input
                aria-label="Search publishers"
                value={publisherSearch}
                onChange={(e) => setPublisherSearch(e.target.value)}
                placeholder="Search publishers"
                className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
              />
            </div>
            <ul className="flex-1 overflow-y-auto p-2">
              {publishers.map((row) => (
                <li key={row.publisher}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedPublisher(row.publisher);
                      setSelectedVolume(null);
                      setSelectedIssue(null);
                      setVariantOptions([]);
                      setSelectedVariant(null);
                      setPreview(null);
                    }}
                    className={`mb-1 w-full rounded-lg px-2 py-2 text-left text-sm ${
                      selectedPublisher === row.publisher ? "bg-sky-900/50 text-white" : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {row.publisher}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="flex min-h-[280px] flex-col rounded-xl border border-slate-800">
            <div className="border-b border-slate-800 p-2">
              <input
                aria-label="Search series"
                value={volumeSearch}
                onChange={(e) => setVolumeSearch(e.target.value)}
                disabled={!selectedPublisher}
                placeholder="Search series / volumes"
                className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white disabled:opacity-50"
              />
            </div>
            <ul className="flex-1 overflow-y-auto p-2">
              {volumes.map((row) => (
                <li key={row.volume_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedVolume(row);
                      setSelectedIssue(null);
                      setVariantOptions([]);
                      setSelectedVariant(null);
                      setPreview(null);
                    }}
                    className={`mb-1 w-full rounded-lg px-2 py-2 text-left text-sm ${
                      selectedVolume?.volume_id === row.volume_id
                        ? "bg-sky-900/50 text-white"
                        : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {row.start_year ? `${row.title} (${row.start_year})` : row.title}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="flex min-h-[280px] flex-col rounded-xl border border-slate-800">
            {mode === "single" ? (
              <>
                <div className="border-b border-slate-800 p-2">
                  <input
                    aria-label="Filter issue number"
                    value={issueFilter}
                    onChange={(e) => setIssueFilter(e.target.value)}
                    disabled={!selectedVolume}
                    placeholder="Search issue #"
                    className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white disabled:opacity-50"
                  />
                </div>
                <ul className="flex-1 overflow-y-auto p-2">
                  {issues.map((row) => {
                    const selected =
                      selectedIssue?.normalized_issue_number === row.normalized_issue_number;
                    return (
                      <li key={row.normalized_issue_number}>
                        <button
                          type="button"
                          onClick={() => void selectIssue(row)}
                          className={`mb-1 flex w-full gap-2 rounded-lg px-2 py-2 text-left text-sm ${
                            selected ? "bg-sky-900/50 text-white" : "text-slate-200 hover:bg-slate-800"
                          }`}
                        >
                          {!row.has_variants && row.cover_image_url ? (
                            <img
                              src={row.cover_image_url}
                              alt=""
                              className="h-14 w-10 shrink-0 rounded object-cover"
                            />
                          ) : null}
                          <span className="min-w-0 flex-1">
                            <span className="font-medium">#{row.issue_number}</span>
                            {row.issue_title ? ` — ${row.issue_title}` : ""}
                            {row.has_variants ? (
                              <span className="mt-0.5 block text-xs text-indigo-300">
                                {row.cover_count} cover{row.cover_count === 1 ? "" : "s"}
                              </span>
                            ) : null}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </>
            ) : (
              <div className="space-y-3 overflow-y-auto p-3">
                <label className="block text-xs text-slate-400">
                  From issue #
                  <input
                    value={bulkStart}
                    onChange={(e) => {
                      setBulkStart(e.target.value);
                      setPreview(null);
                    }}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                  />
                </label>
                <label className="block text-xs text-slate-400">
                  To issue #
                  <input
                    value={bulkEnd}
                    onChange={(e) => {
                      setBulkEnd(e.target.value);
                      setPreview(null);
                    }}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                  />
                </label>
                <label className="block text-xs text-slate-400">
                  Exclude issues (comma-separated)
                  <input
                    aria-label="Exclude issues"
                    value={bulkExclude}
                    onChange={(e) => {
                      setBulkExclude(e.target.value);
                      setPreview(null);
                    }}
                    placeholder="221,244,266"
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                  />
                </label>
                <label className="block text-xs text-slate-400">
                  Quantity per issue
                  <input
                    aria-label="Quantity per issue"
                    value={bulkQty}
                    onChange={(e) => setBulkQty(e.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                  />
                </label>
                <label className="block text-xs text-slate-400">
                  Notes
                  <input
                    value={bulkNotes}
                    onChange={(e) => setBulkNotes(e.target.value)}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                  />
                </label>
                <label className="block text-xs text-slate-400">
                  Variant / cover (optional)
                  <select
                    aria-label="Variant preset"
                    value={variantPreset}
                    onChange={(e) => {
                      setVariantPreset(e.target.value);
                      setPreview(null);
                    }}
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                  >
                    {VARIANT_PRESETS.map((row) => (
                      <option key={row.label} value={row.value}>
                        {row.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs text-slate-400">
                  Variant notes
                  <input
                    aria-label="Variant notes"
                    value={variantNotes}
                    onChange={(e) => setVariantNotes(e.target.value)}
                    placeholder='e.g. "Silver foil cover"'
                    className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                  />
                </label>
                <button
                  type="button"
                  disabled={!selectedVolume || busy}
                  onClick={() => void runPreview()}
                  className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:border-sky-400 disabled:opacity-50"
                >
                  Preview range
                </button>
                {preview ? (
                  <div className="rounded-lg bg-slate-900/80 p-3 text-sm text-slate-200">
                    <p>
                      Total in range: <strong>{preview.total_issues_in_range}</strong>
                    </p>
                    <p>
                      Excluded: <strong>{preview.excluded_count}</strong>
                    </p>
                    <p>
                      Already in acquisition: <strong>{preview.already_in_acquisition}</strong>
                    </p>
                    <p>
                      Catalog matches to add: <strong>{preview.catalog_items_to_add}</strong>
                    </p>
                    <p>
                      Placeholders to create: <strong>{preview.placeholders_to_create}</strong>
                    </p>
                    <p>
                      Skipped duplicates: <strong>{preview.skipped_duplicates}</strong>
                    </p>
                  </div>
                ) : null}
              </div>
            )}
          </section>

          {mode === "single" && selectedIssue?.has_variants ? (
            <section className="flex min-h-[280px] flex-col rounded-xl border border-slate-800 xl:col-span-1">
              <div className="border-b border-slate-800 px-3 py-2">
                <p className="text-sm font-semibold text-white">Covers for #{selectedIssue.issue_number}</p>
                <p className="text-xs text-slate-400">Pick a variant</p>
              </div>
              <ul className="grid flex-1 grid-cols-2 gap-2 overflow-y-auto p-2 sm:grid-cols-3">
                {variantOptions.map((option, index) => {
                  const picked =
                    selectedVariant?.catalog_issue_id === option.catalog_issue_id &&
                    selectedVariant?.variant_label === option.variant_label &&
                    selectedVariant?.cover_image_url === option.cover_image_url;
                  return (
                    <li key={`${option.catalog_issue_id}-${option.variant_label ?? "main"}-${index}`}>
                      <button
                        type="button"
                        onClick={() => setSelectedVariant(option)}
                        className={`relative flex aspect-[2/3] w-full flex-col overflow-hidden rounded-lg border text-left ${
                          picked ? "border-sky-400 ring-2 ring-sky-400" : "border-slate-700 hover:border-sky-500"
                        }`}
                      >
                        {option.cover_image_url ? (
                          <img
                            src={option.cover_image_url}
                            alt=""
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <span className="flex h-full items-center justify-center bg-slate-800 px-1 text-center text-xs text-slate-300">
                            {option.variant_label ?? "Cover"}
                          </span>
                        )}
                        <span className="absolute bottom-0 left-0 right-0 bg-slate-950/80 px-1 py-0.5 text-[10px] text-white">
                          {option.variant_label ?? option.title ?? "Cover"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              {variantOptions.length === 0 && !busy ? (
                <p className="p-3 text-sm text-slate-400">No cover art in catalog for this issue yet.</p>
              ) : null}
            </section>
          ) : null}
        </div>

        <footer className="flex flex-wrap items-center gap-3 border-t border-slate-800 px-4 py-3">
          {mode === "single" ? (
            <>
              <label className="text-sm text-slate-300">
                Qty
                <input
                  aria-label="Quantity"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="ml-2 w-16 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-white"
                />
              </label>
              <button
                type="button"
                disabled={
                  busy ||
                  !selectedIssue ||
                  (selectedIssue.has_variants ? selectedVariant == null : false)
                }
                onClick={() => void createSingle()}
                className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-400 disabled:opacity-50"
              >
                Add to collection
              </button>
              <button
                type="button"
                disabled={busy || !selectedVolume}
                onClick={() => void createUnknown()}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:border-sky-400 disabled:opacity-50"
              >
                Unknown Issue
              </button>
            </>
          ) : (
            <button
              type="button"
              disabled={
                busy ||
                !selectedVolume ||
                !preview ||
                preview.catalog_items_to_add + preview.placeholders_to_create === 0
              }
              onClick={() => void createRange()}
              className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-400 disabled:opacity-50"
            >
              Create {preview ? preview.catalog_items_to_add + preview.placeholders_to_create : 0} items
            </button>
          )}
          {busy ? <span className="text-xs text-slate-500">Working…</span> : null}
        </footer>
    </div>
  );

  if (embedded) {
    return panel;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">{panel}</div>
  );
}
