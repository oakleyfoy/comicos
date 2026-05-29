import type { MarketplacePricingRuleResponse } from "../../../api/client";

export function MarketplacePricingRuleList({
  items,
  busyRuleId,
  canManage,
  onSelect,
  onToggleStatus,
}: {
  items: MarketplacePricingRuleResponse[];
  busyRuleId: number | null;
  canManage: boolean;
  onSelect: (rule: MarketplacePricingRuleResponse | null) => void;
  onToggleStatus: (ruleId: number, ruleStatus: "active" | "inactive") => Promise<void>;
}): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Pricing rules</p>
          <h2 className="mt-1 text-base font-semibold text-white">Deterministic rule evaluation inputs</h2>
        </div>
        <p className="text-sm text-slate-400">{items.length} loaded</p>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">No pricing rules have been created yet.</p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm">
            <thead className="bg-white/5 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Rule</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((item) => (
                <tr key={item.id} className="bg-slate-950/35 align-top text-slate-200">
                  <td className="px-4 py-3">
                    <button type="button" className="text-left font-medium text-white" onClick={() => onSelect(item)}>
                      {item.rule_name}
                    </button>
                    <p className="mt-1 text-xs text-slate-500">{item.rule_key}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    <p>{String(item.rule_payload_json["rule_type"] ?? "custom")}</p>
                    <p>Updated: {new Date(item.updated_at).toLocaleString()}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">
                      {item.rule_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {canManage ? (
                      <div className="flex flex-wrap gap-2">
                        <ActionButton disabled={busyRuleId === item.id} onClick={() => onSelect(item)}>
                          Edit
                        </ActionButton>
                        <ActionButton
                          disabled={busyRuleId === item.id}
                          onClick={() => void onToggleStatus(item.id, item.rule_status === "active" ? "inactive" : "active")}
                        >
                          {item.rule_status === "active" ? "Deactivate" : "Activate"}
                        </ActionButton>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">View only</p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ActionButton({
  children,
  disabled,
  onClick,
}: {
  children: string;
  disabled: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-2xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}
