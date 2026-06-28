import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getStoredToken } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export type CollectionSummary = {
  id: number;
  name: string;
  collection_type: "real" | "test" | "sandbox";
  is_default: boolean;
  source_collection_id: number | null;
};

type CollectionContextValue = {
  collections: CollectionSummary[];
  activeCollectionId: number | null;
  activeCollection: CollectionSummary | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setActiveCollection: (collectionId: number) => Promise<void>;
  cloneCollection: (sourceId: number) => Promise<CollectionSummary>;
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

  const refresh = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setCollections([]);
      setActiveCollectionId(null);
      return;
    }
    setLoading(true);
    try {
      const body = await apiFetch<{ active_collection_id: number | null; items: CollectionSummary[] }>(
        token,
        "/api/collections",
      );
      setCollections(body.items);
      setActiveCollectionId(body.active_collection_id);
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

  const cloneCollection = useCallback(
    async (sourceId: number) => {
      const token = getStoredToken();
      if (!token) {
        throw new Error("Not authenticated");
      }
      const row = await apiFetch<CollectionSummary>(token, `/api/collections/${sourceId}/clone`, {
        method: "POST",
        body: JSON.stringify({}),
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
      refresh,
      setActiveCollection,
      cloneCollection,
      resetCollection,
      deleteCollection,
    }),
    [
      activeCollection,
      activeCollectionId,
      cloneCollection,
      collections,
      deleteCollection,
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
