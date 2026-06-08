type Props = {
  title: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
  children?: React.ReactNode;
  badge?: string;
};

export function WizardSelectionCard({
  title,
  description,
  selected,
  onSelect,
  children,
  badge,
}: Props): JSX.Element {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full rounded-xl border p-4 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 ${
        selected
          ? "border-slate-900 bg-slate-900 text-white shadow-lg"
          : "border-slate-200 bg-white text-slate-900 hover:border-slate-400 hover:shadow-sm"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          <p className={`mt-1 text-sm ${selected ? "text-slate-200" : "text-slate-600"}`}>{description}</p>
        </div>
        {badge ? (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
              selected ? "bg-white/15 text-white" : "bg-slate-100 text-slate-600"
            }`}
          >
            {badge}
          </span>
        ) : null}
      </div>
      {children ? <div className={`mt-3 text-sm ${selected ? "text-slate-100" : "text-slate-600"}`}>{children}</div> : null}
    </button>
  );
}
