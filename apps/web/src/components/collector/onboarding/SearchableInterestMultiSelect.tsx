import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { ApiError, apiClient, type P91InterestOptionRead } from "../../../api/client";

type Props = {
  kind: "PUBLISHER" | "CHARACTER" | "CREATOR";
  selected: string[];
  onChange: (labels: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
};

export function SearchableInterestMultiSelect({
  kind,
  selected,
  onChange,
  placeholder = "Search…",
  disabled = false,
}: Props): JSX.Element {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<P91InterestOptionRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedSet = useMemo(() => new Set(selected.map((s) => s.toLowerCase())), [selected]);

  const visibleOptions = useMemo(
    () => options.filter((opt) => !selectedSet.has(opt.label.toLowerCase())),
    [options, selectedSet],
  );

  const load = useCallback(async (search: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.searchCollectorOnboardingInterestOptions({ kind, q: search, limit: 50 });
      setOptions(res.items);
      setActiveIndex(0);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed.");
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, [kind]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void load(query);
    }, 180);
    return () => window.clearTimeout(handle);
  }, [query, load]);

  function addLabel(label: string): void {
    const trimmed = label.trim();
    if (!trimmed || selectedSet.has(trimmed.toLowerCase())) return;
    onChange([...selected, trimmed]);
    setQuery("");
    inputRef.current?.focus();
  }

  function removeLabel(label: string): void {
    onChange(selected.filter((item) => item !== label));
  }

  function onInputKeyDown(event: React.KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(visibleOptions.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && visibleOptions[activeIndex]) {
      event.preventDefault();
      addLabel(visibleOptions[activeIndex].label);
    } else if (event.key === "Escape") {
      setQuery("");
    } else if (event.key === "Backspace" && !query && selected.length > 0) {
      onChange(selected.slice(0, -1));
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex min-h-[2.75rem] flex-wrap gap-2 rounded-lg border border-slate-200 bg-white px-2 py-2 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-200">
        {selected.map((label) => (
          <button
            key={label}
            type="button"
            disabled={disabled}
            className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1 text-xs font-medium text-white"
            onClick={() => removeLabel(label)}
            aria-label={`Remove ${label}`}
          >
            {label}
            <span aria-hidden>×</span>
          </button>
        ))}
        <input
          ref={inputRef}
          type="search"
          role="combobox"
          aria-expanded={visibleOptions.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          disabled={disabled}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onInputKeyDown}
          placeholder={selected.length ? "Add another…" : placeholder}
          className="min-w-[8rem] flex-1 border-0 bg-transparent px-1 py-1 text-sm text-slate-900 outline-none placeholder:text-slate-400"
        />
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {loading ? <p className="text-xs text-slate-500">Searching catalog…</p> : null}
      <ul id={listId} role="listbox" className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-slate-100 bg-slate-50 p-1">
        {visibleOptions.length === 0 && !loading ? (
          <li className="px-3 py-2 text-sm text-slate-500">No matches — try a different search.</li>
        ) : null}
        {visibleOptions.map((opt, index) => (
          <li key={`${opt.label}-${opt.source_id ?? index}`}>
            <button
              type="button"
              role="option"
              aria-selected={index === activeIndex}
              disabled={disabled}
              className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition ${
                index === activeIndex ? "bg-white shadow-sm ring-1 ring-slate-200" : "hover:bg-white/80"
              }`}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => addLabel(opt.label)}
            >
              <span className="font-medium text-slate-900">{opt.label}</span>
              {opt.subtitle ? <span className="text-xs text-slate-500">{opt.subtitle}</span> : null}
            </button>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-500">Optional — skip anytime and refine later in Settings.</p>
    </div>
  );
}
