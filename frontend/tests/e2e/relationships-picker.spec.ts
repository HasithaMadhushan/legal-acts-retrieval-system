import { expect, test } from "@playwright/test";

test("lawyer can choose a relationship focus Act without knowing its UUID", async ({ page }) => {
  const email = process.env.PLAYWRIGHT_LAWYER_EMAIL;
  const password = process.env.PLAYWRIGHT_LAWYER_PASSWORD;
  test.skip(!email || !password, "Set PLAYWRIGHT_LAWYER_EMAIL/PASSWORD to enable relationship picker QA.");

  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("checkbox", { name: "Keep me signed in" }).check();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/lawyer\/search$/);
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Relationships" })).toBeVisible();

  await page.goto("/lawyer/relationships");
  await expect(page.getByRole("heading", { name: "Relationship explorer" })).toBeVisible();
  const focusPicker = page.getByRole("combobox").first();
  await expect(focusPicker).toBeVisible();
  await focusPicker.click();
  const antiCorruptionAct = page.getByRole("option", {
    name: /Anti-Corruption Act.*No\. 9.*2023/i
  });
  await expect(antiCorruptionAct).toBeVisible();
  await antiCorruptionAct.click();
  await page.getByRole("button", { name: "Render" }).click();
  await expect(
    page.getByRole("img", { name: "Mapped Act-to-Act relationship graph" })
  ).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/\d+ nodes? · [1-9]\d* edges?/i)).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("relationship-explorer.png"), fullPage: true });
});
