import { useState } from "react";

import { isTestLikeCollection, useCollections } from "../context/CollectionContext";

export function CollectionSwitcherBar(): JSX.Element | null {
  const {
    collections,
    activeCollectionId,
    activeCollection,
    setActiveCollection,
    cloneCollection,
    resetCollection,
    deleteCollection,
  } = useCollections();
  const [busy, setBusy] = useState(false);

  if (!collections.length) {
    return null;
  }

  const onClone = async () => {
    if (activeCollectionId == null) {
      return;
    }
    setBusy(true);
    try {
      const clone = await cloneCollection(activeCollectionId);
      await setActiveCollection(clone.id);
    } finally {
      setBusy(false);
    }
  };

  const onReset = async () => {
    if (activeCollectionId == null || !activeCollection || !isTestLikeCollection(activeCollection.collection_type)) {
      return;
    }
    if (!window.confirm("Reset this test collection? All collection-owned data will be removed.")) {
      return;
    }
    setBusy(true);
    try {
      await resetCollection(activeCollectionId);
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async () => {
    if (activeCollectionId == null || !activeCollection || !isTestLikeCollection(activeCollection.collection_type)) {
      return;
    }
    if (!window.confirm("Delete this test collection? This cannot be undone.")) {
      return;
    }
    setBusy(true);
    try {
      await deleteCollection(activeCollectionId);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
      {activeCollection && isTestLikeCollection(activeCollection.collection_type) ? (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-900">
          Test collection active — changes here do not affect your real collection.
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-600">Collection</label>
        <select
          className="min-w-[12rem] rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
          value={activeCollectionId ?? ""}
          disabled={busy}
          onChange={(e) => void setActiveCollection(Number(e.target.value))}
        >
          {collections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.collection_type})
            </option>
          ))}
        </select>
        <button
          type="button"
          className="rounded-md bg-patriot-blue px-2 py-1 text-xs font-semibold text-white disabled:opacity-50"
          disabled={busy || activeCollectionId == null}
          onClick={() => void onClone()}
        >
          Clone collection
        </button>
        {activeCollection && isTestLikeCollection(activeCollection.collection_type) ? (
          <>
            <button
              type="button"
              className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 disabled:opacity-50"
              disabled={busy}
              onClick={() => void onReset()}
            >
              Reset test collection
            </button>
            <button
              type="button"
              className="rounded-md border border-red-300 px-2 py-1 text-xs font-semibold text-red-700 disabled:opacity-50"
              disabled={busy}
              onClick={() => void onDelete()}
            >
              Delete test collection
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
