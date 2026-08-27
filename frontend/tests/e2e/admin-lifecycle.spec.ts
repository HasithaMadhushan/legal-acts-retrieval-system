import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const apiBase = "http://127.0.0.1:8000/api/v1";
const adminEmail = process.env.PLAYWRIGHT_ADMIN_EMAIL;
const adminPassword = process.env.PLAYWRIGHT_ADMIN_PASSWORD;
const managedUserEmail = "playwright-admin-managed@example.com";
const managedUserPassword = "ManagedUserPass123!";
const fixturePdf = path.resolve(
  process.cwd(),
  "../data/evaluation-acts/09_code-of-criminal-procedure-amendment-act-2-of-2022.pdf"
);

async function signInAsAdmin(page: Page) {
  test.skip(!adminEmail || !adminPassword, "Set PLAYWRIGHT_ADMIN_EMAIL/PASSWORD to enable Admin lifecycle QA.");
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail!);
  await page.getByLabel("Password").fill(adminPassword!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin\/acts$/);
}

async function adminToken(request: APIRequestContext) {
  const response = await request.post(`${apiBase}/auth/login`, {
    data: { email: adminEmail, password: adminPassword, remember_me: false }
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).access_token as string;
}

async function ensureManagedUser(request: APIRequestContext) {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };
  const listResponse = await request.get(`${apiBase}/users`, { headers });
  expect(listResponse.ok()).toBeTruthy();
  const users = (await listResponse.json()) as Array<{ id: string; email: string }>;
  const existing = users.find((user) => user.email === managedUserEmail);

  if (existing) {
    const resetResponse = await request.patch(`${apiBase}/users/${existing.id}`, {
      headers,
      data: { role: "GENERAL_USER", is_active: true, password: managedUserPassword }
    });
    expect(resetResponse.ok()).toBeTruthy();
    return existing.id;
  }

  const createResponse = await request.post(`${apiBase}/users`, {
    headers,
    data: {
      full_name: "Playwright Managed User",
      email: managedUserEmail,
      password: managedUserPassword,
      role: "GENERAL_USER",
      is_active: true
    }
  });
  expect(createResponse.ok()).toBeTruthy();
  return ((await createResponse.json()) as { id: string }).id;
}

async function removeExistingFixtureAct(request: APIRequestContext) {
  const token = await adminToken(request);
  const headers = { Authorization: `Bearer ${token}` };
  const response = await request.get(`${apiBase}/acts`, { headers });
  expect(response.ok()).toBeTruthy();
  const acts = (await response.json()) as Array<{ id: string; source_file_name: string }>;
  const existing = acts.find(
    (act) => act.source_file_name === "09_code-of-criminal-procedure-amendment-act-2-of-2022.pdf"
  );
  if (!existing) return;
  const deleteResponse = await request.delete(`${apiBase}/acts/${existing.id}`, { headers });
  const detail = await deleteResponse.text();
  expect(deleteResponse.ok(), detail).toBeTruthy();
}

