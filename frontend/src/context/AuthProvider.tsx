import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiRequestError, getCSRF, login as loginRequest, pinLogin, logout as logoutRequest, me, type AuthUser } from "@/lib/api";
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

  const loadUser = useCallback(async () => {
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
    loadUser();
  }, [loadUser]);

  const login = useCallback(async ({ identifier, password }: { identifier: string; password: string }) => {
    await getCSRF();
    const payload = identifier.includes("@")
      ? { email: identifier, password }
      : { username: identifier, password };
    await loginRequest(payload);
    const verified = await me();
    setUser(verified);
    return verified;
  }, []);

  const loginWithPin = useCallback(async ({ pin }: { pin: string }) => {
    await getCSRF();
    const pinResponse = await pinLogin({ pin });
    authDebugLog("loginWithPin.pinLogin.ok", {
      user: pinResponse.username,
      role: pinResponse.role,
    });
    try {
      const verified = await me();
      authDebugLog("loginWithPin.me.ok", { user: verified.username, role: verified.role, redirectTo: verified.redirectTo });
      setUser(verified);
      return verified;
    } catch (error) {
      authDebugLog("loginWithPin.me.failed", error instanceof Error ? error.message : String(error));
      if (error instanceof ApiRequestError) {
        throw new ApiRequestError("SESSION_VERIFY_FAILED", {
          code: "SESSION_VERIFY_FAILED",
          status: error.status,
          isNetworkError: error.isNetworkError,
        });
      }
      throw new Error("SESSION_VERIFY_FAILED");
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
