/**
 * API 客户端
 */
import axios from "axios"

const client = axios.create({
  baseURL: "/api",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
})

// 请求拦截器：自动添加 Token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token")
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：处理 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token")
      localStorage.removeItem("user")
      localStorage.removeItem("role")
      window.location.href = "/"
    }
    return Promise.reject(error)
  }
)

export default client

// ====================== API 方法封装 ======================

export const authAPI = {
  login: (username: string, password: string) =>
    client.post("/login", { username, password }),
  register: (username: string, password: string) =>
    client.post("/register", { username, password }),
  verify: () => client.get("/verify"),
  getMyInfo: () => client.get("/users/me"),
}

export const chatAPI = {
  uploadImage: (image: File) => {
    const form = new FormData()
    form.append("image", image)
    return client.post("/chat/image-upload", form, { headers: { "Content-Type": "multipart/form-data" } })
  },
  send: (question: string, conversation_id = "") =>
    client.post("/chat/send", { question, conversation_id }, {
      responseType: "stream",
      adapter: "fetch",
    } as any),
  getConversations: () =>
    client.get("/chat/conversations"),
  deleteConversation: (id: string) =>
    client.delete(`/chat/conversations/${id}`),
  getHistory: (id: string) =>
    client.get(`/chat/history/${id}`),
  submitFeedback: (message_id: string, rating: number) =>
    client.post("/chat/feedback", { message_id, rating }),
  debug: (question: string, knowledge_base_ids: string[], conversation_id = "") =>
    client.post("/chat/debug", { question, knowledge_base_ids, conversation_id }),
}

export const documentAPI = {
  upload: (file: File, visibility = "internal", knowledge_base_id = "", chunk_template = "general") => {
    const formData = new FormData()
    formData.append("file", file)
    return client.post("/documents/upload", formData, {
      params: { visibility, knowledge_base_id, chunk_template },
      headers: { "Content-Type": "multipart/form-data" },
    })
  },
  list: (page = 1, page_size = 20, status = "", knowledge_base_id = "") =>
    client.get("/documents/list", { params: { page, page_size, status, knowledge_base_id } }),
  delete: (id: string) =>
    client.delete(`/documents/${id}`),
  chunks: (id: string, page = 1, page_size = 20) =>
    client.get("/documents/" + id + "/chunks", { params: { page, page_size } }),
  reindex: (id: string, chunk_template: string) =>
    client.post("/documents/" + id + "/reindex", null, { params: { chunk_template } }),
  content: (id: string) => client.get("/documents/" + id + "/content", { responseType: "blob" }),
  chunkImage: (documentId: string, chunkId: string) => client.get("/documents/" + documentId + "/chunks/" + chunkId + "/image", { responseType: "blob" }),
}
export const knowledgeBaseAPI = {
  list: () => client.get("/knowledge-bases"),
  create: (data: { name: string; description: string; visibility: string }) =>
    client.post("/knowledge-bases", data),
  update: (id: string, data: any) => client.put("/knowledge-bases/" + id, data),
  delete: (id: string) => client.delete("/knowledge-bases/" + id),
}

export const evaluationAPI = {
  items: () => client.get("/evaluation/items"),
  create: (data: any) => client.post("/evaluation/items", data),
  update: (id: string, data: any) => client.put("/evaluation/items/" + id, data),
  delete: (id: string) => client.delete("/evaluation/items/" + id),
  runs: () => client.get("/evaluation/runs"),
  run: (limit: number, generate_answers: boolean) => client.post("/evaluation/run", { limit, generate_answers }),
}
export const adminAPI = {
  users: () => client.get("/admin/users"),
  createUser: (data: any) => client.post("/admin/users", data),
  deleteUser: (id: string) => client.delete("/admin/users/" + id),
  toggleUser: (id: string) => client.put("/admin/users/" + id + "/toggle-status"),
  departments: () => client.get("/admin/departments"),
  createDepartment: (name: string, description = "") => client.post("/admin/departments", null, { params: { name, description } }),
  deleteDepartment: (id: string) => client.delete("/admin/departments/" + id),
  setDepartment: (userId: string, departmentId: string) => client.put("/admin/users/" + userId + "/department", null, { params: { department_id: departmentId } }),
  stats: () => client.get("/admin/stats"),
  history: (limit = 100) => client.get("/admin/history", { params: { limit } }),
}

