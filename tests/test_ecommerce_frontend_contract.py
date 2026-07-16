from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_MARKERS = ("鏅", "鐢", "鍟", "杩", "寤", "鏁", "椋", "�", "乂", "丒")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_frontend_uses_ecommerce_product_identity():
    app = read("frontend/src/App.vue")
    login = read("frontend/src/views/Login.vue")
    router = read("frontend/src/router/index.ts")

    assert "智能电商运营 Agent 平台" in app
    assert "运营驾驶舱" in app
    assert "运营 Agent" in app
    assert "运营知识库" in app
    assert "智能电商运营 Agent 平台" in login
    assert 'path: "/dashboard"' in router
    assert 'path: "/agent"' in router
    assert 'path: "/recommendations"' in router
    assert "企业知识库问答" not in app + login + router


def test_frontend_api_exports_ecommerce_client():
    client = read("frontend/src/api/client.ts")
    assert "export const ecommerceAPI" in client
    assert 'client.get("/ecommerce/dashboard")' in client
    assert 'client.post("/ecommerce/agent/analyze"' in client
    assert 'campaignPlan: (goal = "大促增长")' in client


def test_ecommerce_pages_render_agent_and_analysis_terms():
    pages = [
        "frontend/src/views/Ecommerce/Dashboard.vue",
        "frontend/src/views/Ecommerce/AgentWorkspace.vue",
        "frontend/src/views/Ecommerce/Products.vue",
        "frontend/src/views/Ecommerce/Campaigns.vue",
        "frontend/src/views/Ecommerce/Recommendations.vue",
    ]
    content = "\n".join(read(path) for path in pages)

    assert "GMV" in content
    assert "GMV 趋势图" in content
    assert "GMV 归因" in content
    assert "Agent 执行轨迹" in content
    assert "数据证据" in content
    assert "商品分层" in content
    assert "ABC 分层" in content
    assert "建议审批" in content


def test_public_copy_has_no_mojibake_markers():
    files = [
        "README.md",
        "frontend/src/App.vue",
        "frontend/src/views/Login.vue",
        "frontend/src/views/Ecommerce/Dashboard.vue",
        "frontend/src/views/Ecommerce/AgentWorkspace.vue",
        "frontend/src/views/Ecommerce/Products.vue",
        "frontend/src/views/Ecommerce/Campaigns.vue",
        "frontend/src/views/Ecommerce/Recommendations.vue",
        "backend/main.py",
        "backend/api/ecommerce.py",
        "backend/ecommerce/agent.py",
        "backend/ecommerce/anomaly.py",
        "backend/ecommerce/metrics.py",
        "backend/ecommerce/segmentation.py",
        "backend/ecommerce/tools.py",
    ]

    offenders = {
        path: [marker for marker in MOJIBAKE_MARKERS if marker in read(path)]
        for path in files
    }
    offenders = {path: markers for path, markers in offenders.items() if markers}

    assert offenders == {}


def test_enterprise_agent_routes_and_workflows_are_exposed():
    router = read("frontend/src/router/index.ts")
    app = read("frontend/src/App.vue")
    client = read("frontend/src/api/client.ts")
    pages = "\n".join(read(path) for path in [
        "frontend/src/views/Ecommerce/AgentWorkspace.vue",
        "frontend/src/views/Ecommerce/Customers.vue",
        "frontend/src/views/Ecommerce/Runs.vue",
        "frontend/src/views/Ecommerce/AgentEvaluation.vue",
        "frontend/src/views/Ecommerce/Recommendations.vue",
        "frontend/src/views/Ecommerce/Campaigns.vue",
    ])

    assert 'path: "/customers"' in router
    assert 'path: "/runs"' in router
    assert 'path: "/agent-evaluation"' in router
    assert "客户分析" in app
    assert "运行中心" in app
    assert "sessions:" in client
    assert "sessionDetail:" in client
    assert "runSummary:" in client
    assert "execution_mode" in pages
    assert "模拟测算" in pages
    assert "审批审计" in pages
    assert "RFM" in pages


def test_product_page_exposes_durable_simulation_controls_and_deltas():
    client = read("frontend/src/api/client.ts")
    products = read("frontend/src/views/Ecommerce/Products.vue")

    assert "simulationState:" in client
    assert "advanceSimulation:" in client
    assert "resetSimulation:" in client
    assert "expected_version" in client
    for copy in ("模拟日期", "推进一天", "重置模拟", "今日经营事件"):
        assert copy in products
    assert "row.deltas" in products
