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
  await expect(page.getByRole("heading", { name: /便携榨汁杯.*推广文案/ })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText("分析报告")).toBeVisible()
  await expect(page.getByText("等待人工批准")).toHaveCount(0)
  await expect(page.getByText("已创建推广活动")).toHaveCount(0)
})

test("agent asks for missing channel then resumes the same conversation", async ({ page }) => {
  await page.goto("/agent")
  await page.locator(".command-input input").fill("给便携榨汁杯写推广文案")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByText(/准备发布在哪个渠道/)).toBeVisible({ timeout: 30_000 })

  await page.locator(".command-input input").fill("小红书，语气生活化")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByRole("heading", { name: /便携榨汁杯.*小红书.*推广文案/ })).toBeVisible({ timeout: 30_000 })
})

test("agent fills a missing product from the next message", async ({ page }) => {
  await page.goto("/agent")
  await page.locator(".command-input input").fill("写一篇小红书推广文案")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByText(/商品名称或商品编号/)).toBeVisible({ timeout: 30_000 })

  await page.locator(".command-input input").fill("便携榨汁杯")
  await page.getByRole("button", { name: "创建并运行" }).click()

  await expect(page.getByRole("heading", { name: /便携榨汁杯.*小红书.*推广文案/ })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/商品名称或商品编号/)).toHaveCount(1)
})

test("competitor analysis returns evidence and never creates a campaign", async ({ page }) => {
  await page.goto("/agent")
  await page.locator(".command-input input").fill("给便携榨汁杯做一个小红书竞品分析")
  await page.getByRole("button", { name: "创建并运行" }).click()

  await expect(page.getByRole("heading", { name: /竞品分析/ })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText("建议动作")).toBeVisible()
  await expect(page.getByText(/查看数据证据/)).toBeVisible()
  await expect(page.getByText("已创建推广活动")).toHaveCount(0)
  await expect(page.getByText("等待人工批准")).toHaveCount(0)
})

test("follow-up resolves actions from the previous report", async ({ page }) => {
  await page.goto("/agent")
  await page.locator(".command-input input").fill("给便携榨汁杯做一个小红书竞品分析")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByRole("heading", { name: /竞品分析/ })).toBeVisible({ timeout: 30_000 })

  await page.locator(".command-input input").fill("实现你的建议动作")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByText(/1\. 先产出 3 组差异化内容/)).toBeVisible()
  await expect(page.getByText(/你希望我重点解决哪类问题/)).toHaveCount(0)

  await page.locator(".command-input input").fill("执行第一个")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByRole("heading", { name: /便携榨汁杯.*小红书.*推广文案/ })).toBeVisible({ timeout: 30_000 })
})

test("autonomous goal clarifies contract and shows replan loop", async ({ page }) => {
  await page.goto("/agent")
  await page.locator(".command-input input").fill("自主提升便携榨汁杯转化率")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByText(/多少天内达成目标/)).toBeVisible()
  await expect(page.getByText(/预算上限/)).toBeVisible()

  await page.locator(".command-input input").fill("未来7天提升15%，预算1000元")
  await page.getByRole("button", { name: "创建并运行" }).click()
  await expect(page.getByRole("heading", { name: "自主运营闭环运行报告" })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText("Critic 反思与重规划")).toBeVisible()
  await expect(page.getByText(/第 1 轮 · replan/)).toBeVisible()
  await expect(page.getByText(/商品语义和用户偏好记忆/)).toBeVisible()
})

test("mobile execution workspace has no horizontal overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile")
  await page.goto("/agent")
  await expect(page.getByRole("heading", { name: "电商运营执行助手" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
