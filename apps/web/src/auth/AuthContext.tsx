import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  apiClient,
  clearStoredToken,
  getStoredToken,
  setStoredToken,
  type LoginPayload,
  type OrganizationSecurityContextRead,
  type RegisterPayload,
  type User,
} from "../api/client";
import { clearPersistedActiveOrganizationId } from "../lib/securityContext";
import { hydrateSecurityContext, switchOrganizationContext } from "../lib/sessionManager";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  securityContext: OrganizationSecurityContextRead | null;
  isOpsAdmin: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  refreshSecurityContext: () => Promise<void>;
  switchOrganization: (organizationId: number) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [securityContext, setSecurityContext] = useState<OrganizationSecurityContextRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const configuredOpsAdmins = useMemo(
    () =>
      (import.meta.env.VITE_OPS_ADMIN_EMAILS ?? "")
        .split(",")
        .map((value: string) => value.trim().toLowerCase())
        .filter(Boolean),
    [],
  );

  const refreshSecurityContext = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setSecurityContext(null);
      return;
    }
    try {
      const nextContext = await hydrateSecurityContext();
      setSecurityContext(nextContext);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setSecurityContext(null);
        return;
      }
      throw error;
    }
  }, []);

  const refreshUser = useCallback(async () => {
    const token = getStoredToken();

    if (!token) {
      setUser(null);
      setSecurityContext(null);
      setIsLoading(false);
      return;
    }

    try {
      const currentUser = await apiClient.getCurrentUser();
      setUser(currentUser);
      const nextContext = await hydrateSecurityContext();
      setSecurityContext(nextContext);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        setSecurityContext(null);
      } else {
        throw error;
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (payload: LoginPayload) => {
    const tokenResponse = await apiClient.login(payload);
    setStoredToken(tokenResponse.access_token);
    setIsLoading(true);
    await refreshUser();
  }, [refreshUser]);

  const register = useCallback(async (payload: RegisterPayload) => {
    await apiClient.register(payload);
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    clearPersistedActiveOrganizationId();
    setUser(null);
    setSecurityContext(null);
  }, []);

  const switchOrganization = useCallback(async (organizationId: number) => {
    const nextContext = await switchOrganizationContext(organizationId);
    setSecurityContext(nextContext);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: Boolean(user),
      isLoading,
      user,
      securityContext,
      isOpsAdmin:
        user !== null &&
        (configuredOpsAdmins.length === 0 ||
          configuredOpsAdmins.includes(user.email.trim().toLowerCase())),
      login,
      register,
      logout,
      refreshUser,
      refreshSecurityContext,
      switchOrganization,
    }),
    [configuredOpsAdmins, isLoading, login, logout, refreshSecurityContext, refreshUser, securityContext, switchOrganization, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
