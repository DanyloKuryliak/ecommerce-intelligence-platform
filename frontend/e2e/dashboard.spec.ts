import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const snapshot = JSON.parse(readFileSync(resolve(process.cwd(), "../web/demo-data.json"), "utf8"));

for (const width of [1440, 768, 375]) {
  test(`dashboard layout at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Understand the store/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Product performance" })).toBeVisible();
    await expect(page.locator(".recharts-line")).toBeVisible();
    await page.screenshot({ path: `test-results/dashboard-${width}.png`, fullPage: width !== 1440, animations: "disabled" });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBe(false);
  });
}

test("forecast scenario and customer scoring", async ({ page }) => {
  await page.route("http://127.0.0.1:8001/api/v1/dashboard", (route) => route.fulfill({ json: snapshot }));
  await page.route("http://127.0.0.1:8001/api/v1/customers/1/churn-score", (route) => route.fulfill({
    json: { customer_id: 1, churn_probability: 0.72, risk_band: "high", model: "extra_trees", model_run_id: "test", reasons: ["No recent order"] },
  }));
  await page.goto("/");
  await expect(page.getByText("Local live pipeline")).toBeVisible();
  await page.getByRole("slider", { name: "Sales growth assumption" }).fill("20");
  await expect(page.getByText("+20%", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Analyze customer/ }).click();
  await expect(page.getByText(/churn risk/)).toBeVisible();
});
