from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_resume_and_demo_docs_exist():
    resume = read("docs/resume.md")
    demo = read("docs/demo-script.md")

    assert "智能电商运营 Agent 平台" in resume
    assert "GMV 归因" in resume
    assert "3 分钟演示脚本" in demo
    assert "Agent 执行轨迹" in demo


def test_readme_documents_demo_and_production_boundary():
    readme = read("README.md")

    assert "本地可演示" in readme
    assert "Demo 与生产边界" in readme
    assert "development" in readme
    assert "production" in readme


def test_docs_describe_implemented_enterprise_agent_capabilities_without_false_claims():
    content = read("README.md") + read("docs/resume.md") + read("docs/architecture.md")
    for term in ("DeepSeek", "确定性降级", "90 天", "RFM", "Agent 评测", "SQLite", "审批审计"):
        assert term in content
    assert "已接入淘宝" not in content
    assert "已投入生产" not in content
