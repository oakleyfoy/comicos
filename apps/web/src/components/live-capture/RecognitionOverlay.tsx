interface RecognitionOverlayProps {
  title: string;
  subtitle?: string | null;
  status?: string | null;
}

export function RecognitionOverlay({ title, subtitle, status }: RecognitionOverlayProps): JSX.Element {
  return (
    <div className="pointer-events-none absolute inset-0 flex flex-col justify-between rounded-3xl border border-white/10 bg-gradient-to-b from-slate-950/10 via-transparent to-slate-950/50 p-4 text-white">
      <div className="rounded-2xl bg-slate-950/70 px-3 py-2 text-sm font-semibold uppercase tracking-[0.2em] text-slate-200">
        {title}
      </div>
      <div className="space-y-2">
        {subtitle ? <div className="inline-flex rounded-2xl bg-emerald-500/90 px-3 py-2 text-sm font-semibold text-slate-950">{subtitle}</div> : null}
        {status ? <div className="inline-flex rounded-2xl bg-slate-950/80 px-3 py-2 text-xs text-slate-300">{status}</div> : null}
      </div>
    </div>
  );
}
