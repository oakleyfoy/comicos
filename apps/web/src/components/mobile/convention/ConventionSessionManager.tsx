export function ConventionSessionManager({
  sessions,
  canManage,
  submitting,
  sessionName,
  onSessionNameChange,
  onCreate,
  onStart,
}: {
  sessions: import("../../../api/client").ConventionSessionResponse[];
  canManage: boolean;
  submitting: boolean;
  sessionName: string;
  onSessionNameChange: (v: string) => void;
  onCreate: () => void;
  onStart: (sessionId: number) => void;
}): JSX.Element {
  return (
    <div className="space-y-4">
      {canManage ? (
        <div className="flex flex-wrap gap-2">
          <input
            value={sessionName}
            onChange={(e) => onSessionNameChange(e.target.value)}
            placeholder="Session name"
            className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
          />
          <button
            type="button"
            disabled={submitting || !sessionName.trim()}
            onClick={onCreate}
            className="rounded-xl border border-orange-400/40 px-4 py-2 text-sm font-semibold text-orange-100 disabled:opacity-50"
          >
            Create session
          </button>
        </div>
      ) : null}
      <div className="overflow-x-auto rounded-2xl border border-white/10">
        <table className="min-w-full text-left text-sm text-slate-200">
          <thead className="border-b border-white/10 bg-slate-950/60 text-[11px] uppercase tracking-[0.14em] text-slate-500">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((row) => (
              <tr key={row.id} className="border-b border-white/5">
                <td className="px-4 py-3 font-medium text-white">{row.session_name}</td>
                <td className="px-4 py-3">{row.session_status}</td>
                <td className="px-4 py-3">
                  {canManage && row.session_status === "planned" ? (
                    <button
                      type="button"
                      disabled={submitting}
                      onClick={() => onStart(row.id)}
                      className="text-xs text-orange-200 underline disabled:opacity-50"
                    >
                      Start
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
