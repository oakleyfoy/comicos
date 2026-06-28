import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getStoredToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export type CollectionStats = {
  books: number;
  orders: number;
  scans: number;
  retailer_imports: number;
};

export type CollectionSummary = {
  id: number;
  name: string;
  collection_type: "real" | "test" | "sandbox";
  is_default: boolean;
  source_collection_id: number | null;
  stats?: CollectionStats;
  created_at?: string;
  updated_at?: string;
};

type CollectionContextValue = {
  collections: CollectionSummary[];
  activeCollectionId: number | null;
  activeCollection: CollectionSummary | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setActiveCollection: (collectionId: number) => Promise<void>;
  createCollection: (name: string) => Promise<CollectionSummary>;
  cloneCollection: (sourceId: number, name?: string) => Promise<CollectionSummary>;
  resetCollection: (collectionId: number) => Promise<void>;
  deleteCollection: (collectionId: number) => Promise<void>;
};

const CollectionContext = createContext<CollectionContextValue | null>(null);

async function apiFetch<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || resp.statusText);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return (await resp.json()) as T;
}

export function CollectionProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [activeCollectionId, setActiveCollectionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setCollections([]);
      setActiveCollectionId(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const body = await apiFetch<{ active_collection_id: number | null; items: CollectionSummary[] }>(
        token,
        "/api/collections",
      );
      setCollections(body.items);
      setActiveCollectionId(body.active_collection_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load collections.");
      setCollections([]);
      setActiveCollectionId(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      void refresh();
    }
  }, [isAuthenticated, refresh]);

  const setActiveCollection = useCallback(
    async (collectionId: number) => {
      const token = getStoredToken();
      if (!token) {
        return;
      }
      await apiFetch(token, "/api/collections/active", {
        method: "POST",
        body: JSON.stringify({ collection_id: collectionId }),
      });
      await refresh();
    },
    [refresh],
  );

  const createCollection = useCallback(
    async (name: string) => {
      const token = getStoredToken();
      if (!token) {
        throw new Error("Not authenticated");
      }
      const row = await apiFetch<CollectionSummary>(token, "/api/collections", {
        method: "POST",
        body: JSON.stringify({ name, collection_type: "test" }),
      });
      await refresh();
      return row;
    },
    [refresh],
  );

  const cloneCollection = useCallback(
    async (sourceId: number, name?: string) => {
      const token = getStoredToken();
      if (!token) {
        throw new Error("Not authenticated");
      }
      const row = await apiFetch<CollectionSummary>(token, `/api/collections/${sourceId}/clone`, {
        method: "POST",
        body: JSON.stringify(name ? { name } : {}),
      });
      await refresh();
      return row;
    },
    [refresh],
  );

  const resetCollection = useCallback(
    async (collectionId: number) => {
      const token = getStoredToken();
      if (!token) {
        return;
      }
      await apiFetch(token, `/api/collections/${collectionId}/reset`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      await refresh();
    },
    [refresh],
  );

  const deleteCollection = useCallback(
    async (collectionId: number) => {
      const token = getStoredToken();
      if (!token) {
        return;
      }
      await apiFetch(token, `/api/collections/${collectionId}`, { method: "DELETE" });
      await refresh();
    },
    [refresh],
  );

  const activeCollection = useMemo(
    () => collections.find((c) => c.id === activeCollectionId) ?? null,
    [activeCollectionId, collections],
  );

  const value = useMemo(
    () => ({
      collections,
      activeCollectionId,
      activeCollection,
      loading,
      error,
      refresh,
      setActiveCollection,
      createCollection,
      cloneCollection,
      resetCollection,
      deleteCollection,
    }),
    [
      activeCollection,
      activeCollectionId,
      cloneCollection,
      collections,
      createCollection,
      deleteCollection,
      error,
      loading,
      refresh,
      resetCollection,
      setActiveCollection,
    ],
  );

  return <CollectionContext.Provider value={value}>{children}</CollectionContext.Provider>;
}

export function useCollections(): CollectionContextValue {
  const ctx = useContext(CollectionContext);
  if (!ctx) {
    throw new Error("useCollections requires CollectionProvider");
  }
  return ctx;
}

export function isTestLikeCollection(type: string | undefined): boolean {
  return type === "test" || type === "sandbox";
}
