export function ConventionBoothManager({
  booths,
  canManage,
  submitting,
  boothName,
  sessionId,
  sessions,
  onBoothNameChange,
  onSessionIdChange,
  onCreate,
  onOpen,
}: {
  booths: import("../../../api/client").ConventionBoothResponse[];
  canManage: boolean;
  submitting: boolean;
  boothName: string;
  sessionId: number | null;
  sessions: import("../../../api/client").ConventionSessionResponse[];
  onBoothNameChange: (v: string) => void;
  onSessionIdChange: (v: number) => void;
  onCreate: () => void;
  onOpen: (boothId: number) => void;
}): JSX.Element {
  return (
    <div className="space-y-4">
      {canManage ? (
        <div className="flex flex-wrap gap-2">
          <select
            value={sessionId ?? ""}
            onChange={(e) => onSessionIdChange(Number(e.target.value))}
            className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.session_name}
              </option>
            ))}
          </select>
          <input
            value={boothName}
            onChange={(e) => onBoothNameChange(e.target.value)}
            placeholder="Booth name"
            className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
          />
          <button
            type="button"
            disabled={submitting || sessionId === null || !boothName.trim()}
            onClick={onCreate}
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-200 disabled:opacity-50"
          >
            Add booth
          </button>
        </div>
      ) : null}
      <ul className="space-y-2">
        {booths.map((booth) => (
          <li key={booth.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 px-4 py-3">
            <span className="text-sm text-white">
              {booth.booth_name} <span className="text-slate-500">({booth.booth_status})</span>
            </span>
            {canManage && booth.booth_status === "setup" ? (
              <button type="button" disabled={submitting} onClick={() => onOpen(booth.id)} className="text-xs text-emerald-200 underline">
                Open booth
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
