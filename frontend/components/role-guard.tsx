"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { me } from "@/lib/api";
import { canAccessRoute, clearSession, getStoredRole, getToken } from "@/lib/auth";
import type { Role } from "@/lib/types";

export function RoleGuard({
  allowed,
  path,
  children
}: {
  allowed: Role[];
  path: string;
  children: React.ReactNode;
}) {
  const [role, setRole] = useState<Role | null>(null);
  const [checking, setChecking] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    const token = getToken();
    if (!token) {
      setRole(null);
      setChecking(false);
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    setRole(getStoredRole());
    me()
      .then((user) => {
        if (cancelled) return;
        setRole(user.role);
      })
      .catch(() => {
        if (cancelled) return;
        clearSession();
        setRole(null);
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (checking) {
    return (
      <div className="panel">
        <p>Checking session...</p>
      </div>
    );
  }

  if (!role) {
    return (
      <div className="panel">
        <p>You must log in to access this page.</p>
        <Link className="button" href="/login">
          Login
        </Link>
      </div>
    );
  }

  if (!allowed.includes(role) || !canAccessRoute(path, role)) {
    return (
      <div className="panel">
        <h1>Access restricted</h1>
        <p>This page is limited by role-based permissions.</p>
      </div>
    );
  }

  return <>{children}</>;
}
