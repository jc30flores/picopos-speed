import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";
import { PinKeypad } from "@/components/auth/PinKeypad";
import { ClockSV } from "@/components/ClockSV";
import { getLandingRouteForRole } from "@/lib/roleAccess";
import { isApiStatusError, isNetworkApiError } from "@/lib/api";
import { APP_DISPLAY_NAME } from "@/lib/branding";
import { InstallAppButton } from "@/components/pwa/InstallAppButton";

const PIN_LENGTH = 6;
const AUTH_DEBUG = String(import.meta.env.VITE_AUTH_DEBUG ?? "").toLowerCase() === "true";

const Login = () => {
  const navigate = useNavigate();
  const { login, loginWithPin } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  const [usePassword, setUsePassword] = useState(false);
  const loginInFlightRef = useRef(false);
  const pinRef = useRef("");
  const lastSubmittedPinRef = useRef<string | null>(null);

  const pinDots = useMemo(() => Array.from({ length: PIN_LENGTH }), []);

  const sanitizePin = (value: string) => value.replace(/\D/g, "").slice(0, PIN_LENGTH);

  const clearPinState = useCallback(() => {
    pinRef.current = "";
    setPin("");
  }, []);

  const submitPin = useCallback(async (forcedPin: string, source: "auto" | "enter" | "button") => {
    const value = sanitizePin(forcedPin.trim());
    if (value.length !== PIN_LENGTH) {
      if (AUTH_DEBUG) console.info("AUTH_LOGIN_SUBMIT_SKIPPED", { source, reason: "incomplete_pin", length: value.length });
      return;
    }
    if (loginInFlightRef.current) {
      if (AUTH_DEBUG) console.info("AUTH_LOGIN_SUBMIT_SKIPPED", { source, reason: "in_flight" });
      return;
    }
    if (lastSubmittedPinRef.current === value) {
      if (AUTH_DEBUG) console.info("AUTH_LOGIN_SUBMIT_SKIPPED", { source, reason: "already_submitted" });
      return;
    }
    if (AUTH_DEBUG) {
      console.info("AUTH_LOGIN_SUBMIT", { method: "pin", source });
    }
    loginInFlightRef.current = true;
    lastSubmittedPinRef.current = value;
    setLoading(true);
    try {
      const session = await loginWithPin({ pin: value });
      toast.success("Sesión iniciada", { id: "login-success" });
      if (AUTH_DEBUG) {
        console.info("AUTH_LOGIN_SUCCESS", { source });
        console.info("AUTH_LOGIN_NAVIGATE", session.redirectTo || getLandingRouteForRole(session.role, session.isSuperuser));
      }
      navigate(session.redirectTo || getLandingRouteForRole(session.role, session.isSuperuser), { replace: true });
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (AUTH_DEBUG) console.info("AUTH_LOGIN_FAILED", { source, message: message || "unknown" });
      if (message.includes("PIN_DUPLICATE") || message.includes("duplicado")) {
        toast.error("PIN duplicado, contacte al administrador");
      } else if (message.includes("PIN_INVALID")) {
        toast.error("PIN incorrecto");
      } else if (message.includes("PIN_THROTTLED")) {
        toast.error("Demasiados intentos, espera 30 segundos");
      } else if (isApiStatusError(error, [401])) {
        toast.error("PIN incorrecto.");
      } else if (isApiStatusError(error, [403])) {
        toast.error("Error de sesión/seguridad. Recarga e intenta de nuevo.");
      } else if (isNetworkApiError(error) || message.includes("NETWORK_ERROR")) {
        toast.error("Error de conexión. Reintenta.");
      } else if (message.includes("PIN_FORBIDDEN") || message.includes("csrf")) {
        toast.error("Error de sesión/seguridad. Recarga e intenta de nuevo.");
      } else {
        toast.error(message || "No se pudo iniciar sesión.");
      }
      lastSubmittedPinRef.current = null;
      clearPinState();
    } finally {
      loginInFlightRef.current = false;
      setLoading(false);
    }
  }, [clearPinState, loginWithPin, navigate]);

  const setAndMaybeSubmitPin = useCallback((nextValue: string) => {
    if (loginInFlightRef.current) return;
    const nextPin = sanitizePin(nextValue);
    pinRef.current = nextPin;
    setPin(nextPin);
    if (nextPin.length < PIN_LENGTH) {
      lastSubmittedPinRef.current = null;
    }
    if (AUTH_DEBUG) console.info("AUTH_PIN_DIGIT", { length: nextPin.length });
    if (nextPin.length === PIN_LENGTH) {
      if (AUTH_DEBUG) console.info("AUTH_PIN_AUTOSUBMIT", { source: "auto", length: nextPin.length });
      void submitPin(nextPin, "auto");
    }
  }, [submitPin]);

  useEffect(() => {
    if (usePassword) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Enter") {
        event.preventDefault();
        if (pinRef.current.length === PIN_LENGTH) {
          void submitPin(pinRef.current, "enter");
        }
        return;
      }
      if (loginInFlightRef.current) return;
      if (event.key >= "0" && event.key <= "9") {
        event.preventDefault();
        setAndMaybeSubmitPin(`${pinRef.current}${event.key}`);
        return;
      }
      if (event.key === "Backspace" || event.key === "Delete") {
        event.preventDefault();
        setAndMaybeSubmitPin(pinRef.current.slice(0, -1));
        return;
      }
      if (event.key === "Escape" || event.key.toLowerCase() === "c") {
        event.preventDefault();
        setAndMaybeSubmitPin("");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [setAndMaybeSubmitPin, submitPin, usePassword]);

  const handlePasswordSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loginInFlightRef.current) return;
    if (AUTH_DEBUG) {
      // eslint-disable-next-line no-console
      console.info("AUTH_LOGIN_SUBMIT", { method: "password" });
    }
    if (!identifier || !password) {
      toast.error("Completa usuario/correo y PIN");
      return;
    }
    const numericPassword = sanitizePin(password);
    if (!/^\d{6}$/.test(numericPassword)) {
      toast.error("El PIN debe tener exactamente 6 dígitos");
      return;
    }

    loginInFlightRef.current = true;
    setLoading(true);
    try {
      const session = await login({ identifier, password: numericPassword });
      toast.success("Sesión iniciada", { id: "login-success" });
      if (AUTH_DEBUG) {
        // eslint-disable-next-line no-console
        console.info("AUTH_LOGIN_NAVIGATE", session.redirectTo || getLandingRouteForRole(session.role, session.isSuperuser));
      }
      navigate(session.redirectTo || getLandingRouteForRole(session.role, session.isSuperuser), { replace: true });
    } catch {
      toast.error("Credenciales inválidas");
    } finally {
      loginInFlightRef.current = false;
      setLoading(false);
    }
  };
  const handlePinSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void submitPin(pinRef.current, "enter");
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-md space-y-4">
      <ClockSV className="mx-auto w-full max-w-sm bg-background/50" timeClassName="text-4xl sm:text-5xl" />
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary">{APP_DISPLAY_NAME}</p>
          <CardTitle>{usePassword ? "Login administrador" : "Ingresa tu PIN"}</CardTitle>
        </CardHeader>
        <CardContent>
          {usePassword ? (
            <form onSubmit={handlePasswordSubmit} className="space-y-4" noValidate>
              <div className="space-y-2">
                <Label htmlFor="identifier">Usuario o correo</Label>
                <Input id="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">PIN (6 dígitos)</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  inputMode="numeric"
                  maxLength={PIN_LENGTH}
                  onChange={(e) => setPassword(sanitizePin(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">Si tu contraseña anterior no era numérica, actualízala a un PIN de 6 dígitos.</p>
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Ingresando..." : "Ingresar"}
              </Button>
            </form>
          ) : (
            <form onSubmit={handlePinSubmit} className="space-y-4" noValidate>
              <div className="flex justify-center gap-2">
                {pinDots.map((_, idx) => (
                  <span key={idx} className={`h-4 w-4 rounded-full border ${idx < pin.length ? "bg-primary border-primary" : "border-muted-foreground"}`} />
                ))}
              </div>
              <PinKeypad value={pin} onChange={setAndMaybeSubmitPin} disabled={loading} maxLength={PIN_LENGTH} />
              <Button
                type="button"
                className="w-full h-14 text-base"
                onClick={() => void submitPin(pinRef.current, "button")}
                disabled={loading || pin.length !== PIN_LENGTH}
              >
                {loading ? "Validando..." : "Ingresar"}
              </Button>
            </form>
          )}
          <button
            type="button"
            className="mt-4 w-full text-sm text-muted-foreground underline"
            onClick={() => setUsePassword((prev) => !prev)}
          >
            {usePassword ? "Usar PIN táctil" : "Usar usuario/contraseña (admin)"}
          </button>
          <InstallAppButton className="mt-3 w-full" />
        </CardContent>
      </Card>
      </div>
    </div>
  );
};

export default Login;
