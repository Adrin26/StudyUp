import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { api, onSessionEnded, tokenStore } from "./api";
import { queryClient } from "./query";
import type { Role, User } from "@/types";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
export const supabase: SupabaseClient | null = SUPABASE_URL && SUPABASE_KEY ? createClient(SUPABASE_URL, SUPABASE_KEY) : null;

interface AuthConfig {
  mode: "local" | "supabase";
  ai_enabled: boolean;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  usesSupabase: boolean;
  aiEnabled: boolean;
  /** Why the user was signed out (expired session, disabled account); shown on the login page. */
  notice: string | null;
  clearNotice: () => void;
  signIn: (identifier: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
  /** Replace the stored token, e.g. after a password change issues a new one. */
  setToken: (token: string) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function roleHome(role: Role): string {
  return role === "admin" ? "/admin" : role === "teacher" ? "/teacher" : "/";
}

/** Whether a path belongs to this role's area (used to resume after sign-in). */
export function isOwnArea(role: Role, path: string): boolean {
  if (path.startsWith("/profile")) return true;
  const area = (p: string) => path === p || path.startsWith(`${p}/`);
  if (role === "admin") return area("/admin");
  if (role === "teacher") return area("/teacher");
  return !area("/admin") && !area("/teacher");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<AuthConfig>({ mode: supabase ? "supabase" : "local", ai_enabled: false });
  const [notice, setNotice] = useState<string | null>(null);

  const clearSession = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    queryClient.clear();
  }, []);

  const signOut = useCallback(async () => {
    clearSession();
    if (supabase) await supabase.auth.signOut();
  }, [clearSession]);

  useEffect(() => {
    onSessionEnded((error) => {
      clearSession();
      setNotice(error.message);
      if (supabase) void supabase.auth.signOut();
    });
    (async () => {
      api.get<AuthConfig>("/api/auth/config").then(setConfig).catch(() => undefined);
      if (supabase) {
        const { data } = await supabase.auth.getSession();
        if (data.session) tokenStore.set(data.session.access_token);
        supabase.auth.onAuthStateChange((_event, session) => {
          if (session) tokenStore.set(session.access_token);
        });
      }
      if (tokenStore.get()) {
        try {
          setUser(await api.get<User>("/api/auth/me"));
        } catch {
          tokenStore.clear();
        }
      }
      setLoading(false);
    })();
  }, [clearSession]);

  const signIn = useCallback(async (identifier: string, password: string) => {
    setNotice(null);
    if (supabase) {
      const { data, error } = await supabase.auth.signInWithPassword({ email: identifier, password });
      if (error || !data.session) throw new Error(error?.message ?? "Sign in failed");
      tokenStore.set(data.session.access_token);
      const me = await api.get<User>("/api/auth/me");
      setUser(me);
      return me;
    }
    const res = await api.post<{ access_token: string; user: User }>("/api/auth/login", { identifier, password });
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      usesSupabase: !!supabase,
      aiEnabled: config.ai_enabled,
      notice,
      clearNotice: () => setNotice(null),
      signIn,
      signOut,
      setToken: tokenStore.set,
    }),
    [user, loading, config.ai_enabled, notice, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
