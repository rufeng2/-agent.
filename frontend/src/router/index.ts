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
      path: "/operations-center",
      name: "operations-center",
      component: () => import("@/views/Ecommerce/OperationsCenter.vue"),
      meta: { title: "运营任务中心", requiresAuth: true },
    },
    {
      path: "/agent",
      name: "agent",
      component: () => import("@/views/Ecommerce/AgentWorkspace.vue"),
      meta: { title: "运营 Agent", requiresAuth: true },
    },
    {
      path: "/products",
      name: "products",
      component: () => import("@/views/Ecommerce/Products.vue"),
      meta: { title: "商品分析", requiresAuth: true },
    },
    {
      path: "/customers",
      name: "customers",
      component: () => import("@/views/Ecommerce/Customers.vue"),
      meta: { title: "客户分析", requiresAuth: true },
    },
    {
      path: "/campaigns",
      name: "campaigns",
      component: () => import("@/views/Ecommerce/Campaigns.vue"),
      meta: { title: "活动策略", requiresAuth: true },
    },
    {
      path: "/growth-workflow",
      name: "growth-workflow",
      component: () => import("@/views/Ecommerce/GrowthWorkflow.vue"),
      meta: { title: "跨境增长工作流", requiresAuth: true },
    },
    {
      path: "/recommendations",
      name: "recommendations",
      component: () => import("@/views/Ecommerce/Recommendations.vue"),
      meta: { title: "建议审批", requiresAuth: true },
    },
    {
      path: "/runs",
      name: "runs",
      component: () => import("@/views/Ecommerce/Runs.vue"),
      meta: { title: "Agent 运行中心", requiresAuth: true },
    },
    {
      path: "/agent-evaluation",
      name: "agent-evaluation",
      component: () => import("@/views/Ecommerce/AgentEvaluation.vue"),
      meta: { title: "电商 Agent 评测", requiresAuth: true },
    },
    {
      path: "/knowledge",
      name: "knowledge",
      component: () => import("@/views/Documents.vue"),
      meta: { title: "运营知识库", requiresAuth: true },
    },
    {
      path: "/evaluation",
      name: "evaluation",
      component: () => import("@/views/Evaluation.vue"),
      meta: { title: "Agent 分析质量评测", requiresAuth: true, requiresAdmin: true },
    },
    {
      path: "/admin",
      name: "admin",
      component: () => import("@/views/Admin/Dashboard.vue"),
      meta: { title: "运营管理后台", requiresAuth: true, requiresAdmin: true },
    },
    { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
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
