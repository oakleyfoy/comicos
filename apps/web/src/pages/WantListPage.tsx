import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type WantListItemRead,
  type WantListPriority,
  type WantListItemStatus,
  type WantListRead,
  type WantListSummaryRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

const PRIORITIES: WantListPriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const STATUSES: WantListItemStatus[] = ["WANTED", "FOUND", "ACQUIRED", "REMOVED"];

function priorityClass(p: WantListPriority): string {
  if (p === "CRITICAL") return "text-rose-300";
  if (p === "HIGH") return "text-amber-200";
  if (p === "MEDIUM") return "text-cyan-200";
  return "text-slate-400";
}

export function WantListPage(): JSX.Element {
  const [lists, setLists] = useState<WantListSummaryRead[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<WantListRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [newListName, setNewListName] = useState("");
  const [itemForm, setItemForm] = useState({
    publisher: "",
    series_name: "",
    issue_number: "",
    variant_description: "",
    priority: "MEDIUM" as WantListPriority,
    notes: "",
  });
  const [editing, setEditing] = useState<WantListItemRead | null>(null);

  const loadLists = useCallback(async () => {
    const body = await apiClient.getWantLists();
    setLists(body.items);
    setSelectedId((prev) => prev ?? (body.items[0]?.id ?? null));
  }, []);

  const loadDetail = useCallback(async (id: number) => {
    const body = await apiClient.getWantList(id);
    setDetail(body);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await loadLists();
      if (selectedId !== null) {
        await loadDetail(selectedId);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load want lists.");
    } finally {
      setLoading(false);
    }
  }, [loadDetail, loadLists, selectedId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (selectedId === null) return;
    void loadDetail(selectedId).catch((err) => {
      setError(err instanceof ApiError ? err.message : "Unable to load list.");
    });
  }, [loadDetail, selectedId]);

  async function onCreateList() {
    setMessage(null);
    setError(null);
    if (!newListName.trim()) {
      setError("Enter a list name.");
      return;
    }
    try {
      const created = await apiClient.createWantList({ name: newListName.trim() });
      setNewListName("");
      setSelectedId(created.id);
      setMessage(`Created list "${created.name}".`);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create list.");
    }
  }

  async function onAddItem() {
    if (selectedId === null) return;
    setMessage(null);
    setError(null);
    if (!itemForm.series_name.trim() || !itemForm.issue_number.trim()) {
      setError("Series and issue number are required.");
      return;
    }
    try {
      await apiClient.addWantListItem(selectedId, {
        publisher: itemForm.publisher,
        series_name: itemForm.series_name.trim(),
        issue_number: itemForm.issue_number.trim(),
        variant_description: itemForm.variant_description,
        priority: itemForm.priority,
        notes: itemForm.notes,
      });
      setItemForm({
        publisher: "",
        series_name: "",
        issue_number: "",
        variant_description: "",
        priority: "MEDIUM",
        notes: "",
      });
      setMessage("Item added.");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to add item.");
    }
  }

  async function onSaveEdit() {
    if (!editing) return;
    setMessage(null);
    setError(null);
    try {
      await apiClient.patchWantListItem(editing.id, {
        publisher: editing.publisher,
        series_name: editing.series_name,
        issue_number: editing.issue_number,
        variant_description: editing.variant_description,
        priority: editing.priority,
        status: editing.status,
        notes: editing.notes,
      });
      setEditing(null);
      setMessage("Item updated.");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update item.");
    }
  }

  async function onRemoveItem(itemId: number) {
    setMessage(null);
    setError(null);
    try {
      await apiClient.deleteWantListItem(itemId);
      setMessage("Item removed.");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to remove item.");
    }
  }

  const items = detail?.items ?? [];

  return (
    <AppShell>
      <PageHeader
        eyebrow="P55-01"
        title="Want Lists"
        description="Track comics you wish to acquire — manual wanted books, priorities, and status (no marketplace search or purchases)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      <div className="mt-6 flex flex-wrap gap-6">
        <div className="min-w-[220px] rounded-3xl border border-white/10 bg-slate-900/65 p-4">
          <p className="text-xs uppercase text-slate-500">Want lists</p>
          {loading && lists.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">Loading…</p>
          ) : (
            <ul className="mt-3 space-y-1">
              {lists.map((list) => (
                <li key={list.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(list.id)}
                    className={`w-full rounded-lg px-2 py-1.5 text-left text-sm ${
                      selectedId === list.id ? "bg-cyan-500/20 text-cyan-100" : "text-slate-300 hover:bg-white/5"
                    }`}
                  >
                    {list.name}
                    <span className="ml-2 text-xs text-slate-500">({list.item_count})</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 border-t border-white/10 pt-4">
            <input
              type="text"
              placeholder="New list name"
              value={newListName}
              onChange={(e) => setNewListName(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
            />
            <button
              type="button"
              onClick={() => void onCreateList()}
              className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
            >
              Create list
            </button>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          {detail ? (
            <>
              <h2 className="text-lg font-semibold text-white">{detail.name}</h2>
              {detail.description ? <p className="mt-1 text-sm text-slate-400">{detail.description}</p> : null}

              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <input
                  placeholder="Publisher"
                  value={itemForm.publisher}
                  onChange={(e) => setItemForm((f) => ({ ...f, publisher: e.target.value }))}
                  className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
                />
                <input
                  placeholder="Series *"
                  value={itemForm.series_name}
                  onChange={(e) => setItemForm((f) => ({ ...f, series_name: e.target.value }))}
                  className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
                />
                <input
                  placeholder="Issue # *"
                  value={itemForm.issue_number}
                  onChange={(e) => setItemForm((f) => ({ ...f, issue_number: e.target.value }))}
                  className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
                />
                <input
                  placeholder="Variant"
                  value={itemForm.variant_description}
                  onChange={(e) => setItemForm((f) => ({ ...f, variant_description: e.target.value }))}
                  className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
                />
                <select
                  value={itemForm.priority}
                  onChange={(e) => setItemForm((f) => ({ ...f, priority: e.target.value as WantListPriority }))}
                  className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
                <input
                  placeholder="Notes"
                  value={itemForm.notes}
                  onChange={(e) => setItemForm((f) => ({ ...f, notes: e.target.value }))}
                  className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-sm text-white"
                />
              </div>
              <button
                type="button"
                onClick={() => void onAddItem()}
                className="mt-3 rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100"
              >
                Add wanted book
              </button>

              {items.length === 0 ? (
                <p className="mt-6 text-sm text-slate-400">No items on this list yet.</p>
              ) : (
                <div className="mt-6 overflow-x-auto rounded-3xl border border-white/10 bg-slate-900/65">
                  <table className="min-w-full text-left text-sm">
                    <thead className="border-b border-white/10 text-xs uppercase text-slate-500">
                      <tr>
                        <th className="px-4 py-3">Book</th>
                        <th className="px-4 py-3">Priority</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Notes</th>
                        <th className="px-4 py-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) =>
                        editing?.id === item.id ? (
                          <tr key={item.id} className="border-b border-white/5">
                            <td className="px-4 py-3">
                              <input
                                value={editing.series_name}
                                onChange={(e) => setEditing({ ...editing, series_name: e.target.value })}
                                className="mb-1 w-full rounded border border-white/10 bg-slate-950 px-2 py-1 text-xs"
                              />
                              <input
                                value={editing.issue_number}
                                onChange={(e) => setEditing({ ...editing, issue_number: e.target.value })}
                                className="w-full rounded border border-white/10 bg-slate-950 px-2 py-1 text-xs"
                              />
                            </td>
                            <td className="px-4 py-3">
                              <select
                                value={editing.priority}
                                onChange={(e) =>
                                  setEditing({ ...editing, priority: e.target.value as WantListPriority })
                                }
                                className="rounded border border-white/10 bg-slate-950 px-2 py-1 text-xs text-white"
                              >
                                {PRIORITIES.map((p) => (
                                  <option key={p} value={p}>
                                    {p}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="px-4 py-3">
                              <select
                                value={editing.status}
                                onChange={(e) =>
                                  setEditing({ ...editing, status: e.target.value as WantListItemStatus })
                                }
                                className="rounded border border-white/10 bg-slate-950 px-2 py-1 text-xs text-white"
                              >
                                {STATUSES.map((s) => (
                                  <option key={s} value={s}>
                                    {s}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="px-4 py-3">
                              <input
                                value={editing.notes}
                                onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
                                className="w-full min-w-[120px] rounded border border-white/10 bg-slate-950 px-2 py-1 text-xs"
                              />
                            </td>
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                onClick={() => void onSaveEdit()}
                                className="text-cyan-300 hover:underline"
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditing(null)}
                                className="ml-2 text-slate-400 hover:underline"
                              >
                                Cancel
                              </button>
                            </td>
                          </tr>
                        ) : (
                          <tr key={item.id} className="border-b border-white/5">
                            <td className="px-4 py-3 text-white">
                              {item.publisher ? `${item.publisher} · ` : ""}
                              {item.series_name} #{item.issue_number}
                              {item.variant_description ? (
                                <span className="block text-xs text-slate-500">{item.variant_description}</span>
                              ) : null}
                            </td>
                            <td className={`px-4 py-3 font-medium ${priorityClass(item.priority)}`}>
                              {item.priority}
                            </td>
                            <td className="px-4 py-3 text-slate-300">{item.status}</td>
                            <td className="px-4 py-3 text-slate-400">{item.notes || "—"}</td>
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                onClick={() => setEditing(item)}
                                className="text-cyan-300 hover:underline"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => void onRemoveItem(item.id)}
                                className="ml-2 text-rose-300 hover:underline"
                              >
                                Remove
                              </button>
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-400">Select a want list.</p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
