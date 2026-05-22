export function LoadingState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-xl shadow-black/20">
      <div className="animate-pulse">
        <div className="h-3 w-28 rounded bg-white/10" />
        <div className="mt-4 h-8 w-64 rounded bg-white/10" />
        <div className="mt-3 h-4 w-full max-w-2xl rounded bg-white/10" />
        <div className="mt-2 h-4 w-full max-w-xl rounded bg-white/10" />
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="h-24 rounded-2xl bg-white/5" />
          <div className="h-24 rounded-2xl bg-white/5" />
          <div className="h-24 rounded-2xl bg-white/5" />
        </div>
      </div>
      <p className="mt-5 text-sm text-slate-400">
        <span className="font-medium text-slate-300">{title}</span>
        {" - "}
        {description}
      </p>
    </div>
  );
}
