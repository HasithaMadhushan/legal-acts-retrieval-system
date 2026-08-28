import { clearSession, getToken } from "@/lib/auth";
import type {
  ActReviewQueueItem,
  LegalAct,
  LegalReference,
  EvaluationMetricsSummary,
  EvaluationRun,
  EvaluationRunCreatePayload,
  GoldReference,
  GoldReferenceCreatePayload,
  MappingRemapResult,
  ProcessingJob,
  ReferenceCreatePayload,
  RelationshipGraphResponse,
  RelationshipListResponse,
  Role,
  SavedItem,
  SavedItemCreatePayload,
  SavedItemListResponse,
  SearchResponse,
  Section,
  ReadingHistoryItem,
  LegalActBrowse,
  User,
  VerificationSummary
} from "@/lib/types";

function defaultApiBase() {
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
  }
  return "http://127.0.0.1:8000/api/v1";
}

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? defaultApiBase()).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function searchErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 400) {
    return "Semantic search is not enabled yet. Use Keyword or All methods.";
  }
  if (err instanceof ApiError && err.status === 503) {
    return "Semantic search is enabled but not ready. Use Keyword or All methods.";
  }
  if (err instanceof ApiError && err.status === 401) {
    return "Session expired — sign in again";
  }
  return err instanceof Error ? err.message : "Search failed. Login may be required.";
}

const ME_TTL_MS = 5 * 60 * 1000;
let meCache: { at: number; user: User & { disclaimer: string } } | null = null;

export function clearMeCache() {
  meCache = null;
}

const AUTH_PAGE_PREFIXES = ["/login", "/register", "/forgot-password", "/reset-password"];

export function redirectIfUnauthorized(status: number, apiPath: string) {
  if (status !== 401 || typeof window === "undefined") return;
  if (apiPath.startsWith("/auth/login") || apiPath.startsWith("/auth/register")) return;
  clearSession();
  clearMeCache();
  if (apiPath.startsWith("/auth/me")) return;
  const path = window.location.pathname;
  if (AUTH_PAGE_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))) return;
  const next = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`/login?next=${encodeURIComponent(next)}&expired=1`);
}


export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const bodyIsFormData = options.body instanceof FormData;
  if (options.body && !bodyIsFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const data = await response.json();
      if (Array.isArray(data.detail)) {
        detail = data.detail
          .map((item: { msg?: string } | string) => (typeof item === "string" ? item : item.msg ?? ""))
          .filter(Boolean)
          .join(" ");
      } else {
        detail = data.detail ?? detail;
      }
    } catch {
      // Keep fallback detail.
    }
    const error = new ApiError(response.status, detail);
    redirectIfUnauthorized(response.status, path);
    throw error;
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return (await response.text()) as T;
  return response.json() as Promise<T>;
}

export async function login(email: string, password: string, rememberMe = false) {
  return apiFetch<{ access_token: string; role: Role; disclaimer: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, remember_me: rememberMe })
  });
}

export async function register(payload: {
  email: string;
  password: string;
  full_name?: string;
}) {
  return apiFetch<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function submitLawyerVerification(formData: FormData) {
  return apiFetch<User>("/auth/lawyer-verification", { method: "POST", body: formData });
}

export async function forgotPassword(email: string) {
  return apiFetch<{ detail: string }>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email })
  });
}

export async function resetPassword(token: string, password: string) {
  return apiFetch<{ detail: string }>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password })
  });
}

export async function approveLawyerRequest(userId: string) {
  return apiFetch<User>(`/users/${userId}/lawyer-requests/approve`, { method: "POST" });
}

export async function rejectLawyerRequest(userId: string) {
  return apiFetch<User>(`/users/${userId}/lawyer-requests/reject`, { method: "POST" });
}

export async function me() {
  if (meCache && Date.now() - meCache.at < ME_TTL_MS) return meCache.user;
  const user = await apiFetch<User & { disclaimer: string }>("/auth/me");
  meCache = { at: Date.now(), user };
  return user;
}

export async function listActs() {
  return apiFetch<LegalAct[]>("/acts");
}

export async function listActsBrowse() {
  return apiFetch<LegalActBrowse[]>("/acts/browse");
}

export async function listReadingHistory(limit = 20) {
  return apiFetch<{ items: ReadingHistoryItem[]; total_results: number }>(
    `/reading-history?limit=${limit}`
  );
}

