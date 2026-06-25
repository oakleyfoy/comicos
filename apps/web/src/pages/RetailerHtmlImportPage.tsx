import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, apiClient, type SupportedRetailer } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const ACCEPTED_EXTENSIONS = [".html", ".htm", ".txt"];

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function statusLabel(retailer: SupportedRetailer): string {
  if (retailer.is_fallback) {
    return "Other retailer";
  }
  if (retailer.status === "supported") {
    return "Full parser";
  }
  if (retailer.status === "beta") {
    return "HTML import (beta parser)";
  }
  return "HTML import";
}

function retailerImportHint(retailer: SupportedRetailer | undefined): string | null {
  if (!retailer) {
    return null;
  }
  if (retailer.key === "midtown") {
    return "Use the same save-as-HTML steps below. Midtown uses the dedicated parser (order #, line items, covers).";
  }
  if (retailer.status === "beta") {
    return (
      "Same workflow as Midtown: open your order detail page in the browser, press Ctrl+S, save as Webpage HTML, " +
      "then upload here. ComicOS uses best-effort parsing for this retailer; review every line on the next screen before confirming."
    );
  }
  if (retailer.is_fallback) {
    return "Upload a saved order page from any retailer. We’ll try generic parsing and you can fix fields before confirming.";
  }
  return null;
}

function statusClasses(retailer: SupportedRetailer): string {
  if (retailer.status === "supported") {
    return "border-emerald-400/40 bg-emerald-400/10 text-emerald-100";
  }
  if (retailer.is_fallback) {
    return "border-cyan-400/40 bg-cyan-400/10 text-cyan-100";
  }
  return "border-amber-400/40 bg-amber-400/10 text-amber-100";
}

export function RetailerHtmlImportPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [retailers, setRetailers] = useState<SupportedRetailer[]>([]);
  const [selectedRetailer, setSelectedRetailer] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void apiClient
      .listImportRetailers()
      .then((response) => {
        if (cancelled) {
          return;
        }
        setRetailers(response.items);
        const supported = response.items.find((item) => item.status === "supported");
        setSelectedRetailer((current) => current ?? supported?.key ?? response.items[0]?.key ?? null);
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof ApiError ? loadError.message : "Unable to load supported retailers.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedRetailerCard = retailers.find((item) => item.key === selectedRetailer);
  const importHint = retailerImportHint(selectedRetailerCard);

  const pickFile = useCallback((file: File | null) => {
    setError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (!isAcceptedFile(file)) {
      setSelectedFile(null);
      setError("Choose a saved retailer order page file (.html, .htm, or .txt).");
      return;
    }
    setSelectedFile(file);
  }, []);

  async function handleUpload(): Promise<void> {
    if (!selectedRetailer) {
      setError("Choose a retailer first.");
      return;
    }
    if (!selectedFile) {
      setError("Select the saved order HTML file first.");
      return;
    }
    setIsUploading(true);
    setError(null);
    try {
      const response = await apiClient.importRetailerOrderHtml(selectedRetailer, selectedFile);
      navigate(`/retailer-orders/${response.order_id}`);
    } catch (uploadError) {
      setError(uploadError instanceof ApiError ? uploadError.message : "Unable to import this file.");
    } finally {
      setIsUploading(false);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setDragActive(false);
    pickFile(event.dataTransfer.files[0] ?? null);
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Add comics"
        title="Import saved order HTML"
        description="Save your retailer order page as HTML (Ctrl+S), upload it here, review detected books, then confirm into your portfolio. Works for Midtown, Third Eye, DCBS, and more—no login or sync required."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6" aria-label="Supported retailers">
        <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-400">
          Choose your retailer
        </h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {retailers.map((retailer) => {
            const isSelected = retailer.key === selectedRetailer;
            return (
              <button
                key={retailer.key}
                type="button"
                onClick={() => {
                  setSelectedRetailer(retailer.key);
                  setError(null);
                }}
                aria-pressed={isSelected}
                className={`rounded-2xl border p-4 text-left transition ${
                  isSelected
                    ? "border-cyan-400/70 bg-cyan-400/10 ring-1 ring-cyan-400/40"
                    : "border-white/10 bg-slate-900/70 hover:border-white/25"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-white">{retailer.display_name}</span>
                </div>
                <span
                  className={`mt-3 inline-block rounded-full border px-3 py-1 text-xs font-medium ${statusClasses(
                    retailer,
                  )}`}
                >
                  {statusLabel(retailer)}
                </span>
                {retailer.is_fallback ? (
                  <p className="mt-3 text-xs text-slate-300">
                    Don&apos;t see your retailer? Upload a saved order page and ComicOS can add support.
                  </p>
                ) : null}
              </button>
            );
          })}
        </div>
        {importHint ? (
          <p className="mt-4 text-sm text-slate-300">{importHint}</p>
        ) : null}
      </section>

      <section className="mt-8 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <ol className="space-y-4 text-sm text-slate-200">
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-400/20 text-sm font-semibold text-cyan-200">
              1
            </span>
            <div>
              <p className="font-semibold text-white">Open your retailer order detail page</p>
              <p className="mt-1 text-slate-300">
                Go to the page that shows your order number and the list of books you bought.
              </p>
            </div>
          </li>
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-400/20 text-sm font-semibold text-cyan-200">
              2
            </span>
            <div>
              <p className="font-semibold text-white">Press Ctrl+S and save as Webpage HTML</p>
              <p className="mt-1 text-slate-300">
                Save the page as <span className="text-slate-100">Webpage, HTML Only</span>. You should get a{" "}
                <span className="font-mono text-slate-100">.html</span> file.
              </p>
            </div>
          </li>
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-400/20 text-sm font-semibold text-cyan-200">
              3
            </span>
            <div>
              <p className="font-semibold text-white">Drop the saved file here, then review the detected books</p>
              <p className="mt-1 text-slate-300">
                ComicOS reads the saved HTML, extracts your order and items, and opens the review page so you can
                confirm into your portfolio.
              </p>
            </div>
          </li>
        </ol>

        <div
          className={`mt-8 rounded-3xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragActive
              ? "border-cyan-400/60 bg-cyan-400/10"
              : "border-white/15 bg-slate-950/40 hover:border-white/25"
          }`}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setDragActive(false);
          }}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".html,.htm,.txt,text/html,text/plain"
            className="hidden"
            onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
          />
          <p className="text-sm text-slate-300">
            {selectedFile ? (
              <>
                Selected: <span className="font-medium text-white">{selectedFile.name}</span>
              </>
            ) : (
              "Drop your saved order .html file here"
            )}
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={isUploading}
              className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Choose file
            </button>
            <button
              type="button"
              onClick={() => void handleUpload()}
              disabled={isUploading || !selectedFile || !selectedRetailer}
              className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUploading ? "Importing…" : "Upload & review order"}
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => navigate("/retailer-orders")}
            className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:bg-white/5"
          >
            View imported orders
          </button>
        </div>
      </section>
    </AppShell>
  );
}
