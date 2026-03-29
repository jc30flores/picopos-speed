import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/context/useAuth";
import { toast } from "sonner";

const PIN_MIN = 4;
const PIN_MAX = 6;

const Login = () => {
  const navigate = useNavigate();
  const { login, loginWithPin } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  const [usePassword, setUsePassword] = useState(false);

  const pinDots = useMemo(() => Array.from({ length: PIN_MAX }), []);

  const submitPin = async (forcedPin?: string) => {
    const value = (forcedPin ?? pin).trim();
    if (value.length < PIN_MIN || value.length > PIN_MAX) {
      toast.error("PIN inválido (4-6 dígitos)");
      return;
    }
    setLoading(true);
    try {
      await loginWithPin({ pin: value });
      toast.success("Sesión iniciada");
      navigate("/");
    } catch {
      toast.error("PIN incorrecto");
      setPin("");
    } finally {
      setLoading(false);
    }
  };

  const onPressDigit = (digit: string) => {
    if (loading || pin.length >= PIN_MAX) return;
    const next = `${pin}${digit}`;
    setPin(next);
    if (next.length === PIN_MAX) {
      void submitPin(next);
    }
  };

  const handlePasswordSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!identifier || !password) {
      toast.error("Completa usuario/correo y contraseña");
      return;
    }
    setLoading(true);
    try {
      await login({ identifier, password });
      toast.success("Sesión iniciada");
      navigate("/");
    } catch {
      toast.error("Credenciales inválidas");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{usePassword ? "Login administrador" : "Ingresa tu PIN"}</CardTitle>
        </CardHeader>
        <CardContent>
          {usePassword ? (
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="identifier">Usuario o correo</Label>
                <Input id="identifier" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Contraseña</Label>
                <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Ingresando..." : "Ingresar"}
              </Button>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="flex justify-center gap-2">
                {pinDots.map((_, idx) => (
                  <span key={idx} className={`h-4 w-4 rounded-full border ${idx < pin.length ? "bg-primary border-primary" : "border-muted-foreground"}`} />
                ))}
              </div>
              <div className="grid grid-cols-3 gap-2">
                {["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "⌫"].map((key) => (
                  <Button
                    key={key}
                    type="button"
                    variant={key === "C" ? "secondary" : "outline"}
                    className="h-14 text-xl"
                    onClick={() => {
                      if (key === "C") setPin("");
                      else if (key === "⌫") setPin((prev) => prev.slice(0, -1));
                      else onPressDigit(key);
                    }}
                    disabled={loading}
                  >
                    {key}
                  </Button>
                ))}
              </div>
              <Button className="w-full h-12" onClick={() => void submitPin()} disabled={loading || pin.length < PIN_MIN}>
                {loading ? "Validando..." : "Ingresar"}
              </Button>
            </div>
          )}
          <button
            type="button"
            className="mt-4 w-full text-sm text-muted-foreground underline"
            onClick={() => setUsePassword((prev) => !prev)}
          >
            {usePassword ? "Usar PIN táctil" : "Usar usuario/contraseña (admin)"}
          </button>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
