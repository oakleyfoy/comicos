import { Link } from "react-router-dom";

import type { P91CollectorHomeSetupStatusRead } from "../../api/client";

type TaskDef = {
  id: string;
  title: string;
  description: string;
  cta: string;
  to: string;
  complete: boolean;
  icon: string;
};

function buildTasks(status: P91CollectorHomeSetupStatusRead): TaskDef[] {
  return [
    {
      id: "import",
      title: "Import your first order",
      description: "Connect Gmail or paste an order so ComicOS can start building your inventory.",
      cta: "Import order",
      to: "/imports/guided",
      complete: status.imported_first_order,
      icon: "📥",
    },
    {
      id: "review",
      title: "Review unmatched books",
      description: "Check any books ComicOS could not match automatically.",
      cta: "Review imports",
      to: "/imports",
      complete: status.imports_review_complete,
      icon: "🔍",
    },
    {
      id: "inventory",
      title: "Confirm inventory",
      description: "Verify your first inventory items so ComicOS can track value and recommendations.",
      cta: "View inventory",
      to: "/dashboard/collection",
      complete: status.has_inventory,
      icon: "📚",
    },
    {
      id: "pull-list",
      title: "Create pull list",
      description: "Tell ComicOS what series you actively collect so it can watch future releases.",
      cta: "Create pull list",
      to: "/pull-lists",
      complete: status.has_pull_list,
      icon: "📋",
    },
    {
      id: "recommendations",
      title: "View recommendations",
      description: "Review your first personalized buy, hold, or watch recommendations.",
      cta: "View recommendations",
      to: "/collector-recommendations",
      complete: status.recommendations_viewed,
      icon: "✨",
    },
    {
      id: "budget",
      title: "Set buying budget",
      description: "Set monthly buying limits so ComicOS can prioritize smarter buys.",
      cta: "Set budget",
      to: "/collector-budget",
      complete: status.has_budget,
      icon: "💳",
    },
  ];
}

type Props = {
  status: P91CollectorHomeSetupStatusRead;
  dismissing?: boolean;
  onDismiss?: () => void;
};

export function FirstTimeSetupChecklist({ status, dismissing, onDismiss }: Props): JSX.Element {
  const tasks = buildTasks(status);
  const progressPct = Math.round((status.completed_count / status.total_count) * 100);

  return (
    <section
      className="mb-6 overflow-hidden rounded-xl border border-slate-700/80 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 p-5 shadow-lg"
      data-testid="first-time-setup-checklist"
      aria-labelledby="first-time-setup-heading"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Getting started</p>
          <h2 id="first-time-setup-heading" className="mt-1 text-lg font-semibold text-white">
            Finish setting up ComicOS
          </h2>
          <p className="mt-1 max-w-xl text-sm leading-relaxed text-slate-300">
            Complete these steps so ComicOS can track your collection, watch future releases, and personalize
            recommendations.
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold text-white" data-testid="setup-checklist-progress-label">
            {status.completed_count} of {status.total_count} complete
            {status.percent_complete != null ? ` (${status.percent_complete}%)` : ""}
          </p>
          <div className="mt-2 h-2 w-40 max-w-full overflow-hidden rounded-full bg-slate-700">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${progressPct}%` }}
              role="progressbar"
              aria-valuenow={status.completed_count}
              aria-valuemin={0}
              aria-valuemax={status.total_count}
            />
          </div>
        </div>
      </div>

      <ul className="mt-5 space-y-3">
        {tasks.map((task) => (
          <li
            key={task.id}
            className={`flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between ${
              task.complete
                ? "border-emerald-500/30 bg-emerald-950/20"
                : "border-slate-700/80 bg-slate-950/40"
            }`}
            data-testid={`setup-task-${task.id}`}
            data-complete={task.complete ? "true" : "false"}
          >
            <div className="flex min-w-0 items-start gap-3">
              <span
                className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm ${
                  task.complete ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-800 text-slate-200"
                }`}
                aria-hidden
              >
                {task.complete ? "✓" : task.icon}
              </span>
              <div className="min-w-0">
                <p className={`font-medium ${task.complete ? "text-emerald-100" : "text-white"}`}>{task.title}</p>
                <p className="mt-0.5 text-sm text-slate-400">{task.description}</p>
              </div>
            </div>
            {!task.complete ? (
              <Link
                to={task.to}
                className="inline-flex shrink-0 items-center justify-center rounded-md border border-slate-500 bg-slate-800 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700"
              >
                {task.cta}
              </Link>
            ) : (
              <span className="text-xs font-medium text-emerald-400">Done</span>
            )}
          </li>
        ))}
      </ul>

      {status.can_dismiss_checklist && onDismiss ? (
        <div className="mt-4 flex justify-end border-t border-slate-700/80 pt-4">
          <button
            type="button"
            disabled={dismissing}
            onClick={onDismiss}
            className="text-sm font-medium text-slate-400 hover:text-white disabled:opacity-50"
            data-testid="setup-checklist-dismiss"
          >
            {dismissing ? "Hiding…" : "Hide checklist"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
