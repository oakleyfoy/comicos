export function ShopifyStorefrontProjectionViewer({
  projection,
}: {
  projection: Record<string, unknown> | null;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Projection viewer</p>
      <h2 className="mt-1 text-base font-semibold text-white">Storefront projection payload</h2>
      {projection ? (
        <pre className="mt-4 max-h-[28rem] overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-xs text-slate-200">
          {JSON.stringify(projection, null, 2)}
        </pre>
      ) : (
        <p className="mt-4 text-sm text-slate-400">Generate a snapshot to inspect the deterministic storefront projection.</p>
      )}
    </section>
  );
}
