export function ScanCaptureForm({
  scanType,
  scanValue,
  deviceId,
  devices,
  submitting,
  onScanTypeChange,
  onScanValueChange,
  onDeviceIdChange,
  onSubmit,
}: {
  scanType: string;
  scanValue: string;
  deviceId: number | null;
  devices: { id: number; device_name: string }[];
  submitting: boolean;
  onScanTypeChange: (value: string) => void;
  onScanValueChange: (value: string) => void;
  onDeviceIdChange: (value: number) => void;
  onSubmit: () => void;
}): JSX.Element {
  return (
    <div className="flex flex-wrap gap-2">
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
      <select
        value={scanType}
        onChange={(e) => onScanTypeChange(e.target.value)}
        className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
      >
        <option value="barcode">barcode</option>
        <option value="qr">qr</option>
        <option value="upc">upc</option>
        <option value="inventory_identifier">inventory_identifier</option>
      </select>
      <input
        value={scanValue}
        onChange={(e) => onScanValueChange(e.target.value)}
        placeholder="Scan value (manual entry)"
        className="min-w-[220px] rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
      />
      <button
        type="button"
        disabled={submitting || deviceId === null || !scanValue.trim()}
        onClick={onSubmit}
        className="rounded-xl border border-violet-400/40 px-4 py-2 text-sm font-semibold text-violet-100 disabled:opacity-50"
      >
        Capture scan
      </button>
    </div>
  );
}
