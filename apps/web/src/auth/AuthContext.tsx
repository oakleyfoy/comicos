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
  type RegisterPayload,
  type User,
} from "../api/client";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  isOpsAdmin: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const configuredOpsAdmins = useMemo(
    () =>
      (import.meta.env.VITE_OPS_ADMIN_EMAILS ?? "")
        .split(",")
        .map((value: string) => value.trim().toLowerCase())
        .filter(Boolean),
    [],
  );

  const refreshUser = useCallback(async () => {
    const token = getStoredToken();

    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const currentUser = await apiClient.getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
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
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: Boolean(user),
      isLoading,
      user,
      isOpsAdmin:
        user !== null &&
        (configuredOpsAdmins.length === 0 ||
          configuredOpsAdmins.includes(user.email.trim().toLowerCase())),
      login,
      register,
      logout,
      refreshUser,
    }),
    [configuredOpsAdmins, isLoading, login, logout, refreshUser, user],
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
