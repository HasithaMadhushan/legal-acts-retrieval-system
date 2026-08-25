import { expect, test } from "@playwright/test";

const publicRoutes = ["/", "/browse", "/search", "/login"];
const protectedRoutes = [
  "/dashboard",
  "/admin/acts",
  "/admin/acts/upload",
  "/admin/evaluation",
  "/admin/users",
  "/lawyer/search",
  "/lawyer/relationships",
  "/lawyer/workspace",
];

test.describe("LexAtlas public smoke checks", () => {
  for (const route of publicRoutes) {
    test(`${route} renders without a client error`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));

      await page.goto(route);
      await expect(page.locator("body")).toBeVisible();
      expect(errors).toEqual([]);
    });
  }
});

test.describe("Unauthenticated access guards", () => {
  for (const route of protectedRoutes) {
    test(`${route} redirects to login`, async ({ page }) => {
      await page.goto(route);
      await expect(page).toHaveURL(/\/login\?next=/);
      await expect(page.locator('[data-slot="card-title"]', { hasText: "Sign in" })).toBeVisible();
    });
  }
});

test.describe("Configured role sessions", () => {
  const roles = [
    { name: "general", email: process.env.PLAYWRIGHT_GENERAL_EMAIL, password: process.env.PLAYWRIGHT_GENERAL_PASSWORD, home: "/search" },
    { name: "admin", email: process.env.PLAYWRIGHT_ADMIN_EMAIL, password: process.env.PLAYWRIGHT_ADMIN_PASSWORD, home: "/admin/acts" },
    { name: "lawyer", email: process.env.PLAYWRIGHT_LAWYER_EMAIL, password: process.env.PLAYWRIGHT_LAWYER_PASSWORD, home: "/lawyer/search" },
  ];

  for (const role of roles) {
    test(`${role.name} session reaches its landing page`, async ({ page }) => {
      test.skip(!role.email || !role.password, `Set PLAYWRIGHT_${role.name.toUpperCase()}_EMAIL/PASSWORD to enable this role test.`);
      await page.goto("/login");
      await page.getByLabel("Email").fill(role.email!);
      await page.getByLabel("Password").fill(role.password!);
      await page.getByRole("button", { name: "Sign in" }).click();
      await expect(page).toHaveURL(new RegExp(`${role.home.replace("/", "\\/")}$`));
    });
  }
});
