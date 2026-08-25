import { expect, test, type Page } from "@playwright/test";

const adminEmail = process.env.PLAYWRIGHT_ADMIN_EMAIL;
const adminPassword = process.env.PLAYWRIGHT_ADMIN_PASSWORD;

async function signInAsAdmin(page: Page) {
  test.skip(!adminEmail || !adminPassword, "Set PLAYWRIGHT_ADMIN_EMAIL/PASSWORD to enable admin UI QA.");
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail!);
  await page.getByLabel("Password").fill(adminPassword!);
  await page.getByRole("checkbox", { name: "Keep me signed in" }).check();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin\/acts$/);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Upload" })).toBeVisible();
}

test.describe("Admin UI QA", () => {
  test("admin shell exposes the correct navigation and no client errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await signInAsAdmin(page);

    await expect(page.getByRole("navigation", { name: "Main navigation" })).toContainText("Acts");
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toContainText("Upload");
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toContainText("Users");
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toContainText("Evaluation");
    await expect(page.getByRole("heading", { name: "Acts" })).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("acts filters and upload navigation work", async ({ page }) => {
    await signInAsAdmin(page);
    await expect(page.getByRole("heading", { name: "Acts" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Upload Act PDF/ })).toHaveAttribute("href", "/admin/acts/upload");

    const search = page.getByPlaceholder("Search title, act number…");
    await search.fill("no-act-with-this-title");
    await expect(page.getByText("No Acts match these filters.")).toBeVisible();
    await page.getByRole("button", { name: "Clear", exact: true }).click();
    await expect(search).toHaveValue("");

    await page.getByRole("link", { name: /Upload Act PDF/ }).click();
    await expect(page).toHaveURL(/\/admin\/acts\/upload$/);
    await expect(page.getByRole("heading", { name: "Upload Act PDF" })).toBeVisible();
  });

  test("upload validation, evaluation, and users screens are interactive", async ({ page }) => {
    await signInAsAdmin(page);
    await page.goto("/admin/acts/upload");
    await expect(page.getByRole("heading", { name: "Upload Act PDF" })).toBeVisible();
    await page.getByRole("button", { name: "Upload & process" }).click();
    await expect(page.getByText("Choose a PDF file first.")).toBeVisible();
    await expect(page.locator("#file")).toHaveAttribute("accept", "application/pdf");

    await page.goto("/admin/evaluation");
    await expect(page.getByRole("heading", { name: "Evaluation", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Run evaluation" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Refresh", exact: true })).toBeEnabled();

    await page.goto("/admin/users");
    await expect(page.getByRole("heading", { name: "Users" })).toBeVisible();
    await expect(page.getByText(/All users ·/)).toBeVisible();
    await expect(page.getByText(/Attorney verification requests ·/)).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Role for user@example.com" })).toBeVisible();
  });

  test("act management links open when corpus data exists", async ({ page }) => {
    await signInAsAdmin(page);
    const actLink = page.locator('a[href^="/admin/acts/"]:not([href$="/upload"])').first();
    if (await actLink.count()) {
      await actLink.click();
      await expect(page).toHaveURL(/\/admin\/acts\/[^/]+$/);
      await expect(page.getByRole("link", { name: /Review references/ })).toBeVisible();
      await expect(page.getByRole("button", { name: "Delete Act" })).toBeVisible();
    } else {
      await expect(page.getByRole("heading", { name: "Acts" })).toBeVisible();
    }
  });
});
