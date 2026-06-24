import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  barcodeMethodLabel,
  finalMatchSourceLabel,
  readComicWithGpt,
  type GptComicReadResult,
} from "../../api/gptComicRead";
import { AppShell } from "../../components/AppShell";

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{value?.trim() ? value : "—"}</dd>
    </div>
  );
}

export function GptComicReadPage(): JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<GptComicReadResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const onSelectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.files?.[0] ?? null;
    setFile(next);
    setResult(null);
    setError(null);
  };

  const onRead = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await readComicWithGpt(file);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read image with GPT");
    } finally {
      setLoading(false);
    }
  };

  const gpt = result?.gpt_read;
  const barcodeDisplay =
    result?.barcode_read.barcode?.trim() ||
    (result && !result.barcode_read.barcode ? "Not detected" : null);

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-4 py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">GPT Comic Read</h1>
        <p className="mt-3 text-slate-600">
          Upload one comic photo for GPT identification, optional barcode verification, and local catalog
          matching. Missing barcodes never block adding books to your collection.
        </p>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your photo</p>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              data-testid="gpt-comic-read-input"
              className="hidden"
              onChange={onSelectFile}
            />
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-3 rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-200"
            >
              {file ? "Choose a different image" : "Upload image"}
            </button>
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Uploaded comic preview"
                className="mt-3 max-h-[520px] w-full rounded-xl object-contain bg-slate-50"
              />
            ) : (
              <p className="mt-3 text-sm text-slate-500">No image selected yet.</p>
            )}
            <button
              type="button"
              disabled={!file || loading}
              onClick={() => void onRead()}
              className="mt-4 rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {loading ? "Reading with GPT…" : "Read with GPT"}
            </button>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">GPT Comic Read</p>
            {loading ? <p className="mt-4 text-sm text-slate-600">Asking GPT…</p> : null}
            {!loading && !result ? (
              <p className="mt-4 text-sm text-slate-500">Upload an image and click “Read with GPT”.</p>
            ) : null}
            {result && gpt ? (
              <>
                <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                  <Field label="Publisher" value={gpt.publisher} />
                  <Field label="Series" value={gpt.series} />
                  <Field label="Issue Number" value={gpt.issue_number} />
                  <Field label="Issue Title" value={gpt.issue_title} />
                  <Field label="Year" value={gpt.year} />
                  <Field label="Cover Date" value={gpt.cover_date} />
                  <Field label="Variant" value={gpt.variant_description} />
                  <Field
                    label="Confidence"
                    value={
                      gpt.confidence != null ? `${Math.round(gpt.confidence * 100)}%` : null
                    }
                  />
                </dl>

                <div className="mt-6 rounded-xl border border-slate-100 bg-slate-50 p-3" data-testid="gpt-barcode-section">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Barcode</p>
                  <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                    <Field label="Barcode" value={barcodeDisplay} />
                    <Field label="Method" value={barcodeMethodLabel(result.barcode_read.method)} />
                    <Field
                      label="ComicVine barcode match"
                      value={result.comicvine_barcode_match.matched ? "Found" : "Not found"}
                    />
                    <Field
                      label="Final match source"
                      value={finalMatchSourceLabel(result.final_match_source)}
                    />
                  </dl>
                  {result.catalog_match.matched ? (
                    <p className="mt-2 text-xs text-slate-600">
                      Local catalog: {result.catalog_match.series} #{result.catalog_match.issue_number}
                      {result.catalog_match.publisher ? ` · ${result.catalog_match.publisher}` : ""}
                    </p>
                  ) : null}
                </div>

                {gpt.reasoning ? (
                  <div className="mt-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Reasoning</p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{gpt.reasoning}</p>
                  </div>
                ) : null}
                {gpt.possible_alternates && gpt.possible_alternates.length > 0 ? (
                  <div className="mt-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Possible Alternatives
                    </p>
                    <ul className="mt-1 list-disc pl-5 text-sm text-slate-800">
                      {gpt.possible_alternates.map((alt) => (
                        <li key={alt}>{alt}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <p className="mt-4 text-xs text-slate-400">
                  Model: {gpt.model} · {gpt.image_width}×{gpt.image_height}
                </p>
              </>
            ) : null}
          </div>
        </div>

        <Link to="/add-comics/photo" className="mt-8 inline-block text-sm text-blue-700 hover:underline">
          ← Phone Photo Import
        </Link>
      </div>
    </AppShell>
  );
}
