import type { MobileDeviceAccessLogResponse } from "../../../api/client";

export function MobileSecurityAccessLogViewer({ logs }: { logs: MobileDeviceAccessLogResponse[] }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div>
        <h2 className="text-lg font-semibold text-white">Access logs</h2>
        <p className="mt-1 text-sm text-slate-400">Recent allow and deny decisions written by device-aware mobile workflows.</p>
      </div>
      <div className="mt-4 space-y-3">
        {logs.map((log) => (
          <div key={log.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">
                Device #{log.mobile_device_id} / user #{log.user_id}
              </p>
              <span className="rounded-full border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.14em] text-slate-300">
                {log.access_result}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-300">{log.access_reason}</p>
            <p className="mt-2 text-xs text-slate-500">{new Date(log.accessed_at).toLocaleString()}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
