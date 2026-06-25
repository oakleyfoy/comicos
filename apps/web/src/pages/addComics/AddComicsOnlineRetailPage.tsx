import { Link } from "react-router-dom";

import { AppShell } from "../../components/AppShell";

export function AddComicsOnlineRetailPage(): JSX.Element {
  return (
    <AppShell>
      <div className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Online Retail Import</h1>
        <p className="mt-3 text-slate-600">
          Save your retailer order page as HTML and upload it here—no retailer login or automatic sync. Midtown uses a
          full parser; Third Eye, DCBS, and others use the same upload flow with beta parsers (always review before
          confirming).
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/connected-retailers/import"
            className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600"
          >
            Import saved order HTML
          </Link>
          <Link to="/retailer-orders" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium">
            View imported orders
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
