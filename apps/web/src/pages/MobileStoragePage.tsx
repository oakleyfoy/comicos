import { useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { MobileOpsShell } from "../components/mobile/p80/MobileOpsShell";
import { StatusBanner } from "../components/StatusBanner";

export function MobileStoragePage(): JSX.Element {
  const [barcode, setBarcode] = useState("");
  const [boxId, setBoxId] = useState("");
  const [copyId, setCopyId] = useState<number | null>(null);
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [path, setPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function scan(): Promise<void> {
    setError(null);
    const trimmed = barcode.trim();
    if (!trimmed) return;
    try {
      const scan = await apiClient.createMobileScan({ barcode: trimmed });
      const id = scan.book_intelligence?.inventory_id ?? null;
      setCopyId(id);
      if (id) {
        const sug = await apiClient.suggestMobileStorage({
          inventory_copy_id: id,
          box_id: boxId ? Number(boxId) : undefined,
        });
        setSuggestion(
          sug.suggested_slot_number
            ? `Box ${sug.recommended_box_name} · Slot ${sug.suggested_slot_number}`
            : "No slot available",
        );
        setPath(sug.location_path_text ?? null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed.");
    }
  }

  async function assign(): Promise<void> {
    if (!copyId || !boxId) return;
    setError(null);
    try {
      const result = await apiClient.assignMobileStorage({
        inventory_copy_id: copyId,
        box_id: Number(boxId),
        use_suggested_slot: true,
      });
      setPath(`${result.box_name} · Slot ${result.slot_number}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Assign failed.");
    }
  }

  return (
    <MobileOpsShell title="Put away">
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <input
        className="w-full rounded-2xl border border-slate-600 bg-slate-950 px-4 py-3"
        placeholder="Scan book"
        value={barcode}
        onChange={(e) => setBarcode(e.target.value)}
      />
      <input
        className="w-full rounded-2xl border border-slate-600 bg-slate-950 px-4 py-3"
        placeholder="Box id"
        value={boxId}
        onChange={(e) => setBoxId(e.target.value)}
      />
      <button type="button" className="w-full rounded-2xl bg-violet-600 py-3 text-sm font-semibold" onClick={() => void scan()}>
        Suggest slot
      </button>
      <button type="button" className="w-full rounded-2xl border border-slate-600 py-3 text-sm" onClick={() => void assign()}>
        Assign to box
      </button>
      {suggestion ? <p className="text-sm text-violet-200">{suggestion}</p> : null}
      {path ? <p className="text-xs text-slate-400">{path}</p> : null}
    </MobileOpsShell>
  );
}
