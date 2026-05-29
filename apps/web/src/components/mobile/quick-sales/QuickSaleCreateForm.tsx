export function QuickSaleCreateForm({
  saleIdentifier,
  buyerLabel,
  saleSource,
  deviceId,
  sessionId,
  devices,
  sessions,
  submitting,
  onSaleIdentifierChange,
  onBuyerLabelChange,
  onSaleSourceChange,
  onDeviceIdChange,
  onSessionIdChange,
  onSubmit,
}: {
  saleIdentifier: string;
  buyerLabel: string;
  saleSource: string;
  deviceId: number | null;
  sessionId: number | null;
  devices: { id: number; device_name: string }[];
  sessions: { id: number; session_name: string }[];
  submitting: boolean;
  onSaleIdentifierChange: (value: string) => void;
  onBuyerLabelChange: (value: string) => void;
  onSaleSourceChange: (value: string) => void;
  onDeviceIdChange: (value: number) => void;
  onSessionIdChange: (value: number) => void;
  onSubmit: () => void;
}): JSX.Element {
  return (
    <div className="flex flex-wrap gap-2">
      <input
        value={saleIdentifier}
        onChange={(e) => onSaleIdentifierChange(e.target.value)}
        placeholder="Sale identifier"
        className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
      />
      <input
        value={buyerLabel}
        onChange={(e) => onBuyerLabelChange(e.target.value)}
        placeholder="Buyer label"
        className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
      />
      <select
        value={saleSource}
        onChange={(e) => onSaleSourceChange(e.target.value)}
        className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
      >
        <option value="mobile">mobile</option>
        <option value="convention">convention</option>
        <option value="offline">offline</option>
      </select>
      {saleSource === "convention" && sessions.length > 0 ? (
        <select
          value={sessionId ?? ""}
          onChange={(e) => onSessionIdChange(Number(e.target.value))}
          className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
        >
          {sessions.map((session) => (
            <option key={session.id} value={session.id}>
              {session.session_name}
            </option>
          ))}
        </select>
      ) : null}
      {(saleSource === "mobile" || saleSource === "offline") && devices.length > 0 ? (
        <select
          value={deviceId ?? ""}
          onChange={(e) => onDeviceIdChange(Number(e.target.value))}
          className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
        >
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.device_name}
            </option>
          ))}
        </select>
      ) : null}
      <button
        type="button"
        disabled={submitting || !saleIdentifier.trim()}
        onClick={onSubmit}
        className="rounded-xl border border-cyan-400/40 px-4 py-2 text-sm font-semibold text-cyan-100 disabled:opacity-50"
      >
        Create sale
      </button>
    </div>
  );
}
