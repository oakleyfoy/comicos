import type { OrganizationInventoryAssignmentResponse, OrganizationMemberResponse } from "../../../api/client";

type Props = {
  assignments: OrganizationInventoryAssignmentResponse[];
  members: OrganizationMemberResponse[];
  canManage: boolean;
  busyInventoryId: number | null;
  onAssign: (inventoryItemId: number, assignedUserId: number) => void;
  onComplete: (inventoryItemId: number) => void;
  onUnassign: (inventoryItemId: number) => void;
};

export function OrganizationInventoryAssignmentsPanel({
  assignments,
  members,
  canManage,
  busyInventoryId,
  onAssign,
  onComplete,
  onUnassign,
}: Props): JSX.Element {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-white">Staff assignments</h3>
      {!assignments.length ? <p className="text-sm text-slate-500">No assignment records yet.</p> : null}
      <ul className="space-y-2">
        {assignments.map((row) => (
          <li key={row.id} className="rounded-xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium text-white">Copy #{row.inventory_item_id}</p>
                <p className="text-xs text-slate-500">
                  {row.assignment_status} · staff #{row.assigned_user_id}
                </p>
              </div>
              {canManage && row.assignment_status === "ACTIVE" ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busyInventoryId === row.inventory_item_id}
                    className="rounded-lg border border-white/15 px-3 py-1 text-xs text-slate-200 hover:bg-white/5 disabled:opacity-50"
                    onClick={() => onComplete(row.inventory_item_id)}
                  >
                    Complete
                  </button>
                  <button
                    type="button"
                    disabled={busyInventoryId === row.inventory_item_id}
                    className="rounded-lg border border-rose-500/30 px-3 py-1 text-xs text-rose-200 hover:bg-rose-500/10 disabled:opacity-50"
                    onClick={() => onUnassign(row.inventory_item_id)}
                  >
                    Unassign
                  </button>
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {canManage ? (
        <div className="rounded-xl border border-dashed border-white/15 p-4 text-xs text-slate-400">
          Assign from the shared inventory table using member IDs:{" "}
          {members.map((member) => `${member.user_email} (${member.user_id})`).join(" · ") || "none"}
          <div className="mt-3 flex flex-wrap gap-2">
            {members.map((member) => (
              <button
                key={member.id}
                type="button"
                className="rounded-lg border border-white/10 px-2 py-1 text-[11px] text-slate-300 hover:bg-white/5"
                onClick={() => {
                  const raw = window.prompt("Inventory copy ID to assign to this member?");
                  const inventoryItemId = raw ? Number(raw) : NaN;
                  if (Number.isFinite(inventoryItemId)) {
                    onAssign(inventoryItemId, member.user_id);
                  }
                }}
              >
                Assign to {member.user_email}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
