import { useState } from "react";

import { useCollections } from "../context/CollectionContext";

export function CollectionHeaderSwitcher(): JSX.Element | null {
  const { collections, activeCollectionId, activeCollection, loading, setActiveCollection } = useCollections();
  const [busy, setBusy] = useState(false);

  if (!collections.length) {
    return null;
  }

  const label = activeCollection?.name ?? "Collection";

  return (
    <label className="flex min-w-0 items-center gap-2 text-sm">
      <span className="hidden shrink-0 text-blue-100 sm:inline">Current:</span>
      <select
        className="max-w-[14rem] truncate rounded-md border border-white/30 bg-white/10 px-2 py-1.5 text-sm font-semibold text-white sm:max-w-[18rem]"
        value={activeCollectionId ?? ""}
        disabled={busy || loading}
        aria-label="Active collection"
        onChange={(e) => {
          const id = Number(e.target.value);
          setBusy(true);
          void setActiveCollection(id).finally(() => setBusy(false));
        }}
      >
        {collections.map((c) => (
          <option key={c.id} value={c.id} className="text-slate-900">
            {c.name}
          </option>
        ))}
      </select>
      <span className="sr-only">{label}</span>
    </label>
  );
}
