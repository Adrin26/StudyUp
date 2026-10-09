import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { api, onUnauthorized, tokenStore } from "./api";
import type { User } from "@/types";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
export const supabase: SupabaseClient | null = SUPABASE_URL && SUPABASE_KEY ? createClient(SUPABASE_URL, SUPABASE_KEY) : null;

interface AuthState {
  user: User | null;
  loading: boolean;
  usesSupabase: boolean;
  signIn: (email: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const signOut = useCallback(async () => {
    tokenStore.clear();
    setUser(null);
    if (supabase) await supabase.auth.signOut();
  }, []);

  useEffect(() => {
    onUnauthorized(() => {
      tokenStore.clear();
      setUser(null);
    });
    (async () => {
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
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    if (supabase) {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error || !data.session) throw new Error(error?.message ?? "Sign in failed");
      tokenStore.set(data.session.access_token);
      const me = await api.get<User>("/api/auth/me");
      setUser(me);
      return me;
    }
    const res = await api.post<{ access_token: string; user: User }>("/api/auth/demo-login", { email, password });
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const value = useMemo(() => ({ user, loading, usesSupabase: !!supabase, signIn, signOut }), [user, loading, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
