"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { SESSION_CHANGE_EVENT, sessionIdentityKey } from "@/lib/auth";

const AUTH_PREFIXES = ["/login", "/register", "/forgot-password", "/reset-password"];

function useShellSessionKey(pathname: string) {
  const [sessionKey, setSessionKey] = useState("boot");

  useEffect(() => {
    setSessionKey(sessionIdentityKey());
    const sync = () => setSessionKey(sessionIdentityKey());
    window.addEventListener(SESSION_CHANGE_EVENT, sync);
    return () => window.removeEventListener(SESSION_CHANGE_EVENT, sync);
  }, [pathname]);

  return sessionKey;
}

export function AuthAwareShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const sessionKey = useShellSessionKey(pathname);
  const isAuthRoute = AUTH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  if (isAuthRoute) {
    return children;
  }
  return <AppShell key={sessionKey}>{children}</AppShell>;
}
