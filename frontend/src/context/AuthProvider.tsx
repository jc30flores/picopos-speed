import { useCallback, useEffect, useMemo, useState } from "react";
import { getCSRF, login as loginRequest, pinLogin, logout as logoutRequest, me, type AuthUser } from "@/lib/api";
import { AuthContext } from "./authContext";

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const current = await me();
      setUser(current);
    } catch {
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

  const loginWithPin = useCallback(async ({ pin }: { pin: string }) => {
    await getCSRF();
    const current = await pinLogin({ pin });
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
      loginWithPin,
      logout,
    }),
    [user, loading, login, loginWithPin, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
