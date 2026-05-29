import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type {
  MarketplacePricingRuleCreateRequest,
  MarketplacePricingRuleResponse,
  MarketplacePricingRuleUpdateRequest,
} from "../../../api/client";

export function MarketplacePricingRuleEditorShell({
  canManage,
  submitting,
  selectedRule,
  onSave,
  onClear,
}: {
  canManage: boolean;
  submitting: boolean;
  selectedRule: MarketplacePricingRuleResponse | null;
  onSave: (
    payload: MarketplacePricingRuleCreateRequest | MarketplacePricingRuleUpdateRequest,
    ruleId: number | null,
  ) => Promise<void>;
  onClear: () => void;
}): JSX.Element {
  const [ruleKey, setRuleKey] = useState("");
  const [ruleName, setRuleName] = useState("");
  const [ruleStatus, setRuleStatus] = useState("active");
  const [rulePayloadJson, setRulePayloadJson] = useState('{"rule_type":"fixed_margin","margin_amount":"1.00"}');
  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedRule) {
      setRuleKey(selectedRule.rule_key);
      setRuleName(selectedRule.rule_name);
      setRuleStatus(selectedRule.rule_status);
      setRulePayloadJson(JSON.stringify(selectedRule.rule_payload_json, null, 2));
    } else {
      setRuleKey("");
      setRuleName("");
      setRuleStatus("active");
      setRulePayloadJson('{"rule_type":"fixed_margin","margin_amount":"1.00"}');
    }
    setJsonError(null);
  }, [selectedRule]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    let parsedPayload: Record<string, unknown>;
    try {
      parsedPayload = JSON.parse(rulePayloadJson) as Record<string, unknown>;
      setJsonError(null);
    } catch {
      setJsonError("Rule payload must be valid JSON.");
      return;
    }
    await onSave(
      {
        rule_key: ruleKey.trim(),
        rule_name: ruleName.trim(),
        rule_status: ruleStatus,
        rule_payload_json: parsedPayload,
      },
      selectedRule?.id ?? null,
    );
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Rule editor</p>
          <h2 className="mt-1 text-base font-semibold text-white">
            {selectedRule ? `Edit ${selectedRule.rule_name}` : "Create a pricing rule"}
          </h2>
        </div>
        {selectedRule ? (
          <button
            type="button"
            className="rounded-2xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200"
            onClick={onClear}
          >
            Create new
          </button>
        ) : null}
      </div>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Rule key</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={ruleKey}
              onChange={(event) => setRuleKey(event.target.value)}
              disabled={Boolean(selectedRule) || !canManage}
              placeholder="fixed_margin_10_percent"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Rule name</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={ruleName}
              onChange={(event) => setRuleName(event.target.value)}
              disabled={!canManage}
              placeholder="10% margin"
            />
          </label>
        </div>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Status</span>
          <select
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={ruleStatus}
            onChange={(event) => setRuleStatus(event.target.value)}
            disabled={!canManage}
          >
            <option value="active">active</option>
            <option value="inactive">inactive</option>
          </select>
        </label>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Rule payload JSON</span>
          <textarea
            className="min-h-[180px] rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 font-mono text-xs text-slate-100"
            value={rulePayloadJson}
            onChange={(event) => setRulePayloadJson(event.target.value)}
            disabled={!canManage}
          />
        </label>
        {jsonError ? <p className="text-sm text-rose-300">{jsonError}</p> : null}
        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={!canManage || submitting}
            className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {selectedRule ? "Save rule" : "Create rule"}
          </button>
          {selectedRule ? (
            <button
              type="button"
              disabled={submitting}
              onClick={onClear}
              className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel edit
            </button>
          ) : null}
        </div>
      </form>
    </section>
  );
}
