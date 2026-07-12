"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useAuth } from "@/context/AuthContext";

interface Props {
  id?: string;
  className: string;
  authenticatedLabel?: string;
  guestLabel: string;
  children?: ReactNode;
}

export default function AuthCta({
  id,
  className,
  authenticatedLabel = "Open dashboard",
  guestLabel,
  children,
}: Props) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <span className={className} aria-disabled="true" aria-busy="true">
        <span className="spinner spinner-sm" /> Loading…
      </span>
    );
  }

  const label = user ? authenticatedLabel : guestLabel;
  return (
    <Link href={user ? "/dashboard" : "/login"} id={id} className={className}>
      {label}
      {children}
    </Link>
  );
}
