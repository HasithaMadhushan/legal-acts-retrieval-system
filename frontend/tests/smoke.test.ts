import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { canAccessRoute, containsAdviceIntent, navItemsForRole, safeNextPath } from "../lib/auth";
import { displayActTitle, isPlaceholderActTitle } from "../lib/act-display";

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
    expect(shell).toContain("w-64");
    expect(shell).toContain("GlobalSearch");
    expect(shell).toContain("Sign out");
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
    expect(lawyerSearchPage).toContain('label="Status"');
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
    expect(browsePage).toContain("All verified Acts");
    expect(browsePage).toContain("All categories");
    expect(browsePage).toContain("Next →");
    expect(actPage).toContain("Overview");
    expect(actPage).toContain("Mapped references");
    expect(sectionPage).toContain("Reference evidence");
    expect(sectionPage).toContain("References involving this section");
  });

  it("admin upload and document list expose upload metadata copy", () => {
    const uploadDropzone = readFileSync("components/upload-dropzone.tsx", "utf8");
    const adminActsPage = readFileSync("app/admin/acts/page.tsx", "utf8");
    expect(uploadDropzone).toContain("PDF only · max");
    expect(uploadDropzone).toContain("The selected file is not reported as a PDF");
    expect(uploadDropzone).toContain("Title override");
    expect(uploadDropzone).toContain("Optional Act number");
    expect(uploadDropzone).toContain("Optional year");
    expect(adminActsPage).toContain("All statuses");
    expect(adminActsPage).toContain("Processing");
    expect(adminActsPage).toContain("Uploaded");
    expect(adminActsPage).toContain("verified");
    expect(adminActsPage).toContain("processing");
    expect(adminActsPage).toContain("Reference review queue");
    expect(adminActsPage).toContain("Review citations");
  });

  it("admin act detail exposes processing job summary fields", () => {
    const adminActDetailPage = readFileSync("app/admin/acts/[id]/page.tsx", "utf8");
    expect(adminActDetailPage).toContain("Processing job summary");
    expect(adminActDetailPage).toContain("Verification summary");
    expect(adminActDetailPage).toContain("Pending sections");
    expect(adminActDetailPage).toContain("Mapped references");
    expect(adminActDetailPage).toContain("Remap unverified");
    expect(adminActDetailPage).toContain("Open needs-review queue");
    expect(adminActDetailPage).toContain("Requested parser");
    expect(adminActDetailPage).toContain("Latest job parser");
    expect(adminActDetailPage).toContain("extraction_artifact.parser_name");
    expect(adminActDetailPage).toContain("physicalPagesChip");
    expect(adminActDetailPage).toContain("page map unknown");
    expect(adminActDetailPage).toContain("no physical page map");
    expect(adminActDetailPage).not.toContain("act?.parser_used");
    expect(adminActDetailPage).toContain("Extracted characters");
    expect(adminActDetailPage).toContain("Warnings");
    expect(adminActDetailPage).toContain("Errors");
  });

  it("admin act detail exposes metadata review controls", () => {
    const adminActDetailPage = readFileSync("app/admin/acts/[id]/page.tsx", "utf8");
    expect(adminActDetailPage).toContain("Metadata editor");
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
    expect(adminReferencesPage).toContain("Remap unverified");
    expect(adminReferencesPage).toContain("Needs review:");
    expect(adminReferencesPage).toContain('return "NEEDS_REVIEW"');
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
    expect(evaluationPage).toContain(">Evaluation</h1>");
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
    const relationshipDossier = readFileSync("components/relationship-dossier.tsx", "utf8");
    expect(relationshipsPage).toContain("Relationship explorer");
    expect(relationshipsPage).toContain("Focus");
    expect(relationshipsPage).toContain("Depth");
    expect(relationshipsPage).toContain("1 hop");
    expect(relationshipsPage).toContain("2 hops");
    expect(relationshipsPage).toContain("Render");
    expect(relationshipsPage).toContain("RelationshipDossier");
    expect(relationshipsPage).toContain("No verified relationships are available yet.");
    expect(relationshipsPage).toContain("Save reference");
    expect(relationshipsPage).toContain("Unsave from workspace");
    expect(relationshipGraph).toContain("Mapped Act-to-Act graph edges only");
    expect(relationshipGraph).toContain("No external Act-to-Act network to draw yet");
    expect(relationshipGraph).toContain("Press Render to load the relationship graph");
    expect(relationshipGraph).toContain("No verified relationships match these filters");
    expect(relationshipGraph).toContain("Unresolved relationships");
    expect(relationshipGraph).toContain("Focus:");
    expect(relationshipGraph).toContain("More citations");
    expect(relationshipGraph).toContain("This Act");
    expect(relationshipGraph).toContain("Linked Act");
    expect(relationshipsPage).toContain("Click a linked Act");
    expect(relationshipDossier).toContain("Focus Act");
    expect(relationshipDossier).toContain("View all in Table");
    expect(readFileSync("lib/relationship-dossier.ts", "utf8")).toContain("Amends / repeals");
    expect(relationshipsPage).toContain("Verified + pending");
    expect(relationshipsPage).toContain('placeholder="Choose an Act to focus the graph"');
    expect(relationshipsPage).toContain("fetchAllRelationshipRows");
    expect(relationshipsPage).toContain("graphModelFromRows");
    expect(relationshipsPage).toContain('statusFilter !== "ANY"');
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
    expect(sectionDetailPage).toContain("References involving this section");
    expect(sectionDetailPage).toContain("Reference evidence");
    expect(sectionDetailPage).toContain("font-serif text-base");
    expect(preview).toContain("No verified relationships are available yet.");
    expect(preview).toContain("information retrieval only");
    expect(preview).not.toContain("Correct reference");
    expect(preview).not.toContain("Clear mapping");
  });

  it("uses readable Act titles when PDF metadata is placeholder text", () => {
    expect(
      isPlaceholderActTitle("This Act can be downloaded from www.documents.gov.lk")
    ).toBe(true);
    expect(
      displayActTitle({
        title: "This Act can be downloaded from www.documents.gov.lk",
        act_number: "24",
        year: 2022,
        source_file_name: "personal-data-protection.pdf"
      })
    ).toBe("Act No. 24 of 2022");
  });

  it("relationship explorer uses readable Act titles and filter labels", () => {
    const relationshipsPage = readFileSync("app/lawyer/relationships/page.tsx", "utf8");
    expect(relationshipsPage).toContain("displayActTitle");
    expect(relationshipsPage).toContain("relationshipTypeLabel");
    expect(relationshipsPage).toContain('if (value === "ANY") return "All types"');
  });

  it("remounts app shell when auth session identity changes", () => {
    const authAwareShell = readFileSync("components/auth/auth-aware-shell.tsx", "utf8");
    const auth = readFileSync("lib/auth.ts", "utf8");
    const shell = readFileSync("components/app-shell.tsx", "utf8");
    expect(auth).toContain("SESSION_CHANGE_EVENT");
    expect(auth).toContain("sessionIdentityKey");
    expect(authAwareShell).toContain("key={sessionKey}");
    expect(authAwareShell).toContain("SESSION_CHANGE_EVENT");
    expect(shell).toContain("SESSION_CHANGE_EVENT");
    expect(shell).toContain("getStoredRole()");
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
    expect(shell).toContain("Signed in as");
    expect(shell).toContain("Terms");
    expect(shell).toContain("Privacy");
    expect(shell).toContain("shrink-0");
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
    expect(workspacePage).toContain(">Workspace</h1>");
    expect(workspacePage).toContain("Saved {type.toLowerCase()}");
    expect(workspacePage).toContain("Workspace filters");
    expect(workspacePage).toContain("Manual save");
    expect(workspacePage).toContain("Export CSV");
    expect(workspacePage).toContain("Export Markdown");
    expect(workspacePage).toContain("Save note");
    expect(workspacePage).toContain("Remove");
    expect(workspacePage).toContain("does not provide legal advice");
    expect(saveButton).toContain("Unsave from workspace");
    expect(actDetailPage).toContain("Save Act to workspace");
    expect(sectionDetailPage).toContain("Save Section to workspace");
  });
});
