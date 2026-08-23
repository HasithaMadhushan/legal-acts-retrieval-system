"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LexAtlasMark } from "@/components/auth/lexatlas-mark";
import { Button, buttonVariants } from "@/components/ui/button";
import { me } from "@/lib/api";
import { clearSession, getStoredRole, getToken, navItemsForRole, setSession } from "@/lib/auth";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

function roleLabel(role: Role | null) {
  if (role === "ADMIN") return "Administrator";
  if (role === "LAWYER") return "Attorney-at-Law";
  if (role === "GENERAL_USER") return "General user";
  return "Guest";
}

function initialsFromName(name: string | null, role: Role | null) {
  if (name?.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return `${parts[0]![0] ?? ""}${parts[parts.length - 1]![0] ?? ""}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  }
  if (role === "ADMIN") return "AD";
  if (role === "LAWYER") return "LW";
  if (role === "GENERAL_USER") return "GU";
  return "GT";
}

function isNavActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<Role | null>(null);
  const [fullName, setFullName] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    const token = getToken();
    setHasToken(Boolean(token));
    setRole(getStoredRole());
    if (!token) {
      setFullName(null);
      return;
    }
    me()
      .then((user) => {
        setSession(token, user.role);
        setRole(user.role);
        setFullName(user.full_name);
        setHasToken(true);
      })
      .catch(() => {
        clearSession();
        setRole(null);
        setFullName(null);
        setHasToken(false);
      });
  }, []);

  function logout() {
    clearSession();
    setRole(null);
    setFullName(null);
    setHasToken(false);
    router.push("/login");
  }

  const navItems = navItemsForRole(role).map((item) =>
    item.href === "/dashboard" ? { ...item, label: "Recent" } : item
  );
  const displayName = fullName?.trim() || (hasToken ? "Signed in" : "Guest");
  const initials = initialsFromName(fullName, role);

  return (
    <div className="shell relative flex min-h-screen bg-background">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 h-1 bg-[color:var(--burgundy)]" aria-hidden />

      {navOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[248px] shrink-0 flex-col gap-2 overflow-y-auto bg-sidebar px-[18px] py-7 text-sidebar-foreground transition-transform md:static md:translate-x-0",
          navOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        <LexAtlasMark sidebar className="w-full" />
        <div className="mt-1 h-0.5 w-10 bg-[color:var(--gold)]" aria-hidden />
        <div className="h-2" aria-hidden />
        <nav id="lexatlas-sidebar" className="flex flex-col gap-1" aria-label="Main navigation">
          {navItems.map((item) => {
            const active = isNavActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex h-10 items-center rounded-sm px-4 text-sm no-underline transition-colors",
                  active
                    ? "gap-2.5 bg-[#1a3354] pl-[13px] font-semibold text-[#f4efe4]"
                    : "font-medium text-[#a8b4c2] hover:bg-white/5 hover:text-[#f4efe4]"
                )}
              >
                {active ? (
                  <span className="h-[18px] w-[3px] shrink-0 rounded-[1px] bg-[color:var(--gold)]" aria-hidden />
                ) : null}
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="absolute inset-y-0 right-0 w-[3px] bg-[color:var(--gold)]" aria-hidden />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-[color:var(--surface)] py-3.5 pr-6 pl-4 md:pl-7">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="rounded-sm md:hidden"
            onClick={() => setNavOpen((open) => !open)}
            aria-expanded={navOpen}
            aria-controls="lexatlas-sidebar"
          >
            Menu
          </Button>
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex size-9 items-center justify-center rounded-full border-[1.5px] border-[color:var(--gold)] bg-[#10243a] text-xs font-bold text-[#fcfaf4]">
                {initials}
              </div>
              <div className="flex flex-col gap-px leading-none">
                <span className="text-[13px] font-semibold text-foreground">{displayName}</span>
                <span className="text-[11px] text-muted-foreground">{roleLabel(role)}</span>
              </div>
            </div>
            {hasToken ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-sm border-border bg-[color:var(--surface)] px-3 py-2 text-xs font-semibold text-primary"
                onClick={logout}
              >
                Sign out
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className={cn(
                    buttonVariants({ variant: "outline", size: "sm" }),
                    "rounded-sm text-xs font-semibold"
                  )}
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className={cn(buttonVariants({ size: "sm" }), "rounded-sm text-xs font-semibold")}
                >
                  Register
                </Link>
              </div>
            )}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1180px] flex-1 px-4 py-6 md:px-7">{children}</main>
        <footer className="border-t border-border px-4 py-4 text-xs text-muted-foreground md:px-7">
          <div className="mx-auto flex w-full max-w-[1180px] flex-wrap gap-4">
            <Link href="/legal/terms" className="hover:text-foreground">
              Terms of Use
            </Link>
            <Link href="/legal/privacy" className="hover:text-foreground">
              Privacy Policy
            </Link>
            <span>This system does not provide legal advice.</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
