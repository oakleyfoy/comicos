import { useCallback, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type MidtownHtmlImportDiagnostics,
  type MidtownHtmlImportErrorPayload,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const ACCEPTED_EXTENSIONS = [".html", ".htm", ".txt"];

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

function diagnosticsFromApiError(error: ApiError): MidtownHtmlImportDiagnostics | null {
  const payload = error.data as MidtownHtmlImportErrorPayload | undefined;
  return payload?.diagnostics ?? null;
}

function MidtownImportDiagnosticsPanel({
  diagnostics,
}: {
  diagnostics: MidtownHtmlImportDiagnostics;
}) {
  const parsed = diagnostics.parsed;
  return (
    <section
      className="mt-4 rounded-2xl border border-amber-400/30 bg-slate-950/80 p-5 text-left text-sm text-slate-200"
      aria-label="Import diagnostics"
    >
      <h2 className="text-base font-semibold text-amber-100">What ComicOS saw in this file</h2>
      <dl className="mt-4 grid gap-2 sm:grid-cols-2">
        <div>
          <dt className="text-slate-400">Title tag</dt>
          <dd className="font-mono text-slate-100">{diagnostics.title ?? "(missing)"}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Page length</dt>
          <dd className="font-mono text-slate-100">{diagnostics.page_length.toLocaleString()} chars</dd>
        </div>
        <div>
          <dt className="text-slate-400">.order-item nodes</dt>
          <dd className="font-mono text-slate-100">{diagnostics.order_item_count}</dd>
        </div>
        <div>
          <dt className="text-slate-400">Links with Order #</dt>
          <dd className="font-mono text-slate-100">{diagnostics.order_number_link_count}</dd>
        </div>
        <div>
          <dt className="text-slate-400">#right-contents</dt>
          <dd className="font-mono text-slate-100">{diagnostics.has_right_contents ? "yes" : "no"}</dd>
        </div>
        <div>
          <dt className="text-slate-400">.info-container</dt>
          <dd className="font-mono text-slate-100">{diagnostics.has_info_container ? "yes" : "no"}</dd>
        </div>
        {diagnostics.saved_html_path ? (
          <div className="sm:col-span-2">
            <dt className="text-slate-400">Saved copy on server</dt>
            <dd className="break-all font-mono text-xs text-slate-300">{diagnostics.saved_html_path}</dd>
          </div>
        ) : null}
      </dl>

      {parsed ? (
        <div className="mt-5 border-t border-white/10 pt-4">
          <h3 className="font-semibold text-white">Parsed order preview</h3>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            {"retailer_order_number" in parsed && parsed.retailer_order_number ? (
              <div>
                <dt className="text-slate-400">Order number</dt>
                <dd className="font-mono text-slate-100">{parsed.retailer_order_number}</dd>
              </div>
            ) : null}
            {"order_status" in parsed ? (
              <div>
                <dt className="text-slate-400">Order status</dt>
                <dd className="font-mono text-slate-100">{parsed.order_status ?? "(missing)"}</dd>
              </div>
            ) : null}
            {"order_total" in parsed ? (
              <div>
                <dt className="text-slate-400">Order total</dt>
                <dd className="font-mono text-slate-100">{parsed.order_total ?? "(missing)"}</dd>
              </div>
            ) : null}
            {"items_parsed" in parsed ? (
              <div>
                <dt className="text-slate-400">Items parsed</dt>
                <dd className="font-mono text-slate-100">{parsed.items_parsed ?? 0}</dd>
              </div>
            ) : null}
            {"error" in parsed && parsed.error ? (
              <div className="sm:col-span-2">
                <dt className="text-slate-400">Parser error</dt>
                <dd className="font-mono text-red-200">{parsed.error}</dd>
              </div>
            ) : null}
          </dl>
          {parsed.item_titles && parsed.item_titles.length > 0 ? (
            <ul className="mt-3 list-inside list-disc text-slate-300">
              {parsed.item_titles.map((title) => (
                <li key={title}>{title}</li>
              ))}
            </ul>
          ) : parsed.items_parsed === 0 ? (
            <p className="mt-3 text-slate-400">No line items were extracted from the order body.</p>
          ) : null}
          {parsed.parse_diagnostics ? (
            <pre className="mt-4 max-h-48 overflow-auto rounded-xl bg-black/40 p-3 text-xs text-slate-300">
              {JSON.stringify(parsed.parse_diagnostics, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 border-t border-white/10 pt-4">
        <h3 className="font-semibold text-white">Visible text (first 5,000 characters)</h3>
        <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-black/40 p-3 text-xs text-slate-300">
          {diagnostics.visible_text_excerpt || "(empty)"}
        </pre>
      </div>
    </section>
  );
}

export function MidtownOrderHtmlUploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<MidtownHtmlImportDiagnostics | null>(null);

  const pickFile = useCallback((file: File | null) => {
    setError(null);
    setDiagnostics(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (!isAcceptedFile(file)) {
      setSelectedFile(null);
      setError("Choose a saved Midtown page file (.html, .htm, or .txt).");
      return;
    }
    setSelectedFile(file);
  }, []);

  async function handleUpload(): Promise<void> {
    if (!selectedFile) {
      setError("Select the saved Midtown order HTML file first.");
      return;
    }
    setIsUploading(true);
    setError(null);
    setDiagnostics(null);
    try {
      const response = await apiClient.importMidtownOrderHtml(selectedFile);
      navigate(`/retailer-orders/${response.order_id}`);
    } catch (uploadError) {
      if (uploadError instanceof ApiError) {
        setError(uploadError.message);
        setDiagnostics(diagnosticsFromApiError(uploadError));
      } else {
        setError(uploadError instanceof Error ? uploadError.message : "Unable to import this file.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files[0] ?? null;
    pickFile(file);
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Connected Retailers"
        title="Upload saved Midtown order"
        description="Import an order you saved from Midtown as a webpage file. No browser automation required."
      />

      {error ? (
        <div className="mt-6 space-y-4">
          <StatusBanner tone="error">{error}</StatusBanner>
          {diagnostics ? <MidtownImportDiagnosticsPanel diagnostics={diagnostics} /> : null}
        </div>
      ) : null}

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
        <ol className="space-y-4 text-sm text-slate-200">
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-400/20 text-sm font-semibold text-cyan-200">
              1
            </span>
            <div>
              <p className="font-semibold text-white">Open your Midtown order page</p>
              <p className="mt-1 text-slate-300">
                In your browser, go to the Midtown order detail page (the one that shows{" "}
                <span className="text-slate-100">Order #…</span> and your line items).
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
                Save the page as <span className="text-slate-100">Webpage, HTML Only</span> (or{" "}
                <span className="text-slate-100">Webpage, Complete</span>). You should get a{" "}
                <span className="font-mono text-slate-100">.html</span> file.
              </p>
            </div>
          </li>
          <li className="flex gap-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-400/20 text-sm font-semibold text-cyan-200">
              3
            </span>
            <div>
              <p className="font-semibold text-white">Drag the saved file here or click Upload</p>
              <p className="mt-1 text-slate-300">
                ComicOS reads the saved HTML, extracts your order and items, and opens the review page.
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
              "Drop your saved Midtown .html file here"
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
              disabled={isUploading || !selectedFile}
              className="rounded-2xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUploading ? "Importing…" : "Upload & review order"}
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => navigate("/connected-retailers/midtown/orders")}
            className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:bg-white/5"
          >
            Back to Midtown orders
          </button>
          <button
            type="button"
            onClick={() => navigate("/connected-retailers/import")}
            className="rounded-2xl border border-white/10 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:bg-white/5"
          >
            Connected Retailers
          </button>
        </div>
      </section>
    </AppShell>
  );
}
