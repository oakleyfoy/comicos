import { Link } from "react-router-dom";

import { AppShell } from "../../components/AppShell";

export function AddComicsOnlineRetailPage(): JSX.Element {
  return (
    <AppShell>
      <div className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Online Retail Import</h1>
        <p className="mt-3 text-slate-600">
          Import orders from connected retailers. Midtown HTML import is working today; additional retailers are
          rolling out under the same flow.
        </p>
        <ul className="mt-6 space-y-2 text-sm text-slate-700">
          <li>
            <span className="font-semibold text-emerald-700">Working:</span> Midtown, DCBS (HTML), Third Eye, Lunar
            (via existing tools)
          </li>
          <li>
            <span className="font-semibold text-amber-700">Coming soon:</span> eBay, Whatnot deep links
          </li>
        </ul>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/connected-retailers/import"
            className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600"
          >
            Open retailer import
          </Link>
          <Link to="/connected-retailers" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium">
            Connected retailers
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
