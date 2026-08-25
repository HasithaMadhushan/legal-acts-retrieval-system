"use client";

import Link from "next/link";
import { BookOpen, Clock3, FolderOpen, Home, Network, Search, ShieldCheck, Upload } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LexAtlasMark } from "@/components/auth/lexatlas-mark";
import { GlobalSearch } from "@/components/lexatlas/global-search";
import { Button, buttonVariants } from "@/components/ui/button";
import { me } from "@/lib/api";
import { clearSession, getStoredRole, getToken, navItemsForRole, SESSION_CHANGE_EVENT } from "@/lib/auth";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

function roleStatusLine(role: Role | null) {
  if (role === "ADMIN") return "Admin · verified";
  if (role === "LAWYER") return "Lawyer · verified";
  if (role === "GENERAL_USER") return "General user";
  return "Guest";
}

function signedInAsLabel(role: Role | null) {
  if (role === "ADMIN") return "Signed in as Admin.";
  if (role === "LAWYER") return "Signed in as Lawyer.";
  if (role === "GENERAL_USER") return "Signed in as General user.";
  return "Not signed in.";
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

const navIconByHref = {
  "/": Home,
  "/browse": BookOpen,
  "/search": Search,
  "/dashboard": Clock3,
  "/admin/acts": FolderOpen,
  "/admin/acts/upload": Upload,
  "/admin/users": ShieldCheck,
  "/admin/evaluation": ShieldCheck,
  "/lawyer/search": Search,
  "/lawyer/relationships": Network,
  "/lawyer/workspace": FolderOpen,
};

function navigationGroups(role: Role | null, items: ReturnType<typeof navItemsForRole>) {
  if (role === "ADMIN") {
    return [
      { label: "Corpus", items: items.filter((item) => item.href.startsWith("/admin/acts")) },
      { label: "Governance", items: items.filter((item) => !item.href.startsWith("/admin/acts")) },
    ];
  }
  return [{ label: "Research", items }];
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
    let cancelled = false;

    function applyGuestSession() {
      setHasToken(false);
      setRole(null);
      setFullName(null);
    }

    function syncSession() {
      const token = getToken();
      setHasToken(Boolean(token));
      setRole(getStoredRole());
      if (!token) {
        applyGuestSession();
        return;
      }
      void me()
        .then((user) => {
          if (cancelled) return;
          setRole(user.role);
          setFullName(user.full_name);
          setHasToken(true);
        })
        .catch(() => {
          if (cancelled) return;
          clearSession();
          applyGuestSession();
        });
    }

    syncSession();
    window.addEventListener(SESSION_CHANGE_EVENT, syncSession);
    return () => {
      cancelled = true;
      window.removeEventListener(SESSION_CHANGE_EVENT, syncSession);
    };
  }, [pathname]);

  function logout() {
    clearSession();
    setRole(null);
    setFullName(null);
    setHasToken(false);
    router.push("/login");
  }

  const navItems = navItemsForRole(role);
  const navGroups = navigationGroups(role, navItems);
  const displayName = fullName?.trim() || (hasToken ? "Signed in" : "Guest");
  const initials = initialsFromName(fullName, role);

  return (
    <div className="shell relative flex min-h-screen bg-background">

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
          "fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col overflow-y-auto border-r border-white/7 bg-sidebar text-sidebar-foreground transition-transform md:static md:translate-x-0",
          navOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        <div className="border-b border-white/7 px-5 py-5">
          <LexAtlasMark sidebar className="w-full" />
        </div>
        <nav id="lexatlas-sidebar" className="flex flex-col gap-4 px-2.5 py-4" aria-label="Main navigation">
          {navGroups.map((group) => (
            <div key={group.label}>
              <p className="px-2.5 pb-1.5 pt-2 text-[10px] font-semibold tracking-[0.12em] text-white/35 uppercase">
                {group.label}
              </p>
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const active = isNavActive(pathname, item.href);
                  const Icon = navIconByHref[item.href as keyof typeof navIconByHref] ?? BookOpen;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "relative flex h-9 items-center gap-3 rounded-md px-2.5 text-[13px] no-underline transition-colors",
                        active
                          ? "bg-white/8 font-semibold text-white"
                          : "font-medium text-white/60 hover:bg-white/5 hover:text-white"
                      )}
                    >
                      {active ? (
                        <span className="absolute inset-y-2 -left-2.5 w-0.5 rounded-r bg-[color:var(--gold)]" aria-hidden />
                      ) : null}
                      <Icon className="size-3.5 shrink-0" aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        <div className="mt-auto shrink-0 border-t border-white/7 px-5 py-4 pb-5">
          <p className="leading-relaxed">{signedInAsLabel(role)}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-white/30">
            <Link href="/legal/terms" className="hover:text-white/60">
              Terms
            </Link>
            <span aria-hidden className="text-white/20">
              ·
            </span>
            <Link href="/legal/privacy" className="hover:text-white/60">
              Privacy
            </Link>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-background/95 px-4 backdrop-blur-sm md:px-6">
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
          <div className="hidden md:block">
            <GlobalSearch role={role} />
          </div>
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-[#dcc08a]">
                {initials}
              </div>
              <div className="flex flex-col gap-px leading-none">
                <span className="text-[13px] font-semibold text-foreground">{displayName}</span>
                <span className="text-[11px] text-muted-foreground">{roleStatusLine(role)}</span>
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
        <div className="border-b border-border px-4 py-2 md:hidden">
          <GlobalSearch role={role} />
        </div>
        <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-8 md:px-10 md:py-9">{children}</main>
      </div>
    </div>
  );
}
