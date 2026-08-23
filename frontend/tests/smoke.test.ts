import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { canAccessRoute, containsAdviceIntent, navItemsForRole, safeNextPath } from "../lib/auth";

describe("frontend role and safety smoke checks", () => {
  it("hides admin routes from non-admin roles", () => {
    expect(canAccessRoute("/admin/acts", "GENERAL_USER")).toBe(false);
    expect(canAccessRoute("/admin/acts", "LAWYER")).toBe(false);
    expect(canAccessRoute("/admin/acts", "ADMIN")).toBe(true);
  });

  it("allows lawyer routes for lawyer and admin only", () => {
    expect(canAccessRoute("/lawyer/workspace", "GENERAL_USER")).toBe(false);
    expect(canAccessRoute("/lawyer/workspace", "LAWYER")).toBe(true);
    expect(canAccessRoute("/lawyer/workspace", "ADMIN")).toBe(true);
  });

  it("keeps admin navigation out of general user nav", () => {
    const labels = navItemsForRole("GENERAL_USER").map((item) => item.label);
    expect(labels).not.toContain("Admin Acts");
    expect(labels).not.toContain("Workspace");
    expect(labels).not.toContain("Lawyer Search");
    expect(labels).toContain("Browse Acts");
  });

  it("shows role-aware navigation for lawyer and admin users", () => {
    expect(navItemsForRole("LAWYER").map((item) => item.label)).toContain("Workspace");
    expect(navItemsForRole("ADMIN").map((item) => item.label)).toContain("Users");
    expect(navItemsForRole("ADMIN").map((item) => item.label)).toContain("Evaluation");
  });

  it("detects legal advice intent in the frontend", () => {
    expect(containsAdviceIntent("what should I do in my case")).toBe(true);
  });

  it("rejects open redirects in login next paths", () => {
    expect(safeNextPath("/search", "/dashboard")).toBe("/search");
    expect(safeNextPath("//evil.com", "/dashboard")).toBe("/dashboard");
    expect(safeNextPath("/\\evil.com", "/dashboard")).toBe("/dashboard");
    expect(safeNextPath("https://evil.com", "/dashboard")).toBe("/dashboard");
    expect(safeNextPath(null, "/dashboard")).toBe("/dashboard");
  });

  it("LexAtlas shell uses Brand/Sidebar chrome and maps Dashboard to Recent", () => {
    const shell = readFileSync("components/app-shell.tsx", "utf8");
    const mark = readFileSync("components/auth/lexatlas-mark.tsx", "utf8");
    const layout = readFileSync("app/layout.tsx", "utf8");
    expect(shell).toContain("w-[248px]");
    expect(shell).toContain('label: "Recent"');
    expect(shell).toContain("Sign out");
    expect(shell).toContain("bg-[color:var(--burgundy)]");
    expect(shell).toContain("bg-[color:var(--gold)]");
    expect(shell).toContain("LexAtlasMark sidebar");
    expect(shell).toContain("md:hidden");
    expect(mark).toContain("Statute & citation retrieval");
    expect(mark).toContain("sidebar");
    expect(layout).toContain("LexAtlas — Statute & citation retrieval");
  });

  it("register page exposes account type and attorney verification copy", () => {
    const registerPage = readFileSync("app/register/page.tsx", "utf8");
    const attorneyPage = readFileSync("app/register/attorney-verification/page.tsx", "utf8");
    const layout = readFileSync("app/layout.tsx", "utf8");
    expect(registerPage).toContain("Account type");
    expect(registerPage).toContain("General User");
    expect(registerPage).toContain("Attorney-at-Law");
    expect(registerPage).toContain("Continue to attorney verification");
    expect(registerPage).toContain("Confirm password");
    expect(registerPage).not.toContain("Full name");
    expect(attorneyPage).toContain("Enrollment number");
    expect(attorneyPage).toContain("Proof of enrollment");
    expect(layout).toContain("AuthAwareShell");
  });

  it("login and search pages include expected UI text", () => {
    const loginPage = readFileSync("app/login/page.tsx", "utf8");
    const passwordField = readFileSync("components/auth/password-field.tsx", "utf8");
    const searchPage = readFileSync("app/search/page.tsx", "utf8");
    const lawyerSearchPage = readFileSync("app/lawyer/search/page.tsx", "utf8");
    const searchResults = readFileSync("components/search-results.tsx", "utf8");
    expect(loginPage).toContain("Sign in");
    expect(loginPage).toContain("Keep me signed in");
    expect(loginPage).toContain("Forgot password?");
    expect(loginPage).toContain("Create an account");
    expect(passwordField).toContain("Show password");
    expect(loginPage).not.toContain("AdminPass123!");
    expect(loginPage).not.toContain("LawyerPass123!");
    expect(loginPage).not.toContain("UserPass123!");
    expect(searchPage).toContain("Search");
    expect(searchPage).toContain("search_mode");
    expect(searchPage).toContain("verification_status");
    expect(searchPage).toContain("All methods");
    expect(searchPage).toContain("Verified only");
    expect(searchPage).toContain("No verified results are available");
    expect(lawyerSearchPage).toContain("Processing status");
    expect(lawyerSearchPage).toContain("Verification status");
    expect(lawyerSearchPage).toContain("Previous page");
    expect(lawyerSearchPage).toContain("Next page");
    expect(lawyerSearchPage).toContain("Saved to workspace");
    expect(searchResults).toContain("Search result summary");
    expect(searchResults).toContain("UNRESOLVED");
    expect(searchResults).toContain("Confidence");
    expect(searchResults).toContain("Save to workspace");
    expect(searchResults).toContain("Unsave from workspace");
  });

  it("general user home dashboard and browse pages match LexAtlas Figma flows", () => {
    const homePage = readFileSync("app/page.tsx", "utf8");
    const dashboardPage = readFileSync("app/dashboard/page.tsx", "utf8");
    const browsePage = readFileSync("app/browse/page.tsx", "utf8");
    const actPage = readFileSync("app/acts/[id]/page.tsx", "utf8");
    const sectionPage = readFileSync("app/sections/[id]/page.tsx", "utf8");
    expect(homePage).toContain("Find the statute");
    expect(homePage).toContain("Search Acts");
    expect(homePage).toContain("Recently verified");
    expect(homePage).toContain("listActsBrowse");
    expect(dashboardPage).toContain("Recent reading");
    expect(dashboardPage).toContain("Continue reading");
    expect(dashboardPage).toContain("listReadingHistory");
    expect(browsePage).toContain("Browse Acts");
    expect(browsePage).toContain("Showing");
    expect(browsePage).toContain("Show more Acts");
    expect(actPage).toContain("Overview");
    expect(actPage).toContain("Mapped references");
    expect(sectionPage).toContain("Reference evidence");
    expect(sectionPage).toContain("Mapped references");
  });

  it("admin upload and document list expose upload metadata copy", () => {
    const uploadDropzone = readFileSync("components/upload-dropzone.tsx", "utf8");
    const adminActsPage = readFileSync("app/admin/acts/page.tsx", "utf8");
    expect(uploadDropzone).toContain("PDF only, maximum");
    expect(uploadDropzone).toContain("The selected file is not reported as a PDF");
    expect(uploadDropzone).toContain("Optional title");
    expect(uploadDropzone).toContain("Optional Act number");
    expect(uploadDropzone).toContain("Optional year");
    expect(adminActsPage).toContain("RegistryStatCard");
    expect(adminActsPage).toContain("Verified sections");
    expect(adminActsPage).toContain("Source file");
    expect(adminActsPage).toContain("Uploaded");
  });

  it("admin act detail exposes processing job summary fields", () => {
    const adminActDetailPage = readFileSync("app/admin/acts/[id]/page.tsx", "utf8");
    expect(adminActDetailPage).toContain("Processing job summary");
    expect(adminActDetailPage).toContain("Verification summary");
    expect(adminActDetailPage).toContain("Pending sections");
    expect(adminActDetailPage).toContain("Mapped references");
    expect(adminActDetailPage).toContain("Requested parser");
    expect(adminActDetailPage).toContain("Extracted characters");
    expect(adminActDetailPage).toContain("Warnings");
    expect(adminActDetailPage).toContain("Errors");
  });

  it("admin act detail exposes metadata review controls", () => {
    const adminActDetailPage = readFileSync("app/admin/acts/[id]/page.tsx", "utf8");
    expect(adminActDetailPage).toContain("Metadata review");
    expect(adminActDetailPage).toContain("Save metadata");
    expect(adminActDetailPage).toContain("Metadata warnings");
    expect(adminActDetailPage).toContain("Category / subject area");
  });

  it("admin section review exposes segmentation summary and section metadata", () => {
    const adminSectionsPage = readFileSync("app/admin/acts/[id]/sections/page.tsx", "utf8");
    const sectionViewer = readFileSync("components/section-viewer.tsx", "utf8");
    expect(adminSectionsPage).toContain("Extracted sections");
    expect(adminSectionsPage).toContain("Section status");
    expect(adminSectionsPage).toContain("Section correction");
    expect(adminSectionsPage).toContain("Save section correction");
    expect(adminSectionsPage).toContain("Segmentation warnings");
    expect(adminSectionsPage).toContain("Preview:");
    expect(sectionViewer).toContain("Sort order");
    expect(sectionViewer).toContain("section_type");
  });

  it("admin reference review exposes extraction summary and filters", () => {
    const adminReferencesPage = readFileSync("app/admin/acts/[id]/references/page.tsx", "utf8");
    const referenceTable = readFileSync("components/reference-table.tsx", "utf8");
    expect(adminReferencesPage).toContain("Reference extraction warnings");
    expect(adminReferencesPage).toContain("Mapping warnings");
    expect(adminReferencesPage).toContain("Manual reference creation");
    expect(adminReferencesPage).toContain("Create manual reference");
    expect(adminReferencesPage).toContain("Relationship type");
    expect(adminReferencesPage).toContain("Unresolved mapping");
    expect(adminReferencesPage).toContain("Confidence range");
    expect(adminReferencesPage).toContain("ADDS");
    expect(referenceTable).toContain("Source section");
    expect(referenceTable).toContain("Target path");
    expect(referenceTable).toContain("Mapped target Act ID");
    expect(referenceTable).toContain("Unresolved mapping");
    expect(referenceTable).toContain("Correct reference");
    expect(referenceTable).toContain("Save correction");
    expect(referenceTable).toContain("Link mapping");
    expect(referenceTable).toContain("Clear mapping");
  });

  it("admin evaluation page exposes metrics, mismatches, and safety text", () => {
    const evaluationPage = readFileSync("app/admin/evaluation/page.tsx", "utf8");
    expect(evaluationPage).toContain("Evaluation and demo readiness");
    expect(evaluationPage).toContain("Recall is the primary metric");
    expect(evaluationPage).toContain("MetricsPanel");
    expect(evaluationPage).toContain("Documents");
    expect(evaluationPage).toContain("Processing jobs");
    expect(evaluationPage).toContain("Sections");
    expect(evaluationPage).toContain("References and mappings");
    expect(evaluationPage).toContain("Latest processing warnings and errors");
    expect(evaluationPage).toContain("Gold reference dataset entry");
    expect(evaluationPage).toContain("False positives");
    expect(evaluationPage).toContain("False negatives");
    expect(evaluationPage).toContain("not legal conclusions");
    expect(evaluationPage).not.toContain("LegalDisclaimer");
    expect(evaluationPage).toContain('RoleGuard allowed={["ADMIN"]}');
  });

  it("relationship explorer exposes summaries, filters, and mapped labels", () => {
    const relationshipsPage = readFileSync("app/lawyer/relationships/page.tsx", "utf8");
    const relationshipGraph = readFileSync("components/relationship-graph.tsx", "utf8");
    const actDetailPage = readFileSync("app/acts/[id]/page.tsx", "utf8");
    const sectionDetailPage = readFileSync("app/sections/[id]/page.tsx", "utf8");
    expect(relationshipsPage).toContain("Relationship summary");
    expect(relationshipsPage).toContain("Lookup mode");
    expect(relationshipsPage).toContain("Direction");
    expect(relationshipsPage).toContain("Mapped status");
    expect(relationshipsPage).toContain("Unresolved");
    expect(relationshipsPage).toContain("By verification status");
    expect(relationshipsPage).toContain("No verified relationships are available yet.");
    expect(relationshipsPage).toContain("Save reference");
    expect(relationshipsPage).toContain("Unsave from workspace");
    expect(relationshipGraph).toContain("Mapped Act-to-Act graph edges only");
    expect(relationshipGraph).toContain("Unresolved relationships");
    expect(actDetailPage).toContain("Open relationship explorer");
    expect(sectionDetailPage).toContain("Open relationship explorer");
  });

  it("general Act and section detail pages use Figma tabs and reference panels", () => {
    const actDetailPage = readFileSync("app/acts/[id]/page.tsx", "utf8");
    const sectionDetailPage = readFileSync("app/sections/[id]/page.tsx", "utf8");
    const preview = readFileSync("components/verified-relationship-preview.tsx", "utf8");
    expect(actDetailPage).toContain("Sections");
    expect(actDetailPage).toContain("Mapped references");
    expect(actDetailPage).toContain("OfficialSourceBlock");
    expect(sectionDetailPage).toContain("Mapped references");
    expect(sectionDetailPage).toContain("Reference evidence");
    expect(sectionDetailPage).toContain("Statute text");
    expect(preview).toContain("No verified relationships are available yet.");
    expect(preview).toContain("information retrieval only");
    expect(preview).not.toContain("Correct reference");
    expect(preview).not.toContain("Clear mapping");
  });

  it("redirects expired sessions to login and exposes legal pages", () => {
    const api = readFileSync("lib/api.ts", "utf8");
    const loginPage = readFileSync("app/login/page.tsx", "utf8");
    const shell = readFileSync("components/app-shell.tsx", "utf8");
    const terms = readFileSync("app/legal/terms/page.tsx", "utf8");
    const privacy = readFileSync("app/legal/privacy/page.tsx", "utf8");
    const errorPage = readFileSync("app/error.tsx", "utf8");
    const notFound = readFileSync("app/not-found.tsx", "utf8");
    expect(api).toContain("export class ApiError");
    expect(api).toContain("expired=1");
    expect(loginPage).toContain("Session expired — sign in again");
    expect(shell).toContain("/legal/terms");
    expect(shell).toContain("/legal/privacy");
    expect(terms).toContain("No legal advice");
    expect(privacy).toContain("We do not sell personal data");
    expect(errorPage).toContain("Something went wrong");
    expect(notFound).toContain("Page not found");
  });

  it("lawyer workspace exposes saved item groups, note editing, and exports", () => {
    const workspacePage = readFileSync("app/lawyer/workspace/page.tsx", "utf8");
    const saveButton = readFileSync("components/save-item-button.tsx", "utf8");
    const actDetailPage = readFileSync("app/acts/[id]/page.tsx", "utf8");
    const sectionDetailPage = readFileSync("app/sections/[id]/page.tsx", "utf8");
    expect(workspacePage).toContain("Lawyer workspace");
    expect(workspacePage).toContain("Saved Acts");
    expect(workspacePage).toContain("Workspace filters");
    expect(workspacePage).toContain("Manual save");
    expect(workspacePage).toContain("Export CSV");
    expect(workspacePage).toContain("Export Markdown");
    expect(workspacePage).toContain("Save note");
    expect(workspacePage).toContain("Unsave");
    expect(workspacePage).toContain("does not provide legal advice");
    expect(saveButton).toContain("Unsave from workspace");
    expect(actDetailPage).toContain("Save Act to workspace");
    expect(sectionDetailPage).toContain("Save Section to workspace");
  });
});
