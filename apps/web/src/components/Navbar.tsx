"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const { user, loading, signOut } = useAuth();
  const router = useRouter();

  const handleSignOut = async () => {
    await signOut();
    router.replace("/");
  };

  return (
    <nav className={styles.nav}>
      <div className={styles.inner}>
        <Link href="/" className={styles.logo}>
          <span className={styles.logoIcon}>✦</span>
          <span className="gradient-text">ResumeAI</span>
        </Link>

        <div className={styles.actions}>
          {!loading && (
            <>
              {user ? (
                <div className={styles.userArea}>
                  <span className={styles.userEmail}>{user.email}</span>
                  <button
                    id="nav-signout-btn"
                    onClick={handleSignOut}
                    className="btn btn-ghost btn-sm"
                  >
                    Sign out
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
