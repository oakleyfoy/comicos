import type { InventoryItem } from "../../../api/client";

type Props = {
  items: InventoryItem[];
  loading: boolean;
};

export function OrganizationSharedInventoryListPanel({ items, loading }: Props): JSX.Element {
  if (loading) {
    return <p className="text-sm text-slate-400">Loading shared inventory…</p>;
  }
  if (!items.length) {
    return <p className="text-sm text-slate-500">No organization-scoped inventory rows match the current filters.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full text-left text-sm text-slate-200">
        <thead className="bg-slate-900/80 text-[11px] uppercase tracking-[0.14em] text-slate-500">
          <tr>
            <th className="px-4 py-3">Copy</th>
            <th className="px-4 py-3">Title</th>
            <th className="px-4 py-3">Assignment</th>
            <th className="px-4 py-3">Queue</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.inventory_copy_id} className="border-t border-white/5">
              <td className="px-4 py-3 font-mono text-xs text-slate-400">#{row.inventory_copy_id}</td>
              <td className="px-4 py-3">
                <p className="font-medium text-white">{row.title}</p>
                <p className="text-xs text-slate-500">
                  {row.publisher} #{row.issue_number}
                </p>
              </td>
              <td className="px-4 py-3">
                {row.organization_assignment_status ? (
                  <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">
                    {row.organization_assignment_status} → user {row.organization_assigned_user_id}
                  </span>
                ) : (
                  <span className="text-xs text-slate-500">Unassigned</span>
                )}
              </td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {row.organization_queue_name ? (
                  <>
                    {row.organization_queue_name}
                    {row.organization_queue_position ? ` · #${row.organization_queue_position}` : ""}
                  </>
                ) : (
                  "—"
                )}
                {row.organization_review_status ? (
                  <p className="mt-1 text-violet-300">
                    Review: {row.organization_review_status}
                    {row.organization_review_type ? ` (${row.organization_review_type})` : ""}
                  </p>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
