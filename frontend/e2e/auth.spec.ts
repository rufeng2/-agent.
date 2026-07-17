import { expect, test } from "@playwright/test"

test("user can register and login through the UI", async ({ page }) => {
  const username = `ui-auth-${Date.now()}`
  const password = "ui-auth-password-123"

  await page.goto("/")
  await expect(page.getByText("运营执行服务已连接")).toBeVisible({ timeout: 15_000 })
  await page.getByRole("tab", { name: "注册账号" }).click()
  const registerPanel = page.getByRole("tabpanel", { name: "注册账号" })
  await registerPanel.getByLabel("用户名").fill(username)
  await registerPanel.getByLabel("密码").fill(password)
  await page.getByRole("button", { name: "创建账号" }).click()

  await expect(page.getByText("账号已创建，请登录")).toBeVisible()
  const loginPanel = page.getByRole("tabpanel", { name: "账号登录" })
  await loginPanel.getByLabel("用户名").fill(username)
  await loginPanel.getByLabel("密码").fill(password)
  await page.getByRole("button", { name: "登录" }).click()

  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole("link", { name: "运营执行助手" })).toBeVisible()
})
