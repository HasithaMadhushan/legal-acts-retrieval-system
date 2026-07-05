"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { me } from "@/lib/api";
import { clearSession, getStoredRole, getToken, navItemsForRole, setSession } from "@/lib/auth";
import type { Role } from "@/lib/types";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<Role | null>(null);
  const [hasToken, setHasToken] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const token = getToken();
    setHasToken(Boolean(token));
    setRole(getStoredRole());
    if (!token) return;
    me()
      .then((user) => {
        setSession(token, user.role);
        setRole(user.role);
      })
      .catch(() => {
        clearSession();
        setRole(null);
        setHasToken(false);
      });
  }, [pathname]);

  function logout() {
    clearSession();
    setRole(null);
    setHasToken(false);
    router.push("/login");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <p className="brand">Automated Legal Acts Retrieval</p>
        <nav className="nav" aria-label="Main navigation">
          {navItemsForRole(role).map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
          {hasToken ? (
            <button onClick={logout}>Logout</button>
          ) : (
            <>
              <Link href="/login">Login</Link>
              <Link href="/register">Register</Link>
            </>
          )}
        </nav>
      </aside>
      <div className="content">
        <header className="topbar">
          <span>Academic legal information retrieval prototype</span>
          <span className="muted">Role: {role ?? "Guest"}</span>
        </header>
        <main className="main">{children}</main>
      </div>
    </div>
  );
}
