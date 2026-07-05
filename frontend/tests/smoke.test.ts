import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { canAccessRoute, containsAdviceIntent, navItemsForRole } from "../lib/auth";

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

  it("login and search pages include expected UI text", () => {
    const loginPage = readFileSync("app/login/page.tsx", "utf8");
    const searchPage = readFileSync("app/search/page.tsx", "utf8");
    const lawyerSearchPage = readFileSync("app/lawyer/search/page.tsx", "utf8");
    const searchResults = readFileSync("components/search-results.tsx", "utf8");
    expect(loginPage).toContain("Sign in");
    expect(loginPage).toContain("AdminPass123!");
    expect(searchPage).toContain("Search verified legal information");
    expect(searchPage).toContain("Category");
    expect(searchPage).toContain("Relationship type");
    expect(searchPage).not.toContain("Mapped status");
    expect(searchPage).toContain("No verified results are available");
    expect(searchPage).toContain("reviewed mapped relationships");
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

  it("general user home dashboard and browse pages are simplified and verified-only", () => {
    const homePage = readFileSync("app/page.tsx", "utf8");
    const dashboardPage = readFileSync("app/dashboard/page.tsx", "utf8");
    const browsePage = readFileSync("app/browse/page.tsx", "utf8");
    expect(homePage).toContain("Browse Acts");
    expect(homePage).toContain("Verified information retrieval");
    expect(homePage).toContain("does not explain legal meaning");
    expect(dashboardPage).toContain("General Users can search and browse verified legal information only");
    expect(dashboardPage).toContain("Search verified information");
    expect(dashboardPage).toContain("Browse Acts");
    expect(browsePage).toContain("Browse verified Acts");
    expect(browsePage).toContain("General Users see verified information");
    expect(browsePage).toContain("No verified Acts are available");
    expect(browsePage).toContain("LegalDisclaimer");
    expect(browsePage).not.toContain("Upload");
    expect(browsePage).not.toContain("Workspace");
  });

  it("admin upload and document list expose upload metadata copy", () => {
    const uploadDropzone = readFileSync("components/upload-dropzone.tsx", "utf8");
    const adminActsPage = readFileSync("app/admin/acts/page.tsx", "utf8");
    expect(uploadDropzone).toContain("PDF only, maximum");
    expect(uploadDropzone).toContain("The selected file is not reported as a PDF");
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
    expect(evaluationPage).toContain("LegalDisclaimer");
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

  it("general Act and section detail pages use verified relationship previews", () => {
    const actDetailPage = readFileSync("app/acts/[id]/page.tsx", "utf8");
    const sectionDetailPage = readFileSync("app/sections/[id]/page.tsx", "utf8");
    const preview = readFileSync("components/verified-relationship-preview.tsx", "utf8");
    expect(actDetailPage).toContain("Verified sections");
    expect(actDetailPage).toContain("Verified relationship preview");
    expect(sectionDetailPage).toContain("Verified references from this section");
    expect(preview).toContain("No verified relationships are available yet.");
    expect(preview).toContain("information retrieval only");
    expect(preview).not.toContain("Correct reference");
    expect(preview).not.toContain("Clear mapping");
  });

  it("lawyer workspace exposes saved item groups, note editing, exports, and disclaimer", () => {
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
