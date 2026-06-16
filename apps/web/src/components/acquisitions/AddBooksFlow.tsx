import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type IssueGridResponse,
  type IssueGridTile,
  type PublisherCard,
  type SeriesCard,
  type SeriesListResponse,
  type VariantOption,
} from "../../api/client";
import { AcquisitionTreePickerModal } from "./AcquisitionTreePickerModal";

type FlowStep = "hub" | "publisher" | "series" | "grid" | "variant" | "bulk" | "placeholder";

type Props = {
  acquisitionId: number;
  onBooksAdded: () => void;
  onClose: () => void;
};

function flowErrorMessage(err: unknown, fallback: string): string | null {
  if (err instanceof ApiError && err.status === 401) {
    return null;
  }
  return err instanceof ApiError ? err.message : fallback;
}

export function AddBooksFlow({ acquisitionId, onBooksAdded, onClose }: Props): JSX.Element {
  const [step, setStep] = useState<FlowStep>("hub");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [publishers, setPublishers] = useState<PublisherCard[]>([]);
  const [publisherSearch, setPublisherSearch] = useState("");
  const [selectedPublisher, setSelectedPublisher] = useState<PublisherCard | null>(null);

  const [series, setSeries] = useState<SeriesListResponse | null>(null);
  const [selectedSeries, setSelectedSeries] = useState<SeriesCard | null>(null);

  const [grid, setGrid] = useState<IssueGridResponse | null>(null);
  const [selectedIssueIds, setSelectedIssueIds] = useState<number[]>([]);

  const [variantNumber, setVariantNumber] = useState<string | null>(null);
  const [variantOptions, setVariantOptions] = useState<VariantOption[]>([]);

  const [bulkStart, setBulkStart] = useState("1");
  const [bulkEnd, setBulkEnd] = useState("25");
  const [bulkResolution, setBulkResolution] = useState<"cover_a" | "review" | "generic">("review");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const [phTitle, setPhTitle] = useState("");
  const [phIssue, setPhIssue] = useState("");
  const [phPublisher, setPhPublisher] = useState("");
  const [phQuantity, setPhQuantity] = useState("1");
  const [phNotes, setPhNotes] = useState("");
  const [phStatus, setPhStatus] = useState<string | null>(null);
  const [showTreePicker, setShowTreePicker] = useState(false);

  const openPlaceholder = useCallback(
    (prefill?: { title?: string; publisher?: string }) => {
      setError(null);
      setPhStatus(null);
      setPhTitle(prefill?.title ?? "");
      setPhIssue("");
      setPhPublisher(prefill?.publisher ?? "");
      setPhQuantity("1");
      setPhNotes("");
      setStep("placeholder");
    },
    [],
  );

  const submitPlaceholder = useCallback(async () => {
    const title = phTitle.trim();
    if (!title) {
      setError("Series / Title is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.addAcquisitionPlaceholderItem(acquisitionId, {
        title,
        issue_number: phIssue.trim(),
        publisher: phPublisher.trim() || null,
        quantity: Math.max(1, Number(phQuantity) || 1),
        notes: phNotes.trim() || null,
      });
      onBooksAdded();
      setPhStatus(`Added ${resp.created_count} placeholder book(s). Needs catalog match.`);
      setPhTitle("");
      setPhIssue("");
      setPhPublisher("");
      setPhQuantity("1");
      setPhNotes("");
    } catch (err) {
      const message = flowErrorMessage(err, "Could not add placeholder book.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, [acquisitionId, onBooksAdded, phIssue, phNotes, phPublisher, phQuantity, phTitle]);

  const loadPublishers = useCallback(async (search?: string) => {
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogPublishers(search);
      setPublishers(resp.publishers);
    } catch (err) {
      const message = flowErrorMessage(err, "Could not load publishers.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, []);

  const openPublishers = useCallback(() => {
    setStep("publisher");
    void loadPublishers();
  }, [loadPublishers]);

  const selectPublisher = useCallback(async (publisher: PublisherCard) => {
    setSelectedPublisher(publisher);
    setStep("series");
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.listCatalogSeries(publisher.id);
      setSeries(resp);
    } catch (err) {
      const message = flowErrorMessage(err, "Could not load series.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, []);

  const loadGrid = useCallback(
    async (seriesCard: SeriesCard) => {
      setBusy(true);
      setError(null);
      try {
        const resp = await apiClient.listCatalogIssueGrid(seriesCard.id, acquisitionId);
        setGrid(resp);
      } catch (err) {
        const message = flowErrorMessage(err, "Could not load issues.");
        if (message) setError(message);
      } finally {
        setBusy(false);
      }
    },
    [acquisitionId],
  );

  const selectSeries = useCallback(
    async (seriesCard: SeriesCard) => {
      setSelectedSeries(seriesCard);
      setSelectedIssueIds([]);
      setStep("grid");
      await loadGrid(seriesCard);
    },
    [loadGrid],
  );

  const toggleTile = useCallback(
    async (tile: IssueGridTile) => {
      if (tile.has_variants || tile.catalog_issue_id == null) {
        // open variant picker
        if (!selectedSeries) return;
        setBusy(true);
        setError(null);
        try {
          const resp = await apiClient.listCatalogIssueVariants(
            selectedSeries.id,
            tile.normalized_issue_number,
            acquisitionId,
          );
          setVariantNumber(resp.issue_number);
          setVariantOptions(resp.options);
          setStep("variant");
        } catch (err) {
          const message = flowErrorMessage(err, "Could not load variants.");
          if (message) setError(message);
        } finally {
          setBusy(false);
        }
        return;
      }
      const issueId = tile.catalog_issue_id;
      setSelectedIssueIds((prev) =>
        prev.includes(issueId) ? prev.filter((id) => id !== issueId) : [...prev, issueId],
      );
    },
    [acquisitionId, selectedSeries],
  );

  const commitIssues = useCallback(
    async (catalogIssueIds: number[], forceDuplicate = false) => {
      if (catalogIssueIds.length === 0) return;
      setBusy(true);
      setError(null);
      try {
        const resp = await apiClient.addAcquisitionItems(
          acquisitionId,
          catalogIssueIds.map((id) => ({ catalog_issue_id: id, quantity: 1 })),
          forceDuplicate,
        );
        if (resp.duplicate_catalog_issue_ids.length > 0 && !forceDuplicate) {
          const confirmAdd = window.confirm("Already added. Add another copy?");
          if (confirmAdd) {
            await commitIssues(resp.duplicate_catalog_issue_ids, true);
          }
        }
        setStatusMessage(`Added ${resp.created_count} book(s).`);
        onBooksAdded();
        if (selectedSeries) {
          await loadGrid(selectedSeries);
        }
      } catch (err) {
        const message = flowErrorMessage(err, "Could not add books.");
        if (message) setError(message);
      } finally {
        setBusy(false);
      }
    },
    [acquisitionId, loadGrid, onBooksAdded, selectedSeries],
  );

  const addSelected = useCallback(async () => {
    await commitIssues(selectedIssueIds);
    setSelectedIssueIds([]);
  }, [commitIssues, selectedIssueIds]);

  const addVariant = useCallback(
    async (option: VariantOption) => {
      await commitIssues([option.catalog_issue_id]);
      setStep("grid");
    },
    [commitIssues],
  );

  const addGenericForNumber = useCallback(async () => {
    if (!selectedSeries || !variantNumber) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.addAcquisitionGenericIssue(acquisitionId, {
        series_id: selectedSeries.id,
        issue_number: variantNumber,
        quantity: 1,
      });
      setStatusMessage(`Added ${resp.created_count} generic issue (needs review).`);
      onBooksAdded();
      setStep("grid");
      await loadGrid(selectedSeries);
    } catch (err) {
      const message = flowErrorMessage(err, "Could not add generic issue.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, [acquisitionId, loadGrid, onBooksAdded, selectedSeries, variantNumber]);

  const runBulkRange = useCallback(async () => {
    if (!selectedSeries) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await apiClient.addAcquisitionBulkRange(acquisitionId, {
        series_id: selectedSeries.id,
        start_issue: Number(bulkStart),
        end_issue: Number(bulkEnd),
        variant_resolution: bulkResolution,
      });
      const needsNote =
        resp.needs_variant.length > 0
          ? ` ${resp.needs_variant.length} issue(s) need variant selection.`
          : "";
      setStatusMessage(`Added ${resp.added_count} book(s).${needsNote}`);
      onBooksAdded();
    } catch (err) {
      const message = flowErrorMessage(err, "Could not run bulk range.");
      if (message) setError(message);
    } finally {
      setBusy(false);
    }
  }, [acquisitionId, bulkEnd, bulkResolution, bulkStart, onBooksAdded, selectedSeries]);

  useEffect(() => {
    setStatusMessage(null);
  }, [step]);

  return (
    <section
      aria-label="Add books"
      className="rounded-2xl border border-slate-700 bg-slate-900/80 p-4 text-slate-100"
    >
      <header className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-white">Add Books</h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:border-slate-400"
        >
          Done
        </button>
      </header>

      {error ? (
        <p role="alert" className="mb-3 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}
      {statusMessage ? (
        <p className="mb-3 rounded-lg bg-emerald-500/15 px-3 py-2 text-sm text-emerald-200">{statusMessage}</p>
      ) : null}

      {step === "hub" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={openPublishers}
            className="rounded-xl border border-slate-600 bg-slate-800 p-4 text-left hover:border-sky-400"
          >
            <span className="block text-base font-semibold text-white">Browse Publisher</span>
            <span className="text-sm text-slate-400">Tap publisher → series → issue grid</span>
          </button>
          <button
            type="button"
            onClick={() => {
              openPublishers();
            }}
            className="rounded-xl border border-slate-600 bg-slate-800 p-4 text-left hover:border-sky-400"
          >
            <span className="block text-base font-semibold text-white">Bulk Entry</span>
            <span className="text-sm text-slate-400">Add an issue-number range for a series</span>
          </button>
          <button
            type="button"
            onClick={() => setShowTreePicker(true)}
            className="rounded-xl border border-slate-600 bg-slate-800 p-4 text-left hover:border-emerald-400"
          >
            <span className="block text-base font-semibold text-white">Universe Tree Picker</span>
            <span className="text-sm text-slate-400">Publisher → volume → issue placeholders</span>
          </button>
          <button
            type="button"
            onClick={() => openPlaceholder()}
            className="rounded-xl border border-slate-600 bg-slate-800 p-4 text-left hover:border-amber-400"
          >
            <span className="block text-base font-semibold text-white">Book Not in Catalog</span>
            <span className="text-sm text-slate-400">Create a placeholder issue to add now</span>
          </button>
          <div className="rounded-xl border border-dashed border-slate-700 bg-slate-800/40 p-4 text-slate-500">
            <span className="block text-base font-semibold">Photo Intake</span>
            <span className="text-sm">Coming soon</span>
          </div>
          <div className="rounded-xl border border-dashed border-slate-700 bg-slate-800/40 p-4 text-slate-500">
            <span className="block text-base font-semibold">Barcode Scan</span>
            <span className="text-sm">Coming soon</span>
          </div>
        </div>
      ) : null}

      {step === "publisher" ? (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <input
              aria-label="Search publisher"
              value={publisherSearch}
              onChange={(e) => setPublisherSearch(e.target.value)}
              placeholder="Search publisher (optional)"
              className="flex-1 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            />
            <button
              type="button"
              onClick={() => loadPublishers(publisherSearch)}
              className="rounded-lg bg-sky-600 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-500"
            >
              Search
            </button>
          </div>
          {busy ? <p className="text-sm text-slate-400">Loading…</p> : null}
          {!busy && publishers.length === 0 ? (
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-sm text-slate-300">
              <p>No catalog match found.</p>
              <button
                type="button"
                onClick={() => openPlaceholder({ publisher: publisherSearch.trim() || undefined })}
                className="mt-2 rounded-lg bg-amber-600 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-500"
              >
                Create Placeholder Issue
              </button>
            </div>
          ) : null}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {publishers.map((publisher) => (
              <button
                key={publisher.id}
                type="button"
                onClick={() => selectPublisher(publisher)}
                className="rounded-xl border border-slate-600 bg-slate-800 p-3 text-left hover:border-sky-400"
              >
                <span className="block font-semibold text-white">{publisher.name}</span>
                <span className="text-xs text-slate-400">
                  {publisher.series_count} series{publisher.owned ? " · Owned" : ""}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {step === "series" ? (
        <div>
          <button
            type="button"
            onClick={() => setStep("publisher")}
            className="mb-3 text-sm text-sky-300 hover:underline"
          >
            ← Publishers
          </button>
          {busy ? <p className="text-sm text-slate-400">Loading…</p> : null}
          {series ? <SeriesSections series={series} onSelect={selectSeries} /> : null}
        </div>
      ) : null}

      {step === "grid" && grid ? (
        <div>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <button type="button" onClick={() => setStep("series")} className="text-sm text-sky-300 hover:underline">
              ← Series
            </button>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setStep("bulk")}
                className="rounded-lg border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:border-slate-400"
              >
                Bulk Range
              </button>
              <button
                type="button"
                onClick={() =>
                  openPlaceholder({
                    title: selectedSeries?.name,
                    publisher: selectedPublisher?.name,
                  })
                }
                className="rounded-lg border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:border-amber-400"
              >
                Not in Catalog
              </button>
              {selectedIssueIds.length > 0 ? (
                <>
                  <button
                    type="button"
                    onClick={() => setSelectedIssueIds([])}
                    className="rounded-lg border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:border-slate-400"
                  >
                    Clear ({selectedIssueIds.length})
                  </button>
                  <button
                    type="button"
                    onClick={addSelected}
                    disabled={busy}
                    className="rounded-lg bg-emerald-600 px-3 py-1 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    Add Selected ({selectedIssueIds.length})
                  </button>
                </>
              ) : null}
            </div>
          </div>
          <p className="mb-2 text-sm font-semibold text-white">{grid.series_name}</p>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-8">
            {grid.tiles.map((tile) => {
              const selected = tile.catalog_issue_id != null && selectedIssueIds.includes(tile.catalog_issue_id);
              return (
                <button
                  key={tile.normalized_issue_number}
                  type="button"
                  aria-label={`Issue ${tile.issue_number}`}
                  aria-pressed={selected}
                  onClick={() => toggleTile(tile)}
                  className={`relative flex aspect-[2/3] flex-col items-center justify-between overflow-hidden rounded-lg border p-1 text-center text-xs transition ${
                    selected ? "border-emerald-400 ring-2 ring-emerald-400" : "border-slate-600 hover:border-sky-400"
                  }`}
                >
                  {tile.cover_image_url ? (
                    <img
                      src={tile.cover_image_url}
                      alt={`Issue ${tile.issue_number} cover`}
                      className="h-full w-full rounded object-cover"
                    />
                  ) : (
                    <span className="flex h-full w-full items-center justify-center bg-slate-800 text-slate-300">
                      #{tile.issue_number}
                    </span>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-slate-950/70 px-1 text-[10px] font-semibold text-white">
                    #{tile.issue_number}
                  </span>
                  {tile.has_variants ? (
                    <span className="absolute bottom-1 left-1 rounded bg-indigo-600/90 px-1 text-[10px] text-white">
                      {tile.cover_count} covers
                    </span>
                  ) : null}
                  {tile.owned ? (
                    <span className="absolute right-1 top-1 rounded bg-amber-500/90 px-1 text-[10px] text-white">
                      Owned
                    </span>
                  ) : null}
                  {tile.added ? (
                    <span className="absolute bottom-1 right-1 rounded bg-emerald-600/90 px-1 text-[10px] text-white">
                      Added
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {step === "variant" ? (
        <div>
          <button type="button" onClick={() => setStep("grid")} className="mb-3 text-sm text-sky-300 hover:underline">
            ← Issue grid
          </button>
          <p className="mb-3 text-sm font-semibold text-white">Choose a cover for #{variantNumber}</p>
          <div className="mb-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => variantOptions[0] && addVariant(variantOptions[0])}
              disabled={busy || variantOptions.length === 0}
              className="rounded-lg bg-sky-600 px-3 py-1 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
            >
              Use Cover A
            </button>
            <button
              type="button"
              onClick={addGenericForNumber}
              disabled={busy}
              className="rounded-lg border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:border-slate-400"
            >
              Not Sure / Add Generic Issue
            </button>
            <button
              type="button"
              onClick={() => setStep("grid")}
              className="rounded-lg border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:border-slate-400"
            >
              Cancel
            </button>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {variantOptions.map((option) => (
              <button
                key={option.catalog_issue_id}
                type="button"
                onClick={() => addVariant(option)}
                className="flex gap-3 rounded-xl border border-slate-600 bg-slate-800 p-2 text-left hover:border-sky-400"
              >
                {option.cover_image_url ? (
                  <img src={option.cover_image_url} alt="" className="h-20 w-14 rounded object-cover" />
                ) : (
                  <span className="flex h-20 w-14 items-center justify-center rounded bg-slate-700 text-xs text-slate-300">
                    #{option.issue_number}
                  </span>
                )}
                <span className="text-sm">
                  <span className="block font-semibold text-white">{option.variant_label || `Issue #${option.issue_number}`}</span>
                  <span className="text-xs text-slate-400">{option.publisher}</span>
                  {option.added ? <span className="ml-1 text-[10px] text-emerald-300">Added</span> : null}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {step === "bulk" ? (
        <div>
          <button type="button" onClick={() => setStep("grid")} className="mb-3 text-sm text-sky-300 hover:underline">
            ← Issue grid
          </button>
          <p className="mb-3 text-sm font-semibold text-white">
            Bulk range for {selectedSeries?.name}
          </p>
          <div className="mb-3 flex flex-wrap items-end gap-3">
            <label className="text-sm text-slate-300">
              Start Issue
              <input
                aria-label="Start issue"
                value={bulkStart}
                onChange={(e) => setBulkStart(e.target.value)}
                inputMode="numeric"
                className="mt-1 block w-24 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white"
              />
            </label>
            <label className="text-sm text-slate-300">
              End Issue
              <input
                aria-label="End issue"
                value={bulkEnd}
                onChange={(e) => setBulkEnd(e.target.value)}
                inputMode="numeric"
                className="mt-1 block w-24 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white"
              />
            </label>
            <label className="text-sm text-slate-300">
              Variant handling
              <select
                aria-label="Variant handling"
                value={bulkResolution}
                onChange={(e) => setBulkResolution(e.target.value as "cover_a" | "review" | "generic")}
                className="mt-1 block rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white"
              >
                <option value="review">Review variants one by one</option>
                <option value="cover_a">Use Cover A for all</option>
                <option value="generic">Add generic where unsure</option>
              </select>
            </label>
            <button
              type="button"
              onClick={runBulkRange}
              disabled={busy}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              Add Range
            </button>
          </div>
        </div>
      ) : null}

      {step === "placeholder" ? (
        <div>
          <button type="button" onClick={() => setStep("hub")} className="mb-3 text-sm text-sky-300 hover:underline">
            ← Add books options
          </button>
          <p className="mb-1 text-sm font-semibold text-white">Create Placeholder Issue</p>
          <p className="mb-3 text-xs text-slate-400">
            Add a book that isn’t in the catalog yet. You can match it to a catalog issue later.
          </p>
          <button
            type="button"
            onClick={() => setShowTreePicker(true)}
            className="mb-3 rounded-lg border border-emerald-700 px-3 py-2 text-sm text-emerald-200 hover:border-emerald-400"
          >
            Pick from Universe Tree
          </button>
          {phStatus ? (
            <p className="mb-3 rounded-lg bg-emerald-500/15 px-3 py-2 text-sm text-emerald-200">{phStatus}</p>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm text-slate-300 sm:col-span-2">
              Series / Title
              <input
                aria-label="Series or title"
                value={phTitle}
                onChange={(e) => setPhTitle(e.target.value)}
                placeholder="Uncanny X-Men"
                className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="text-sm text-slate-300">
              Issue #
              <input
                aria-label="Issue number"
                value={phIssue}
                onChange={(e) => setPhIssue(e.target.value)}
                placeholder="221"
                className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="text-sm text-slate-300">
              Publisher
              <input
                aria-label="Publisher"
                value={phPublisher}
                onChange={(e) => setPhPublisher(e.target.value)}
                placeholder="Marvel"
                className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="text-sm text-slate-300">
              Quantity
              <input
                aria-label="Quantity"
                value={phQuantity}
                onChange={(e) => setPhQuantity(e.target.value)}
                inputMode="numeric"
                className="mt-1 block w-24 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </label>
            <label className="text-sm text-slate-300 sm:col-span-2">
              Notes
              <textarea
                aria-label="Notes"
                value={phNotes}
                onChange={(e) => setPhNotes(e.target.value)}
                rows={2}
                className="mt-1 block w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={submitPlaceholder}
            disabled={busy}
            className="mt-3 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-500 disabled:opacity-50"
          >
            Add Placeholder Book
          </button>
        </div>
      ) : null}

      <AcquisitionTreePickerModal
        acquisitionId={acquisitionId}
        open={showTreePicker}
        onClose={() => setShowTreePicker(false)}
        onCreated={() => {
          onBooksAdded();
          setStatusMessage("Placeholder(s) added from universe tree.");
        }}
      />
    </section>
  );
}

function SeriesSections({
  series,
  onSelect,
}: {
  series: SeriesListResponse;
  onSelect: (s: SeriesCard) => void;
}): JSX.Element {
  const sections: { title: string; items: SeriesCard[] }[] = [
    { title: "Popular Series", items: series.popular },
    { title: "Your Series", items: series.user_owned },
    { title: "All Series", items: series.alphabetical },
  ];
  return (
    <div className="space-y-4">
      {sections
        .filter((section) => section.items.length > 0)
        .map((section) => (
          <div key={section.title}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{section.title}</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {section.items.map((card) => (
                <button
                  key={`${section.title}-${card.id}`}
                  type="button"
                  onClick={() => onSelect(card)}
                  className="flex gap-3 rounded-xl border border-slate-600 bg-slate-800 p-2 text-left hover:border-sky-400"
                >
                  {card.sample_cover_url ? (
                    <img src={card.sample_cover_url} alt="" className="h-16 w-11 rounded object-cover" />
                  ) : (
                    <span className="flex h-16 w-11 items-center justify-center rounded bg-slate-700 text-[10px] text-slate-300">
                      No cover
                    </span>
                  )}
                  <span className="text-sm">
                    <span className="block font-semibold text-white">{card.name}</span>
                    <span className="text-xs text-slate-400">
                      {card.start_year ? `${card.start_year} · ` : ""}
                      {card.issue_count} issues{card.owned ? " · Owned" : ""}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}
