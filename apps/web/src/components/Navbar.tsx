"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
import { FileText, LayoutDashboard, LogOut } from "lucide-react";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const { user, loading, signOut } = useAuth();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await signOut();
      router.replace("/login");
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <nav className={styles.nav}>
      <div className={styles.inner}>
        <Link href={user ? "/dashboard" : "/"} className={styles.logo}>
          <span className={styles.logoIcon}><FileText size={17} /></span>
          <span>ResumeAI</span>
        </Link>

        <div className={styles.actions}>
          {!loading && (
            <>
              {user ? (
                <div className={styles.userArea}>
                  <Link href="/dashboard" className="btn btn-ghost btn-sm">
                    <LayoutDashboard size={14} />
                    Dashboard
                  </Link>
                  <span className={styles.userEmail}>{user.email}</span>
                  <button
                    id="nav-signout-btn"
                    onClick={handleSignOut}
                    className="btn btn-ghost btn-sm"
                    disabled={signingOut}
                  >
                    <LogOut size={14} />
                    {signingOut ? "Signing out…" : "Sign out"}
                  </button>
                </div>
              ) : (
                <Link href="/login" className="btn btn-primary btn-sm">
                  Get started
                </Link>
              )}
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
