import { createContext } from "react";
import { AuthUser } from "@/lib/api";

export interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (payload: { identifier: string; password: string }) => Promise<AuthUser>;
  loginWithPin: (payload: { pin: string }) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
