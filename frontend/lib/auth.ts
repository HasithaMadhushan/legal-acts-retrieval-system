import type { Role } from "./types";

const TOKEN_KEY = "legalActsToken";
const ROLE_KEY = "legalActsRole";

export function setSession(token: string, role: Role) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredRole(): Role | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ROLE_KEY) as Role | null;
}

export function canAccessRoute(pathname: string, role: Role | null) {
  if (pathname.startsWith("/admin")) return role === "ADMIN";
  if (pathname.startsWith("/lawyer")) return role === "ADMIN" || role === "LAWYER";
  return true;
}

export function navItemsForRole(role: Role | null) {
  const base = [
    { href: "/", label: "Home" },
    { href: "/browse", label: "Browse Acts" },
    { href: "/search", label: "Search" },
    { href: "/dashboard", label: "Dashboard" }
  ];
  if (role === "ADMIN") {
    return [
      ...base,
      { href: "/admin/acts", label: "Admin Acts" },
      { href: "/admin/users", label: "Users" },
      { href: "/admin/evaluation", label: "Evaluation" },
      { href: "/lawyer/search", label: "Lawyer Search" },
      { href: "/lawyer/relationships", label: "Relationships" },
      { href: "/lawyer/workspace", label: "Workspace" }
    ];
  }
  if (role === "LAWYER") {
    return [
      ...base,
      { href: "/lawyer/search", label: "Lawyer Search" },
      { href: "/lawyer/relationships", label: "Relationships" },
      { href: "/lawyer/workspace", label: "Workspace" }
    ];
  }
  return base;
}

export function containsAdviceIntent(value: string) {
  return /what should i do|should i sue|can i sue|am i liable|my case|my situation|legal advice|legal opinion/i.test(
    value
  );
}
