import { useEffect, useState } from "react";

import { ApiError, apiClient, type P79StorageLocationRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function StorageLocationsPage(): JSX.Element {
  const [locations, setLocations] = useState<P79StorageLocationRead[]>([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("LOCATION");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.listStorageLocations();
      setLocations(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load locations.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  async function createLocation() {
    if (!name.trim()) return;
    try {
      await apiClient.createStorageLocation({
        location_kind: kind,
        name: name.trim(),
        parent_id: null,
      });
      setName("");
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed.");
    }
  }

  async function seedOffice() {
    try {
      await apiClient.createStorageLocation({
        location_kind: "LOCATION",
        name: "Office",
        seed_office_template: true,
      });
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Seed failed.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Storage"
        title="Storage Locations"
        description="Physical hierarchy: location → room → rack → shelf → box → slot (P79-01)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <section className="mb-6 flex flex-wrap gap-2">
        <input
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Location name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <select
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="LOCATION">Location</option>
          <option value="ROOM">Room</option>
          <option value="RACK">Rack</option>
          <option value="SHELF">Shelf</option>
        </select>
        <button type="button" className="rounded bg-slate-900 px-4 py-2 text-sm text-white" onClick={() => void createLocation()}>
          Create
        </button>
        <button type="button" className="rounded border border-slate-300 px-4 py-2 text-sm" onClick={() => void seedOffice()}>
          Seed Office template
        </button>
      </section>
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      <ul className="space-y-2 text-sm text-slate-700">
        {locations.map((loc) => (
          <li key={loc.id} className="rounded border border-slate-200 bg-white p-3">
            <span className="font-medium">{loc.name}</span>{" "}
            <span className="text-slate-500">({loc.location_kind})</span> — {loc.utilization_pct}% used
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
