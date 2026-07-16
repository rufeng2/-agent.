import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page, request }) => {
  const username = `e2e-${Date.now()}-${Math.floor(Math.random() * 10000)}`
  const password = "e2e-password-123"
  const registered = await request.post("http://127.0.0.1:8001/api/register", { data: { username, password, display_name: "E2E" } })
  let auth = await registered.json()
  if (!auth.token) {
    auth = await (await request.post("http://127.0.0.1:8001/api/login", { data: { username, password } })).json()
  }
  expect(auth.token, `authentication failed: ${JSON.stringify(auth)}`).toBeTruthy()
  await page.addInitScript(({ token, username }) => {
    localStorage.setItem("token", token)
    localStorage.setItem("role", "user")
    localStorage.setItem("username", username)
  }, { token: auth.token, username })
})

test("execution task pauses for approval and returns MCP receipt", async ({ page }) => {
  await page.goto("/agent")
  await expect(page.getByText("MCP ready")).toBeVisible({ timeout: 20_000 })
  await page.locator(".command-input input").fill("下架商品 P003")
  await page.getByRole("button", { name: "创建并运行" }).click()

  await expect(page.getByText("等待人工批准"), "task creation must reach the approval gate").toBeVisible()
  await page.getByRole("button", { name: "批准并执行" }).click()
  await page.getByRole("button", { name: "批准并执行" }).last().click()

  await expect(page.getByText("业务工具已完成写入")).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/ecommerce-operations.*set_product_listing/)).toBeVisible()
  await expect(page.getByText("stdio")).toBeVisible()
})

test("composite task exposes completed DAG steps", async ({ page }) => {
  await page.goto("/agent")
  await page.locator(".command-input input").fill("把云感防晒衣价格调整到190元并创建新品推广活动")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByText("等待人工批准")).toBeVisible()
  await page.getByRole("button", { name: "批准并执行" }).click()
  await page.getByRole("button", { name: "批准并执行" }).last().click()

  await expect(page.getByText("price · completed")).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText("campaign · completed")).toBeVisible()
})

test("copy request delivers copy instead of creating a campaign", async ({ page }) => {
  await page.goto("/agent")
  await page.locator(".command-input input").fill("给便携榨汁杯做一个小红书推广文案")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByText("等待人工批准")).toBeVisible({ timeout: 30_000 })
  await page.getByRole("button", { name: "批准并执行" }).click()
  await page.getByRole("button", { name: "批准并执行" }).last().click()

  await expect(page.getByRole("heading", { name: "推广文案已生成" })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator(".copy-result h4")).not.toBeEmpty()
  await expect(page.getByText(/DeepSeek 生成|模板降级/)).toBeVisible()
  await expect(page.getByText("已创建推广活动")).toHaveCount(0)
})

test("mobile execution workspace has no horizontal overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile")
  await page.goto("/agent")
  await expect(page.getByRole("heading", { name: "电商运营执行助手" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
