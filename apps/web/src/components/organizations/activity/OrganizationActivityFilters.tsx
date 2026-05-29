import type { OrganizationActivityCategory } from "../../../api/client";

const CATEGORIES: OrganizationActivityCategory[] = [
  "organization",
  "inventory",
  "reviews",
  "storefront",
  "security",
  "permissions",
];

type Props = {
  category: OrganizationActivityCategory | null;
  onCategoryChange: (category: OrganizationActivityCategory | null) => void;
};

export function OrganizationActivityFilters({ category, onCategoryChange }: Props): JSX.Element {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onCategoryChange(null)}
        className={`rounded-full border px-3 py-1 text-xs font-semibold ${
          category === null ? "border-cyan-400/50 bg-cyan-500/15 text-cyan-100" : "border-white/10 text-slate-400"
        }`}
      >
        All
      </button>
      {CATEGORIES.map((value) => (
        <button
          key={value}
          type="button"
          onClick={() => onCategoryChange(value)}
          className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${
            category === value ? "border-violet-400/50 bg-violet-500/15 text-violet-100" : "border-white/10 text-slate-400"
          }`}
        >
          {value}
        </button>
      ))}
    </div>
  );
}