test.describe("Admin lifecycle QA", () => {
  test.describe.configure({ mode: "serial" });

  test("admin changes a user role and deactivates the account", async ({ page, request }) => {
    await ensureManagedUser(request);
    await signInAsAdmin(page);
    await page.goto("/admin/users");

    let row = page.getByRole("row").filter({ hasText: managedUserEmail });
    await expect(row).toBeVisible();
    const rolePicker = row.getByRole("combobox", { name: `Role for ${managedUserEmail}` });
    await rolePicker.click();
    await page.getByRole("option", { name: "Lawyer" }).click();
    await expect(row).toContainText("LAWYER");

    await row.getByRole("button", { name: "Deactivate" }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.getByRole("alertdialog").getByRole("button", { name: "Deactivate" }).click();
    row = page.getByRole("row").filter({ hasText: managedUserEmail });
    await expect(row).toContainText("INACTIVE");
    await expect(row.getByRole("combobox", { name: `Role for ${managedUserEmail}` })).toBeDisabled();
  });

  test("admin completes the Act ingestion, review, evaluation, and deletion workflow", async ({ page, request }) => {
    test.setTimeout(180_000);
    await removeExistingFixtureAct(request);
    await signInAsAdmin(page);

    const existingActLink = page.locator('a[href^="/admin/acts/"]:not([href$="/upload"])').first();
    await expect(existingActLink).toBeVisible();
    const existingHref = await existingActLink.getAttribute("href");
    const targetActId = existingHref!.split("/").pop()!;

    await page.goto("/admin/acts/upload");
    await page.locator("#file").setInputFiles(fixturePdf);
    await page.getByLabel("Title override").fill("Playwright Lifecycle Act");
    await page.getByLabel("Optional Act number").fill("902");
    await page.getByLabel("Optional year").fill("2026");
    await page.getByLabel("Category").fill("Browser QA");
    await page.getByRole("checkbox", { name: "Create processing job immediately after upload" }).uncheck();

    const uploadResponsePromise = page.waitForResponse(
      (response) => response.url().endsWith("/api/v1/acts/upload") && response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Save as uploaded only" }).click();
    const uploadResponse = await uploadResponsePromise;
    expect(uploadResponse.ok()).toBeTruthy();
    const uploadedAct = (await uploadResponse.json()) as { id: string };
    const actId = uploadedAct.id;
    await expect(page.getByText(/awaiting processing and Admin verification/)).toBeVisible();

    await page.goto(`/admin/acts/${actId}`);
    const processButton = page.getByRole("button", { name: "Reprocess ↻" });
    await processButton.click();
    await expect(page.getByText("PROCESSED", { exact: true }).first()).toBeVisible({ timeout: 120_000 });
    await expect(page.getByRole("button", { name: "Reprocess ↻" })).toBeEnabled();

    await page.getByLabel("Act title").fill("Playwright Reviewed Lifecycle Act");
    await page.getByLabel("Category / subject area").fill("Reviewed browser QA");
    await page.getByRole("button", { name: "Save metadata" }).click();
    await expect(page.getByText("Metadata saved for Admin review.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Playwright Reviewed Lifecycle Act" })).toBeVisible();

    await page.getByRole("link", { name: "Review sections" }).click();
    await expect(page.getByRole("heading", { name: "Review extracted sections" })).toBeVisible();
    let sectionForm = page.locator("form").filter({ hasText: "Section correction" }).first();
    await expect(sectionForm).toBeVisible();
    await sectionForm.getByLabel("Heading").fill("Reviewed through Playwright");
    await sectionForm.getByRole("button", { name: "Save section correction" }).click();
    await expect(page.getByText("Section correction saved.")).toBeVisible();
    sectionForm = page.locator("form").filter({ hasText: "Section correction" }).first();
    await sectionForm.getByRole("button", { name: "Verify" }).click();
    await expect(page.getByText("Section verified.")).toBeVisible();

    await page.goto(`/admin/acts/${actId}/references?status=ANY`);
    await page.getByText("Manual reference creation").click();
    const rawReference = `Playwright mapped reference ${actId}`;
    await page.getByLabel("Raw matched text").last().fill(rawReference);
    await page.getByLabel("Context snippet").last().fill(`QA context for ${rawReference}`);
    await page.getByLabel("Target Act title").last().fill("Existing target Act");
    await page.getByRole("button", { name: "Create manual reference" }).click();
    await expect(page.getByText("Manual reference created.")).toBeVisible();

    let referenceRow = page.getByRole("row").filter({ hasText: rawReference });
    await expect(referenceRow).toBeVisible();
    await referenceRow.getByText("Correct reference").click();
    await referenceRow.getByLabel("Mapped target Act ID").fill(targetActId);
    await referenceRow.getByRole("button", { name: "Link mapping" }).click();
    await expect(page.getByText("Mapping linked.")).toBeVisible();
    referenceRow = page.getByRole("row").filter({ hasText: rawReference });
    await referenceRow.getByRole("button", { name: "Verify" }).click();
    await expect(page.getByText("Reference verified.")).toBeVisible();

    await page.goto("/admin/evaluation");
    await page.getByPlaceholder("Limit run to Act ID").fill(actId);
    await page.getByRole("button", { name: /Run evaluation/ }).click();
    await expect(page.getByText("Evaluation run completed.")).toBeVisible({ timeout: 30_000 });

    await page.goto(`/admin/acts/${actId}`);
    await page.getByRole("button", { name: "Delete Act" }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.getByRole("alertdialog").getByRole("button", { name: "Delete Act" }).click();
    await expect(page).toHaveURL(/\/admin\/acts$/);
    await expect(page.getByText("Playwright Reviewed Lifecycle Act")).toHaveCount(0);
  });
});
