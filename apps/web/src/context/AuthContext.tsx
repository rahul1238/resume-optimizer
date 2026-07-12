"use client";

import {
  createContext,
  useContext,
  useEffect,
  useCallback,
  useMemo,
  useState,
  ReactNode,
} from "react";
import {
  User,
  onIdTokenChanged,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { getAuthInstance } from "@/lib/firebase";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string | null;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  error: null,
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Remove the legacy client-written cookie used by the deleted Next proxy.
    document.cookie = "auth-token=; path=/; max-age=0; SameSite=Lax";

    const auth = getAuthInstance();
    const unsubscribe = onIdTokenChanged(
      auth,
      (firebaseUser) => {
        setUser(firebaseUser);
        setError(null);
        setLoading(false);
      },
      () => {
        setUser(null);
        setError("Authentication could not be initialized. Refresh and try again.");
        setLoading(false);
      },
    );
    return unsubscribe;
  }, []);

  const signOut = useCallback(async () => {
    await firebaseSignOut(getAuthInstance());
  }, []);

  const value = useMemo(
    () => ({ user, loading, error, signOut }),
    [user, loading, error, signOut],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
