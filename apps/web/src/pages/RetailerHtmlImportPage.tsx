import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, apiClient } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const ACCEPTED_EXTENSIONS = [".html", ".htm", ".txt"];

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

type RetailerOption = { key: string; label: string };

function dedupeRetailerOptions(items: RetailerOption[]): RetailerOption[] {
  const seen = new Set<string>();
  const out: RetailerOption[] = [];
  for (const item of items) {
    if (seen.has(item.key)) {
      continue;
    }
    seen.add(item.key);
    out.push(item);
  }
  return out;
}

export function RetailerHtmlImportPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [retailerOptions, setRetailerOptions] = useState<RetailerOption[]>([]);
  const [selectedRetailer, setSelectedRetailer] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const accounts = await apiClient.getRetailerAccounts();
        const fromAccounts = dedupeRetailerOptions(
          accounts.items.map((account) => ({
            key: account.retailer,
            label: (account.display_name?.trim() || account.retailer).replace(/_/g, " "),
          })),
        );
        if (fromAccounts.length > 0) {
          if (!cancelled) {
            setRetailerOptions(fromAccounts);
            setSelectedRetailer((current) => current || fromAccounts[0].key);
          }
          return;
        }
        const catalog = await apiClient.listImportRetailers();
        const fromCatalog = dedupeRetailerOptions(
          catalog.items.map((item) => ({ key: item.key, label: item.display_name })),
        );
        if (!cancelled) {
          setRetailerOptions(fromCatalog);
          setSelectedRetailer((current) => current || fromCatalog[0]?.key || "");
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof ApiError ? loadError.message : "Unable to load retailers.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectClass = useMemo(
    () =>
      "mt-2 w-full max-w-md rounded-2xl border border-white/15 bg-slate-950/80 px-4 py-3 text-sm text-white outline-none focus:border-cyan-400/50",
    [],
  );

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
        description="Save your order page as HTML (Ctrl+S), pick your retailer, upload, and review before adding to your portfolio."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6" aria-label="Retailer selection">
        <label className="block text-sm font-semibold text-slate-200" htmlFor="retailer-import-select">
          Choose a Retailer
        </label>
        <select
          id="retailer-import-select"
          value={selectedRetailer}
          disabled={retailerOptions.length === 0 || isUploading}
          onChange={(event) => {
            setSelectedRetailer(event.target.value);
            setError(null);
          }}
          className={selectClass}
        >
          {retailerOptions.length === 0 ? (
            <option value="">Loading retailers…</option>
          ) : (
            retailerOptions.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))
          )}
        </select>
      </section>

      <section className="mt-8 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <p className="text-sm text-slate-300">
          Open your order detail page in the browser, press Ctrl+S, save as Webpage HTML, then upload the file below.
        </p>

        <div
          className={`mt-6 rounded-3xl border-2 border-dashed px-6 py-10 text-center transition ${
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