export const operationsAPI = {
  auditLogs: (limit = 100, action = "") => client.get("/operations/audit-logs", { params: { limit, action } }),
  exportPrivacy: () => client.get("/operations/privacy/export"),
  deletePrivacy: () => client.delete("/operations/privacy/me"),
  setBaseline: (runId: string, name = "production") => client.post("/operations/evaluation/" + runId + "/baseline", null, { params: { name } }),
  compare: (runId: string, baseline = "production") => client.get("/operations/evaluation/compare", { params: { run_id: runId, baseline } }),
  health: () => client.get("/health"),
  ssoConfig: () => client.get("/sso/config"),
}

export const ecommerceAPI = {
  dashboard: () => client.get("/ecommerce/dashboard"),
  products: () => client.get("/ecommerce/products"),
  simulationState: () => client.get("/ecommerce/simulation/state"),
  advanceSimulation: (expected_version: number) => client.post("/ecommerce/simulation/advance", { expected_version }),
  resetSimulation: (expected_version: number) => client.post("/ecommerce/simulation/reset", { expected_version }),
  analyze: (question: string, session_id = "") => client.post("/ecommerce/agent/analyze", { question, session_id }),
  sessions: () => client.get("/ecommerce/sessions"),
  sessionDetail: (id: string) => client.get(`/ecommerce/sessions/${id}`),
  customers: () => client.get("/ecommerce/customers"),
  funnel: () => client.get("/ecommerce/analytics/funnel"),
  forecast: () => client.get("/ecommerce/analytics/forecast"),
  campaignEffect: () => client.get("/ecommerce/campaigns/effect"),
  runs: (execution_mode = "", status = "") => client.get("/ecommerce/runs", { params: { execution_mode, status } }),
  runDetail: (id: string) => client.get(`/ecommerce/runs/${id}`),
  runSummary: () => client.get("/ecommerce/runs/summary"),
  evaluations: () => client.get("/ecommerce/agent/evaluations"),
  runEvaluation: (online = false) => client.post("/ecommerce/agent/evaluations/run", null, { params: { online } }),
  createJob: (question: string, session_id = "", idempotency_key = crypto.randomUUID()) => client.post("/ecommerce/agent/jobs", { question, session_id, idempotency_key }),
  jobStatus: (jobId: string) => client.get(`/ecommerce/agent/jobs/${jobId}`),
  cancelJob: (jobId: string) => client.delete(`/ecommerce/agent/jobs/${jobId}`),
  campaignPlan: (goal = "大促增长") => client.get("/ecommerce/campaigns/plan", { params: { goal } }),
  createGrowthWorkflow: (product_id: string, platform: string, market_keyword: string) => client.post("/ecommerce/growth/workflows", { product_id, platform, market_keyword }),
  growthWorkflow: (recommendationId: string) => client.get(`/ecommerce/growth/workflows/${recommendationId}`),
  publishGrowthWorkflow: (recommendationId: string) => client.post(`/ecommerce/growth/workflows/${recommendationId}/publish`),
  recommendations: (status = "") => client.get("/ecommerce/recommendations", { params: { status } }),
  recommendationDetail: (id: string) => client.get(`/ecommerce/recommendations/${id}`),
  approveRecommendation: (id: string, version = 1, comment = "") => client.post(`/ecommerce/recommendations/${id}/approve`, { expected_version: version, comment, idempotency_key: crypto.randomUUID() }),
  rejectRecommendation: (id: string, version = 1, comment = "") => client.post(`/ecommerce/recommendations/${id}/reject`, { expected_version: version, comment, idempotency_key: crypto.randomUUID() }),
}
