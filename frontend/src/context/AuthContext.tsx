import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { AuthUser, getCSRF, login as loginRequest, logout as logoutRequest, me } from "@/lib/api";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (payload: { identifier: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const current = await me();
      setUser(current);
    } catch (error) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(async ({ identifier, password }: { identifier: string; password: string }) => {
    await getCSRF();
    const payload = identifier.includes("@")
      ? { email: identifier, password }
      : { username: identifier, password };
    const current = await loginRequest(payload);
    setUser(current);
  }, []);

  const logout = useCallback(async () => {
    await getCSRF();
    await logoutRequest();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
    }),
    [user, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
