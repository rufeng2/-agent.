import os

from locust import HttpUser, between, task


class EcommerceAgentUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        username = os.getenv("LOCUST_USERNAME", "admin")
        password = os.getenv("LOCUST_PASSWORD", "admin123456")
        response = self.client.post("/api/login", json={"username": username, "password": password})
        token = response.json().get("token", "")
        self.headers = {"Authorization": f"Bearer {token}"}

    @task(4)
    def health(self):
        self.client.get("/api/health")

    @task(3)
    def dashboard(self):
        self.client.get("/api/ecommerce/dashboard", headers=self.headers)

    @task(2)
    def products(self):
        self.client.get("/api/ecommerce/products", headers=self.headers)

    @task(1)
    def mcp_status(self):
        self.client.get("/api/ecommerce/mcp/status", headers=self.headers)
