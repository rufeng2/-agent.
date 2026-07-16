import { createRouter, createWebHistory } from "vue-router"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "login",
      component: () => import("@/views/Login.vue"),
      meta: { title: "登录", public: true },
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("@/views/Ecommerce/Dashboard.vue"),
      meta: { title: "运营驾驶舱", requiresAuth: true },
    },
    {
      path: "/agent",
      name: "agent",
      component: () => import("@/views/Ecommerce/ExecutionAgentWorkspace.vue"),
      meta: { title: "电商运营执行助手", requiresAuth: true },
    },
    {
      path: "/products",
      name: "products",
      component: () => import("@/views/Ecommerce/Products.vue"),
      meta: { title: "商品分析", requiresAuth: true },
    },
    { path: "/:pathMatch(.*)*", redirect: "/agent" },
  ],
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || "运营工作台"} - 智能电商运营 Agent 平台`

  const token = localStorage.getItem("token")
  const role = localStorage.getItem("role")

  if (to.meta.requiresAuth && !token) {
    next({ name: "login" })
  } else if (to.meta.requiresAdmin && role !== "admin") {
    next({ name: "dashboard" })
  } else {
    next()
  }
})

export default router
