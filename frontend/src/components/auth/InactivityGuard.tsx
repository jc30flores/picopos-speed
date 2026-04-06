import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/useAuth";

const INACTIVITY_MS = 10 * 60 * 1000;
const COUNTDOWN_SECONDS = 60;

export const InactivityGuard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [countdown, setCountdown] = useState<number | null>(null);
  const inactivityTimerRef = useRef<number | null>(null);
  const countdownTimerRef = useRef<number | null>(null);

  const clearTimers = useCallback(() => {
    if (inactivityTimerRef.current) window.clearTimeout(inactivityTimerRef.current);
    if (countdownTimerRef.current) window.clearInterval(countdownTimerRef.current);
    inactivityTimerRef.current = null;
    countdownTimerRef.current = null;
  }, []);

  const forceLogout = useCallback(async () => {
    clearTimers();
    setCountdown(null);
    try {
      await logout();
    } catch {
      // ignore and continue
    }
    localStorage.removeItem("selected_branch_id");
    navigate("/login", { replace: true });
  }, [clearTimers, logout, navigate]);

  const resetInactivityTimer = useCallback(() => {
    if (!user || location.pathname === "/login") return;
    if (countdownTimerRef.current) {
      window.clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
      setCountdown(null);
    }
    if (inactivityTimerRef.current) window.clearTimeout(inactivityTimerRef.current);
    inactivityTimerRef.current = window.setTimeout(() => {
      setCountdown(COUNTDOWN_SECONDS - 1);
      countdownTimerRef.current = window.setInterval(() => {
        setCountdown((prev) => {
          if (prev == null) return COUNTDOWN_SECONDS - 1;
          if (prev <= 1) {
            window.setTimeout(() => void forceLogout(), 0);
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
    const handleUnauthorized = () => {
      void forceLogout();
    };
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, [forceLogout]);

  if (countdown == null || location.pathname === "/login") return null;

  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center bg-black/20">
      <div className="select-none font-mono text-[20vw] font-black leading-none text-emerald-200/35">{countdown}</div>
    </div>,
    document.body
  );
};
