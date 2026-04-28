import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCSRF, login as loginRequest, pinLogin, logout as logoutRequest, me, type AuthUser } from "@/lib/api";
import { AuthContext } from "./authContext";

const AUTH_DEBUG = String(import.meta.env.VITE_AUTH_DEBUG ?? "").toLowerCase() === "true";

const authDebugLog = (...args: unknown[]) => {
  if (!AUTH_DEBUG) return;
  // eslint-disable-next-line no-console
  console.info("[auth-debug]", ...args);
};

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const loginInFlightRef = useRef(false);

  const loadUser = useCallback(async (reason: "bootstrap" | "manual" = "bootstrap") => {
    authDebugLog("AUTH_REFRESH_ME_START", { reason });
    try {
      const current = await me();
      setUser(current);
    } catch (error) {
      authDebugLog("bootstrap.me.failed", error instanceof Error ? error.message : String(error));
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser("bootstrap");
  }, [loadUser]);

  const login = useCallback(async ({ identifier, password }: { identifier: string; password: string }) => {
    if (loginInFlightRef.current) {
      throw new Error("AUTH_LOGIN_IN_FLIGHT");
    }
    loginInFlightRef.current = true;
    authDebugLog("AUTH_LOGIN_REQUEST_START", { method: "password" });
    await getCSRF();
    const payload = identifier.includes("@")
      ? { email: identifier, password }
      : { username: identifier, password };
    try {
      const authenticated = await loginRequest(payload);
      setUser(authenticated);
      authDebugLog("AUTH_LOGIN_SUCCESS", { method: "password", user: authenticated.username });
      return authenticated;
    } finally {
      loginInFlightRef.current = false;
    }
  }, []);

  const loginWithPin = useCallback(async ({ pin }: { pin: string }) => {
    if (loginInFlightRef.current) {
      throw new Error("AUTH_LOGIN_IN_FLIGHT");
    }
    loginInFlightRef.current = true;
    authDebugLog("AUTH_LOGIN_REQUEST_START", { method: "pin" });
    await getCSRF();
    try {
      const authenticated = await pinLogin({ pin });
      authDebugLog("AUTH_LOGIN_SUCCESS", {
        method: "pin",
        user: authenticated.username,
        role: authenticated.role,
      });
      setUser(authenticated);
      return authenticated;
    } finally {
      loginInFlightRef.current = false;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await getCSRF();
      await logoutRequest();
    } catch {
      // Logout must be idempotent on client side to avoid retry loops.
    }
    Object.keys(localStorage)
      .filter((key) => key.startsWith("pos_draft_"))
      .forEach((key) => localStorage.removeItem(key));
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
