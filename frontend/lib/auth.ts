import type { Role } from "./types";

const TOKEN_KEY = "legalActsToken";
const ROLE_KEY = "legalActsRole";
export const SESSION_CHANGE_EVENT = "lexatlas-session-change";

function dispatchSessionChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT));
}

function sessionStore(persistent: boolean) {
  return persistent ? window.localStorage : window.sessionStorage;
}

function isPersistentSession() {
  return Boolean(window.localStorage.getItem(TOKEN_KEY));
}

export function setSession(token: string, role: Role, remember?: boolean) {
  const persistent = remember ?? isPersistentSession();
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(ROLE_KEY);
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(ROLE_KEY);
  const store = sessionStore(persistent);
  store.setItem(TOKEN_KEY, token);
  store.setItem(ROLE_KEY, role);
  dispatchSessionChange();
}

export function clearSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(ROLE_KEY);
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(ROLE_KEY);
  dispatchSessionChange();
}

export function getToken() {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(TOKEN_KEY) ?? window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredRole(): Role | null {
  if (typeof window === "undefined") return null;
  return (
    (window.sessionStorage.getItem(ROLE_KEY) as Role | null) ??
    (window.localStorage.getItem(ROLE_KEY) as Role | null)
  );
}

export function sessionIdentityKey() {
  return `${getToken() ?? ""}:${getStoredRole() ?? ""}`;
}

export function canAccessRoute(pathname: string, role: Role | null) {
  if (pathname.startsWith("/admin")) return role === "ADMIN";
  if (pathname.startsWith("/lawyer")) return role === "ADMIN" || role === "LAWYER";
  return true;
}

export function safeNextPath(nextPath: string | null, fallback: string) {
  if (!nextPath) return fallback;
  if (!nextPath.startsWith("/") || nextPath.startsWith("//")) return fallback;
  if (nextPath.includes("\\") || nextPath.includes("@") || /\s/.test(nextPath)) {
    return fallback;
  }
  try {
    const decoded = decodeURIComponent(nextPath);
    if (
      decoded.startsWith("//") ||
      decoded.includes("\\") ||
      /^[a-z][a-z0-9+.-]*:/i.test(decoded)
    ) {
      return fallback;
    }
  } catch {
    return fallback;
  }
  return nextPath;
}

export function navItemsForRole(role: Role | null) {
  const base = [
    { href: "/", label: "Home" },
    { href: "/browse", label: "Browse Acts" },
    { href: "/search", label: "Search" },
    { href: "/dashboard", label: "Recent" }
  ];
  if (role === "ADMIN") {
    return [
      { href: "/admin/acts", label: "Acts" },
      { href: "/admin/acts/upload", label: "Upload" },
      { href: "/admin/users", label: "Users" },
      { href: "/admin/evaluation", label: "Evaluation" }
    ];
  }
  if (role === "LAWYER") {
    return [
      { href: "/lawyer/search", label: "Search" },
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
