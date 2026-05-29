import type { PublicStorefrontInventoryItem, PublicStorefrontResponse } from "../../api/client";

type Props = {
  storefront: PublicStorefrontResponse | null;
  inventory: PublicStorefrontInventoryItem[];
  featured: PublicStorefrontInventoryItem[];
  loading: boolean;
};

export function StorefrontHeroPanel({ storefront, loading }: Pick<Props, "storefront" | "loading">): JSX.Element {
  if (loading || !storefront) {
    return <p className="text-sm text-slate-400">Loading storefront…</p>;
  }
  return (
    <section className="rounded-3xl border border-white/10 bg-gradient-to-br from-slate-950 via-slate-900 to-violet-950/40 p-8">
      <p className="text-xs uppercase tracking-[0.18em] text-violet-300">Dealer storefront</p>
      <h1 className="mt-2 text-3xl font-semibold text-white">{storefront.profile.display_name}</h1>
      {storefront.profile.tagline ? <p className="mt-2 text-slate-300">{storefront.profile.tagline}</p> : null}
      {storefront.profile.location_label ? (
        <p className="mt-3 text-sm text-slate-500">{storefront.profile.location_label}</p>
      ) : null}
    </section>
  );
}

export function StorefrontInventoryPanel({
  inventory,
  featured,
}: Pick<Props, "inventory" | "featured">): JSX.Element {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-5">
        <h2 className="text-sm font-semibold text-white">Featured inventory</h2>
        {!featured.length ? <p className="mt-3 text-sm text-slate-500">No featured items configured.</p> : null}
        <ul className="mt-3 space-y-2 text-sm text-slate-200">
          {featured.map((row) => (
            <li key={row.inventory_copy_id} className="rounded-lg border border-white/10 px-3 py-2">
              {row.title} #{row.issue_number} · {row.publisher}
            </li>
          ))}
        </ul>
      </section>
      <section className="rounded-2xl border border-white/10 bg-slate-950/45 p-5">
        <h2 className="text-sm font-semibold text-white">Public inventory</h2>
        {!inventory.length ? <p className="mt-3 text-sm text-slate-500">No public inventory available.</p> : null}
        <ul className="mt-3 space-y-2 text-sm text-slate-200">
          {inventory.map((row) => (
            <li key={row.inventory_copy_id} className="rounded-lg border border-white/10 px-3 py-2">
              {row.title} #{row.issue_number}
              {row.current_fmv ? ` · $${row.current_fmv}` : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
