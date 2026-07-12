"use client";

import { useState, FormEvent, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
} from "firebase/auth";
import { getAuthInstance } from "@/lib/firebase";
import { useAuth } from "@/context/AuthContext";
import styles from "./page.module.css";

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "select_account" });

function getFirebaseErrorMessage(code: string): string {
  const map: Record<string, string> = {
    "auth/invalid-email": "Invalid email address.",
    "auth/user-not-found": "No account found with this email.",
    "auth/wrong-password": "Incorrect password.",
    "auth/email-already-in-use": "An account with this email already exists.",
    "auth/weak-password": "Password must be at least 6 characters.",
    "auth/too-many-requests": "Too many attempts. Please try again later.",
    "auth/network-request-failed": "Network error. Check your connection.",
    "auth/popup-blocked":
      "Google sign-in was blocked by the browser. Allow popups for this site and try again.",
    "auth/popup-closed-by-user": "Google sign-in was cancelled.",
    "auth/cancelled-popup-request": "A Google sign-in window is already open.",
    "auth/invalid-credential": "Invalid email or password.",
    "auth/unauthorized-domain":
      "This domain is not authorised. Add 'localhost' under Firebase Console → Authentication → Settings → Authorised domains.",
    "auth/operation-not-allowed":
      "Google sign-in is not enabled. Enable it in Firebase Console → Authentication → Sign-in method → Google.",
    "auth/internal-error":
      "Firebase configuration error. Check Firebase Console → Authentication → Sign-in method.",
  };
  return map[code] ?? `Sign-in failed (${code}). Please try again.`;
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading: authLoading, error: authError } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && user) {
      router.replace("/dashboard");
    }
  }, [authLoading, router, user]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const cred =
        mode === "signin"
          ? await signInWithEmailAndPassword(getAuthInstance(), email, password)
          : await createUserWithEmailAndPassword(getAuthInstance(), email, password);
      await cred.user.getIdToken();
      router.replace("/dashboard");
    } catch (err: unknown) {
      const e = err as { code?: string };
      setError(getFirebaseErrorMessage(e.code ?? ""));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError(null);
    setGoogleLoading(true);
    try {
      const credential = await signInWithPopup(getAuthInstance(), googleProvider);
      await credential.user.getIdToken(true);
      router.replace("/dashboard");
    } catch (err: unknown) {
      const e = err as { code?: string };
      setError(getFirebaseErrorMessage(e.code ?? ""));
    } finally {
      setGoogleLoading(false);
    }
  };

  if (authLoading || user) {
    return (
      <div className={styles.authLoading} role="status" aria-live="polite">
        <div className="spinner spinner-lg" />
        <p>{user ? "Opening your dashboard…" : "Restoring your session…"}</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      {/* Background glow */}
      <div className={styles.bg} aria-hidden />

      {/* Logo */}
      <Link href="/" className={styles.logo}>
        <span className={styles.logoIcon}>✦</span>
        <span className="gradient-text">ResumeAI</span>
      </Link>

      <div className={`glass-card ${styles.card} animate-slide-up`}>
        {/* Tabs */}
        <div className={styles.tabs}>
          <button
            id="tab-signin"
            className={`${styles.tab} ${mode === "signin" ? styles.tabActive : ""}`}
            onClick={() => { setMode("signin"); setError(null); }}
          >
            Sign in
          </button>
          <button
            id="tab-signup"
            className={`${styles.tab} ${mode === "signup" ? styles.tabActive : ""}`}
            onClick={() => { setMode("signup"); setError(null); }}
          >
            Create account
          </button>
        </div>

        <div className={styles.body}>
          <h1 className={styles.title}>
            {mode === "signin" ? "Welcome back" : "Create your account"}
          </h1>
          <p className={styles.subtitle}>
            {mode === "signin"
              ? "Sign in to access your resume dashboard."
              : "Start optimizing your resume for free."}
          </p>

          {/* Google */}
          <button
            id="google-signin-btn"
            type="button"
            className={`btn btn-google ${styles.googleBtn}`}
            onClick={handleGoogle}
            disabled={loading || googleLoading}
          >
            {googleLoading ? (
              <><div className="spinner spinner-sm" /> Signing in…</>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Continue with Google
              </>
            )}
          </button>

          <div className="divider">or</div>

          {/* Error */}
          {(error || authError) && (
            <div className="alert alert-error animate-fade-in" role="alert">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error || authError}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className={styles.form} noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                className="form-input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                disabled={loading}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                className="form-input"
                placeholder={mode === "signup" ? "At least 6 characters" : "••••••••"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                disabled={loading}
              />
            </div>
            <button
              id="auth-submit-btn"
              type="submit"
              className={`btn btn-primary ${styles.submitBtn}`}
              disabled={loading || !email || !password}
            >
              {loading ? (
                <><div className="spinner spinner-sm" /> Processing…</>
              ) : mode === "signin" ? (
                "Sign in →"
              ) : (
                "Create account →"
              )}
            </button>
          </form>
        </div>
      </div>

      <p className={styles.legal}>
        By continuing, you agree to our{" "}
        <span style={{ color: "var(--color-text-muted)" }}>Terms of Service</span>{" "}
        and{" "}
        <span style={{ color: "var(--color-text-muted)" }}>Privacy Policy</span>.
      </p>
    </div>
  );
}
