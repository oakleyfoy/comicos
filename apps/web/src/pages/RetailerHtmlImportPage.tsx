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

function mergeImportRetailerOptions(
  catalogItems: { key: string; display_name: string; accepts_upload: boolean }[],
  accounts: { retailer: string; display_name?: string | null }[],
): RetailerOption[] {
  const accountLabelByKey = new Map<string, string>();
  for (const account of accounts) {
    const label = (account.display_name?.trim() || account.retailer).replace(/_/g, " ");
    accountLabelByKey.set(account.retailer, label);
  }
  const options = catalogItems
    .filter((item) => item.accepts_upload)
    .map((item) => ({
      key: item.key,
      label: accountLabelByKey.get(item.key) ?? item.display_name,
    }));
  return dedupeRetailerOptions(options).sort((a, b) => {
    if (a.key === "unknown") return 1;
    if (b.key === "unknown") return -1;
    return a.label.localeCompare(b.label);
  });
}

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
        const [catalog, accounts] = await Promise.all([
          apiClient.listImportRetailers(),
          apiClient.getRetailerAccounts(),
        ]);
        const options = mergeImportRetailerOptions(catalog.items, accounts.items);
        if (!cancelled) {
          setRetailerOptions(options);
          setSelectedRetailer((current) => current || options[0]?.key || "");
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
      "mt-2 w-full max-w-md rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-900 shadow-sm outline-none focus:border-patriot-blue focus:ring-2 focus:ring-patriot-blue/25",
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
        <label
          className="block text-sm font-semibold text-patriot-navy"
          htmlFor="retailer-import-select"
        >
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

      <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-lg shadow-slate-200/60">
        <p className="text-sm text-slate-600">
          Open your order detail page in the browser, press Ctrl+S, save as Webpage HTML, then upload the file below.
        </p>

        <div
          className={`mt-6 rounded-3xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragActive
              ? "border-patriot-blue bg-blue-50"
              : "border-slate-300 bg-slate-50 hover:border-slate-400"
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
          <p className="text-sm text-slate-600">
            {selectedFile ? (
              <>
                Selected: <span className="font-medium text-slate-900">{selectedFile.name}</span>
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
              className="rounded-2xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 transition hover:border-patriot-blue hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Choose file
            </button>
            <button
              type="button"
              onClick={() => void handleUpload()}
              disabled={isUploading || !selectedFile || !selectedRetailer}
              className="rounded-2xl bg-patriot-blue px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-900 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUploading ? "Importing…" : "Upload & review order"}
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => navigate("/retailer-orders")}
            className="rounded-2xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-patriot-blue hover:text-patriot-blue"
          >
            View imported orders
          </button>
        </div>
      </section>
    </AppShell>
  );
}
