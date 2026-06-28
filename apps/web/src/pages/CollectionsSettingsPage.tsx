import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";
import { patriotInputClass } from "../components/patriotTheme";
import {
  isTestLikeCollection,
  useCollections,
  type CollectionSummary,
} from "../context/CollectionContext";

function formatType(type: string): string {
  if (type === "real") {
    return "Real";
  }
  if (type === "test") {
    return "Test";
  }
  if (type === "sandbox") {
    return "Sandbox";
  }
  return type;
}

function formatWhen(iso: string | undefined): string {
  if (!iso) {
    return "—";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  return d.toLocaleString();
}

function CollectionCard({
  row,
  isActive,
  busy,
  onOpen,
  onClone,
  onReset,
  onDelete,
}: {
  row: CollectionSummary;
  isActive: boolean;
  busy: boolean;
  onOpen: () => void;
  onClone: () => void;
  onReset: () => void;
  onDelete: () => void;
}): JSX.Element {
  const stats = row.stats;
  const testLike = isTestLikeCollection(row.collection_type);

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{row.name}</h2>
          <p className="text-sm text-slate-600">Type: {formatType(row.collection_type)}</p>
          {isActive ? (
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-patriot-blue">Active now</p>
          ) : null}
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">Books</dt>
          <dd className="font-semibold tabular-nums text-slate-900">{stats?.books ?? 0}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Orders</dt>
          <dd className="font-semibold tabular-nums text-slate-900">{stats?.orders ?? 0}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Scans</dt>
          <dd className="font-semibold tabular-nums text-slate-900">{stats?.scans ?? 0}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Retailer Imports</dt>
          <dd className="font-semibold tabular-nums text-slate-900">{stats?.retailer_imports ?? 0}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Created</dt>
          <dd className="text-slate-800">{formatWhen(row.created_at)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Last Updated</dt>
          <dd className="text-slate-800">{formatWhen(row.updated_at)}</dd>
        </div>
      </dl>
      <div className="mt-5 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-lg bg-patriot-blue px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          disabled={busy || isActive}
          onClick={onOpen}
        >
          Open
        </button>
        <button
          type="button"
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-800 disabled:opacity-50"
          disabled={busy}
          onClick={onClone}
        >
          Clone
        </button>
        {testLike ? (
          <>
            <button
              type="button"
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-800 disabled:opacity-50"
              disabled={busy}
              onClick={onReset}
            >
              Reset
            </button>
            <button
              type="button"
              className="rounded-lg border border-red-300 px-3 py-1.5 text-sm font-semibold text-red-700 disabled:opacity-50"
              disabled={busy}
              onClick={onDelete}
            >
              Delete
            </button>
          </>
        ) : null}
      </div>
    </article>
  );
}

export function CollectionsSettingsPage(): JSX.Element {
  const {
    collections,
    activeCollectionId,
    loading,
    error,
    refresh,
    setActiveCollection,
    cloneCollection,
    resetCollection,
    deleteCollection,
    createCollection,
  } = useCollections();
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [showNew, setShowNew] = useState(false);

  const sorted = useMemo(
    () =>
      [...collections].sort((a, b) => {
        if (a.collection_type === "real") {
          return -1;
        }
        if (b.collection_type === "real") {
          return 1;
        }
        return a.id - b.id;
      }),
    [collections],
  );

  async function withBusy(fn: () => Promise<void>): Promise<void> {
    setBusy(true);
    setLocalError(null);
    try {
      await fn();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Settings"
        title="Collections"
        description="Maintain one real collection. Clone to test scanner, imports, and migrations safely."
      />
      {(error || localError) && (
        <StatusBanner tone="error">
          {localError ?? error}
          <button type="button" className="ml-3 underline" onClick={() => void refresh()}>
            Retry
          </button>
        </StatusBanner>
      )}
      {loading && collections.length === 0 ? (
        <p className="text-sm text-slate-600">Loading collections…</p>
      ) : null}
      <div className="space-y-4">
        {sorted.map((row) => (
          <CollectionCard
            key={row.id}
            row={row}
            isActive={row.id === activeCollectionId}
            busy={busy}
            onOpen={() =>
              void withBusy(async () => {
                await setActiveCollection(row.id);
              })
            }
            onClone={() =>
              void withBusy(async () => {
                const clone = await cloneCollection(row.id);
                await setActiveCollection(clone.id);
              })
            }
            onReset={() => {
              if (!window.confirm("Reset this test collection? Collection-owned data will be removed.")) {
                return;
              }
              void withBusy(async () => {
                await resetCollection(row.id);
              });
            }}
            onDelete={() => {
              if (!window.confirm("Delete this test collection? This cannot be undone.")) {
                return;
              }
              void withBusy(async () => {
                await deleteCollection(row.id);
              });
            }}
          />
        ))}
      </div>
      <section className="mt-8 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5">
        {!showNew ? (
          <button
            type="button"
            className="text-sm font-semibold text-patriot-blue"
            onClick={() => setShowNew(true)}
          >
            + New Collection
          </button>
        ) : (
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void withBusy(async () => {
                const name = newName.trim() || "Untitled Test Collection";
                await createCollection(name);
                setNewName("");
                setShowNew(false);
              });
            }}
          >
            <label className="block min-w-[16rem] flex-1 text-sm">
              <span className="font-medium text-slate-700">Name</span>
              <input
                className={`${patriotInputClass} mt-1 w-full`}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Scanner Regression"
              />
            </label>
            <button
              type="submit"
              className="rounded-lg bg-patriot-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              disabled={busy}
            >
              Create test collection
            </button>
            <button type="button" className="text-sm text-slate-600" onClick={() => setShowNew(false)}>
              Cancel
            </button>
          </form>
        )}
      </section>
      <p className="mt-6 text-sm text-slate-600">
        Tip: use <strong>Clone</strong> on your real collection before risky work.{" "}
        <Link to="/settings/account" className="text-patriot-blue underline">
          Account &amp; data
        </Link>{" "}
        still controls permanent account-wide reset.
      </p>
    </AppShell>
  );
}
