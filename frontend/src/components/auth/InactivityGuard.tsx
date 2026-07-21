import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";

const COUNTDOWN_SECONDS = 60;
const IDLE_TIMEOUT_MS = 10 * 60 * 1000;
const INACTIVITY_MS = IDLE_TIMEOUT_MS - COUNTDOWN_SECONDS * 1000;

export const InactivityGuard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [countdown, setCountdown] = useState<number | null>(null);
  const inactivityTimerRef = useRef<number | null>(null);
  const countdownTimerRef = useRef<number | null>(null);
  const handlingUnauthorizedRef = useRef(false);
  const forceLogoutInFlightRef = useRef(false);

  const clearTimers = useCallback(() => {
    if (inactivityTimerRef.current) window.clearTimeout(inactivityTimerRef.current);
    if (countdownTimerRef.current) window.clearInterval(countdownTimerRef.current);
    inactivityTimerRef.current = null;
    countdownTimerRef.current = null;
  }, []);

  const forceLogout = useCallback(async (message = "Tu sesión se cerró por inactividad.") => {
    if (forceLogoutInFlightRef.current) return;
    forceLogoutInFlightRef.current = true;
    clearTimers();
    setCountdown(null);
    try {
      await logout();
    } catch {
      // ignore and continue
    }
    localStorage.removeItem("selected_branch_id");
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith("auth:"))
      .forEach((key) => sessionStorage.removeItem(key));
    toast.error(message, { id: "auth-session-expired" });
    if (location.pathname !== "/login") {
      navigate("/login", { replace: true });
    }
    forceLogoutInFlightRef.current = false;
  }, [clearTimers, location.pathname, logout, navigate]);

  const resetInactivityTimer = useCallback(() => {
    if (!user || location.pathname === "/login") return;
    if (countdownTimerRef.current) {
      window.clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
      setCountdown(null);
    }
    if (inactivityTimerRef.current) window.clearTimeout(inactivityTimerRef.current);
    inactivityTimerRef.current = window.setTimeout(() => {
      setCountdown(COUNTDOWN_SECONDS);
      countdownTimerRef.current = window.setInterval(() => {
        setCountdown((prev) => {
          if (prev == null) return COUNTDOWN_SECONDS;
          if (prev <= 1) {
            window.setTimeout(() => void forceLogout("Tu sesión se cerró por inactividad."), 0);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }, INACTIVITY_MS);
  }, [forceLogout, location.pathname, user]);

  useEffect(() => {
    if (!user || location.pathname === "/login") {
      clearTimers();
      setCountdown(null);
      return;
    }

    const onActivity = () => resetInactivityTimer();
    const events: Array<keyof WindowEventMap> = ["mousemove", "mousedown", "keydown", "touchstart", "scroll", "click"];
    events.forEach((event) => window.addEventListener(event, onActivity, { passive: true }));
    resetInactivityTimer();

    return () => {
      events.forEach((event) => window.removeEventListener(event, onActivity));
      clearTimers();
    };
  }, [clearTimers, location.pathname, resetInactivityTimer, user]);

  useEffect(() => {
    const handleUnauthorized = (event: Event) => {
      if (location.pathname === "/login") return;
      if (handlingUnauthorizedRef.current) return;
      handlingUnauthorizedRef.current = true;
      const detail = event instanceof CustomEvent ? event.detail : null;
      const message = typeof detail?.message === "string" ? detail.message : "Tu sesión expiró. Ingresa nuevamente.";
      void forceLogout(message);
    };
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    window.addEventListener("auth:session-expired", handleUnauthorized);
    return () => {
      window.removeEventListener("auth:unauthorized", handleUnauthorized);
      window.removeEventListener("auth:session-expired", handleUnauthorized);
    };
  }, [forceLogout, location.pathname, user]);

  useEffect(() => {
    if (!user || location.pathname === "/login") {
      handlingUnauthorizedRef.current = false;
      forceLogoutInFlightRef.current = false;
    }
  }, [location.pathname, user]);

  if (countdown == null || location.pathname === "/login") return null;

  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center bg-black/20">
      <div className="select-none font-mono text-[20vw] font-black leading-none text-emerald-200/35">{countdown}</div>
    </div>,
    document.body
  );
};
