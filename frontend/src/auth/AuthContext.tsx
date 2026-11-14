import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, clearTokens, getAccessToken, saveTokens } from "../lib/api";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: {
    username: string;
    email: string;
    password: string;
    is_private: boolean;
  }) => Promise<void>;
  signOut: () => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const acceptSession = useCallback((tokens: {
    access_token: string;
    refresh_token: string;
    user: User;
  }) => {
    saveTokens(tokens.access_token, tokens.refresh_token);
    setUser(tokens.user);
  }, []);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (!getAccessToken()) {
        if (active) setLoading(false);
        return;
      }
      try {
        const currentUser = await api.me();
        if (active) setUser(currentUser);
      } catch {
        clearTokens();
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    acceptSession(await api.login(email, password));
  }, [acceptSession]);

  const signUp = useCallback(async (input: {
    username: string;
    email: string;
    password: string;
    is_private: boolean;
  }) => {
    acceptSession(await api.register({ ...input }));
  }, [acceptSession]);

  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      signIn,
      signUp,
      signOut,
      updateUser: setUser,
    }),
    [user, loading, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
