import { AppShell } from "../../components/AppShell";

export function AddComicsManualPage(): JSX.Element {
  return (
    <AppShell>
      <div className="mx-auto max-w-lg px-4 py-12 text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-900">Manual Entry</h1>
      <p className="mt-4 text-slate-600">Coming next:</p>
      <p className="mt-2 text-sm text-slate-500">
        Search by title, issue number, publisher, barcode, or series tree.
      </p>
      </div>
    </AppShell>
  );
}
