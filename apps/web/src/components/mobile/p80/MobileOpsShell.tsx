import { Link } from "react-router-dom";

export function MobileOpsShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-lg">
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P80-02</p>
          <h1 className="text-xl font-semibold">{title}</h1>
          <nav className="mt-3 flex flex-wrap gap-2 text-xs">
            <Link to="/mobile-scan" className="rounded-full border border-slate-700 px-3 py-1 text-slate-300">
              Scan
            </Link>
            <Link to="/mobile-intake" className="rounded-full border border-slate-700 px-3 py-1 text-slate-300">
              Intake
            </Link>
            <Link to="/mobile-storage" className="rounded-full border border-slate-700 px-3 py-1 text-slate-300">
              Storage
            </Link>
            <Link to="/mobile-audit" className="rounded-full border border-slate-700 px-3 py-1 text-slate-300">
              Audit
            </Link>
            <Link to="/mobile-operations" className="rounded-full border border-slate-700 px-3 py-1 text-slate-300">
              Ops
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-lg space-y-4 px-4 py-6">{children}</main>
    </div>
  );
}
