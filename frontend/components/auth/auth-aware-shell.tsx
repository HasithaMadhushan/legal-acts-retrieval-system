"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";

const AUTH_PREFIXES = ["/login", "/register", "/forgot-password", "/reset-password"];

export function AuthAwareShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isAuthRoute = AUTH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  if (isAuthRoute) {
    return children;
  }
  return <AppShell>{children}</AppShell>;
}
