import axios from "axios"

const client = axios.create({
  baseURL: "/api",
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token")
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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
  },
)

export default client

export const authAPI = {
  login: (username: string, password: string) => client.post("/login", { username, password }),
  register: (username: string, password: string) => client.post("/register", { username, password }),
  verify: () => client.get("/verify"),
  getMyInfo: () => client.get("/users/me"),
}

export const ecommerceAPI = {
  sendConversationMessage: (message: string, session_id?: string) => client.post("/ecommerce/conversations/messages", { message, session_id }),
  conversations: () => client.get("/ecommerce/conversations"),
  conversation: (id: string) => client.get(`/ecommerce/conversations/${id}`),
  resumeAutonomousTask: (id: string) => client.post(`/ecommerce/autonomous/tasks/${id}/resume`),
  dashboard: () => client.get("/ecommerce/dashboard"),
  mcpStatus: () => client.get("/ecommerce/mcp/status"),
  executionTasks: () => client.get("/ecommerce/execution/tasks"),
  createExecutionTask: (goal: string) => client.post("/ecommerce/execution/tasks", { goal }),
  executionTask: (id: string) => client.get(`/ecommerce/execution/tasks/${id}`),
  approveExecutionTask: (id: string, expected_version: number, comment = "") =>
    client.post(`/ecommerce/execution/tasks/${id}/approve`, { expected_version, comment }),
  rollbackExecutionTask: (id: string, expected_version: number) =>
    client.post(`/ecommerce/execution/tasks/${id}/rollback`, { expected_version, comment: "rollback" }),
  products: () => client.get("/ecommerce/products"),
  simulationState: () => client.get("/ecommerce/simulation/state"),
  advanceSimulation: (expected_version: number) => client.post("/ecommerce/simulation/advance", { expected_version }),
  resetSimulation: (expected_version: number) => client.post("/ecommerce/simulation/reset", { expected_version }),
  funnel: () => client.get("/ecommerce/analytics/funnel"),
  forecast: () => client.get("/ecommerce/analytics/forecast"),
}
