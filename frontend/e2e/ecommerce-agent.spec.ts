import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("token", "demo-e2e-token")
    localStorage.setItem("role", "user")
    localStorage.setItem("user", "e2e-user")
  })
})

test("agent analysis persists a session and exposes a run", async ({ page }) => {
  await page.goto("/agent")
  await page.getByPlaceholder("例如：昨天 GMV 为什么下降？").fill("昨天 GMV 为什么下降？")
  await page.getByRole("button", { name: "分析", exact: true }).click()

  await expect(page.getByText("deterministic_fallback")).toBeVisible()
  await expect(page.getByText("Agent 执行轨迹")).toBeVisible()
  await page.goto("/runs")
  await expect(page.getByRole("heading", { name: "Agent 运行中心" })).toBeVisible()
  await expect(page.locator(".el-table__body tr").first()).toBeVisible()
})

test("campaign goals produce goal-specific strategy and products", async ({ page }) => {
  await page.goto("/campaigns")
  const input = page.locator(".toolbar-row input")
  await input.fill("新品冷启动")
  await page.getByRole("button", { name: "生成策略" }).click()
  await expect(page.getByRole("heading", { name: "新品冷启动策略" })).toBeVisible()
  await expect(page.getByText("抗菌保温杯").first()).toBeVisible()
  await expect(page.getByText("模拟测算，不代表真实业务承诺")).toBeVisible()
})

test("mobile dashboard keeps navigation and analysis content usable", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile")
  await page.goto("/dashboard")
  await expect(page.getByRole("heading", { name: "运营驾驶舱" })).toBeVisible()
  await page.locator(".mobile-header button").click()
  await expect(page.getByText("客户分析")).toBeVisible()
})

test("product simulation advances, survives refresh, and resets", async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium")
  const initialResponse = await request.get("http://127.0.0.1:8001/api/ecommerce/simulation/state")
  const initial = (await initialResponse.json()).data
  if (initial.step > 0) {
    await request.post("http://127.0.0.1:8001/api/ecommerce/simulation/reset", { data: { expected_version: initial.version } })
  }

  await page.goto("/products")
  await expect(page.getByText(/模拟日期/)).not.toHaveText("模拟日期 -")
  const dateBefore = await page.getByText(/模拟日期/).textContent()
  const gmvBefore = await page.locator(".el-table__body tr").first().locator("td").nth(4).innerText()
  await page.getByRole("button", { name: "推进一天" }).click()

  await expect(page.getByText("今日经营事件")).toBeVisible()
  await expect(page.getByText(/模拟日期/)).not.toHaveText(dateBefore || "")
  const gmvAfter = await page.locator(".el-table__body tr").first().locator("td").nth(4).innerText()
  expect(gmvAfter).not.toBe(gmvBefore)

  const advancedDate = await page.getByText(/模拟日期/).textContent()
  await page.reload()
  await expect(page.getByText(/模拟日期/)).toHaveText(advancedDate || "")

  await page.getByRole("button", { name: "重置模拟" }).click()
  await page.getByRole("button", { name: "确定" }).click()
  await expect(page.getByText(/模拟日期/)).toHaveText(dateBefore || "")
})
