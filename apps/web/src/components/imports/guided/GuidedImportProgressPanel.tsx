import type { GuidedImportProgressRead } from "../../../api/client";

type Props = {
  progress: GuidedImportProgressRead | null;
};

export function GuidedImportProgressPanel({ progress }: Props): JSX.Element {
  const phases = progress?.phases ?? [
    { code: "UPLOADING", label: "Reading order", complete: false, active: true },
    { code: "PARSING", label: "Matching comics", complete: false, active: false },
    { code: "MATCHING", label: "Finding covers", complete: false, active: false },
    { code: "ENRICHING", label: "Checking release data", complete: false, active: false },
    { code: "READY_FOR_REVIEW", label: "Building inventory preview", complete: false, active: false },
  ];

  return (
    <ul className="mt-4 space-y-2" data-testid="guided-import-progress">
      {phases.map((phase) => (
        <li
          key={phase.code}
          className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-sm ${
            phase.active ? "border-white/30 bg-white/5" : "border-slate-800 bg-slate-900/40"
          }`}
        >
          <span className={phase.complete ? "text-emerald-400" : phase.active ? "text-white" : "text-slate-600"}>
            {phase.complete ? "✓" : phase.active ? "…" : "○"}
          </span>
          <span className={phase.complete || phase.active ? "text-slate-100" : "text-slate-500"}>{phase.label}</span>
        </li>
      ))}
    </ul>
  );
}
