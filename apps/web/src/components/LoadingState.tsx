export function LoadingState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-blue-200 bg-white p-6 shadow-sm">
      <div className="animate-pulse">
        <div className="h-3 w-28 rounded bg-blue-100" />
        <div className="mt-4 h-8 w-64 rounded bg-blue-100" />
        <div className="mt-3 h-4 w-full max-w-2xl rounded bg-slate-100" />
        <div className="mt-2 h-4 w-full max-w-xl rounded bg-slate-100" />
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="h-24 rounded-xl bg-slate-100" />
          <div className="h-24 rounded-xl bg-slate-100" />
          <div className="h-24 rounded-xl bg-slate-100" />
        </div>
      </div>
      <p className="mt-5 text-sm text-slate-600">
        <span className="font-medium text-patriot-navy">{title}</span>
        {" - "}
        {description}
      </p>
    </div>
  );
}
