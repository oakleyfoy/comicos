import type { OrganizationAuditCategory, OrganizationComplianceSeverity } from "../../../api/client";

const AUDIT_CATEGORIES: OrganizationAuditCategory[] = [
  "organization",
  "permissions",
  "inventory",
  "reviews",
  "storefront",
  "security",
  "sessions",
  "notifications",
];

const SEVERITY_LEVELS: OrganizationComplianceSeverity[] = ["info", "warning", "elevated", "critical"];

type Props = {
  category: OrganizationAuditCategory | null;
  severity: OrganizationComplianceSeverity | null;
  actorFilter: string;
  resourceType: string;
  onCategoryChange: (value: OrganizationAuditCategory | null) => void;
  onSeverityChange: (value: OrganizationComplianceSeverity | null) => void;
  onActorFilterChange: (value: string) => void;
  onResourceTypeChange: (value: string) => void;
};

export function OrganizationAuditFilters({
  category,
  severity,
  actorFilter,
  resourceType,
  onCategoryChange,
  onSeverityChange,
  onActorFilterChange,
  onResourceTypeChange,
}: Props): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label className="text-sm text-slate-300">
          <span className="mb-1 block text-xs uppercase tracking-[0.14em] text-slate-500">Category</span>
          <select
            value={category ?? ""}
            onChange={(event) => onCategoryChange((event.target.value || null) as OrganizationAuditCategory | null)}
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
          >
            <option value="">All categories</option>
            {AUDIT_CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-slate-300">
          <span className="mb-1 block text-xs uppercase tracking-[0.14em] text-slate-500">Severity</span>
          <select
            value={severity ?? ""}
            onChange={(event) => onSeverityChange((event.target.value || null) as OrganizationComplianceSeverity | null)}
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
          >
            <option value="">All severities</option>
            {SEVERITY_LEVELS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-slate-300">
          <span className="mb-1 block text-xs uppercase tracking-[0.14em] text-slate-500">Actor user</span>
          <input
            value={actorFilter}
            onChange={(event) => onActorFilterChange(event.target.value)}
            placeholder="Any"
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white placeholder:text-slate-500"
          />
        </label>

        <label className="text-sm text-slate-300">
          <span className="mb-1 block text-xs uppercase tracking-[0.14em] text-slate-500">Resource type</span>
          <input
            value={resourceType}
            onChange={(event) => onResourceTypeChange(event.target.value)}
            placeholder="Any"
            className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white placeholder:text-slate-500"
          />
        </label>
      </div>
    </section>
  );
}
