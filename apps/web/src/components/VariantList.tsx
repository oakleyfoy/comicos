import type { ReleaseVariantRead } from "../api/client";

export function VariantList({ items }: { items: ReleaseVariantRead[] }): JSX.Element {
  if (!items.length) {
    return <p className="text-sm text-slate-500">No variants yet.</p>;
  }
  return (
    <ul className="space-y-2 text-sm text-slate-300">
      {items.map((row) => (
        <li key={row.id} className="flex justify-between gap-3">
          <span>{row.variant_name}</span>
          <span className="text-slate-400">
            {row.is_incentive_variant && row.ratio_value ? `1:${row.ratio_value}` : row.variant_type}
          </span>
        </li>
      ))}
    </ul>
  );
}