export async function recordReadingHistory(payload: {
  item_type: "ACT" | "SECTION";
  act_id: string;
  section_id?: string | null;
}) {
  return apiFetch<ReadingHistoryItem>("/reading-history", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getAct(id: string) {
  return apiFetch<LegalAct & { raw_text?: string | null }>(`/acts/${id}`);
}

export async function updateAct(id: string, payload: Partial<LegalAct>) {
  return apiFetch<LegalAct>(`/acts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deleteAct(id: string) {
  return apiFetch<{ detail: string }>(`/acts/${id}`, { method: "DELETE" });
}

export async function uploadAct(formData: FormData) {
  return apiFetch<LegalAct>("/acts/upload", { method: "POST", body: formData });
}

export async function processAct(id: string) {
  return apiFetch<ProcessingJob>(`/acts/${id}/process`, { method: "POST" });
}

export async function remapActReferences(id: string) {
  return apiFetch<MappingRemapResult>(`/acts/${id}/remap-references`, { method: "POST" });
}

export async function listReferenceReviewQueue() {
  return apiFetch<ActReviewQueueItem[]>("/acts/review-queue");
}

export async function listProcessingJobs(id: string) {
  return apiFetch<ProcessingJob[]>(`/acts/${id}/processing-jobs`);
}

export async function getVerificationSummary(id: string) {
  return apiFetch<VerificationSummary>(`/acts/${id}/verification-summary`);
}

export async function listSections(actId: string) {
  return apiFetch<Section[]>(`/acts/${actId}/sections`);
}

export async function getSection(id: string) {
  return apiFetch<Section>(`/sections/${id}`);
}

export async function updateSection(id: string, payload: Partial<Section>) {
  return apiFetch<Section>(`/sections/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function verifySection(id: string) {
  return apiFetch<Section>(`/sections/${id}/verify`, { method: "POST" });
}

export async function rejectSection(id: string) {
  return apiFetch<Section>(`/sections/${id}/reject`, { method: "POST" });
}

export async function listActReferences(actId: string, includePending = false) {
  return apiFetch<LegalReference[]>(`/acts/${actId}/references?include_pending=${includePending}`);
}

export async function listSectionReferences(sectionId: string, includePending = false) {
  return apiFetch<LegalReference[]>(`/sections/${sectionId}/references?include_pending=${includePending}`);
}

export async function verifyReference(id: string) {
  return apiFetch<LegalReference>(`/references/${id}/verify`, { method: "POST" });
}

export async function rejectReference(id: string) {
  return apiFetch<LegalReference>(`/references/${id}/reject`, { method: "POST" });
}

export async function updateReference(id: string, payload: Partial<LegalReference>) {
  return apiFetch<LegalReference>(`/references/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function createReference(payload: ReferenceCreatePayload) {
  return apiFetch<LegalReference>("/references", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function linkReferenceTarget(
  id: string,
  payload: { target_act_id: string | null; target_section_id: string | null; notes?: string | null }
) {
  return apiFetch<LegalReference>(`/references/${id}/link-target`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function listSavedItems(params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(params);
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiFetch<SavedItemListResponse>(`/saved-items${suffix}`);
}

export async function createSavedItem(payload: SavedItemCreatePayload) {
  return apiFetch<SavedItem>("/saved-items", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateSavedItem(id: string, payload: { note: string | null }) {
  return apiFetch<SavedItem>(`/saved-items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deleteSavedItem(id: string) {
  return apiFetch<{ detail: string }>(`/saved-items/${id}`, { method: "DELETE" });
}

export async function search(q: string, params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams({ q, ...params });
  return apiFetch<SearchResponse>(`/search?${searchParams.toString()}`);
}

export async function getActRelationships(id: string, params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(params);
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiFetch<RelationshipListResponse>(`/relationships/act/${id}${suffix}`);
}

export async function getSectionRelationships(id: string, params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(params);
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiFetch<RelationshipListResponse>(`/relationships/section/${id}${suffix}`);
}

export async function getRelationshipGraph(params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(params);
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return apiFetch<RelationshipGraphResponse>(`/relationships/graph${suffix}`);
}

export async function getEvaluationMetricsSummary() {
  return apiFetch<EvaluationMetricsSummary>("/evaluation/metrics-summary");
}

export async function listGoldReferences() {
  return apiFetch<GoldReference[]>("/evaluation/gold-references");
}

export async function createGoldReference(payload: GoldReferenceCreatePayload) {
  return apiFetch<GoldReference>("/evaluation/gold-references", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function runEvaluation(payload: EvaluationRunCreatePayload) {
  return apiFetch<EvaluationRun>("/evaluation/run", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function listEvaluationRuns() {
  return apiFetch<EvaluationRun[]>("/evaluation/runs");
}

export async function listUsers() {
  return apiFetch<User[]>("/users");
}

export async function updateUser(
  id: string,
  payload: Partial<Pick<User, "role" | "is_active" | "full_name">>
) {
  return apiFetch<User>(`/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deactivateUser(id: string) {
  return apiFetch<User>(`/users/${id}`, { method: "DELETE" });
}

export function exportUrl(path: string) {
  return `${API_BASE}${path}`;
}
