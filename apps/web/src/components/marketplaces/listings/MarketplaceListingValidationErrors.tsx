import type { MarketplaceListingValidationErrorResponse } from "../../../api/client";

type Props = {
  errors: MarketplaceListingValidationErrorResponse[];
};

export function MarketplaceListingValidationErrors({ errors }: Props): JSX.Element | null {
  if (!errors.length) {
    return null;
  }
  return (
    <div className="rounded-2xl border border-rose-400/20 bg-rose-500/5 p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-rose-300">Validation</p>
      <ul className="mt-2 space-y-1 text-sm text-rose-100">
        {errors.map((row) => (
          <li key={row.code}>
            <span className="font-mono text-xs text-rose-200">{row.code}</span> — {row.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
