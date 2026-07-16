import pytest

from backend.ecommerce.persistence.repository import EcommerceRepository, VersionConflict


@pytest.mark.asyncio
async def test_sessions_and_messages_survive_repository_restart(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}"
    first = EcommerceRepository(url)
    await first.initialize()
    session = await first.create_session(user_id="user-1", title="GMV 诊断")
    await first.append_message(session.id, "user", "昨天 GMV 为什么下降？")
    await first.dispose()

    second = EcommerceRepository(url)
    await second.initialize()
    restored = await second.get_session(session.id)
    assert restored is not None
    assert restored.title == "GMV 诊断"
    assert [item.content for item in restored.messages] == ["昨天 GMV 为什么下降？"]
    await second.dispose()


@pytest.mark.asyncio
async def test_approval_is_idempotent_and_writes_audit_record(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    recommendation = await repository.create_recommendation(
        title="暂停低 ROI 广告", action_type="ad_budget_pause", risk_level="high",
        reason="ROI 低于阈值", expected_impact="减少无效消耗", evidence=[],
    )

    approved = await repository.transition_recommendation(
        recommendation.id, "approved", expected_version=1, operator="admin",
        comment="数据证据充分", idempotency_key="approve-1",
    )
    duplicate = await repository.transition_recommendation(
        recommendation.id, "approved", expected_version=1, operator="admin",
        comment="数据证据充分", idempotency_key="approve-1",
    )
    audit = await repository.list_approvals(recommendation.id)

    assert approved.version == 2
    assert duplicate.version == 2
    assert len(audit) == 1
    assert audit[0].comment == "数据证据充分"
    await repository.dispose()


@pytest.mark.asyncio
async def test_approval_rejects_stale_version(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    recommendation = await repository.create_recommendation(
        title="补货", action_type="restock", risk_level="medium", reason="低于安全库存",
        expected_impact="避免断货", evidence=[],
    )
    await repository.transition_recommendation(
        recommendation.id, "approved", 1, "admin", "确认", "first",
    )

    with pytest.raises(VersionConflict):
        await repository.transition_recommendation(
            recommendation.id, "rejected", 1, "reviewer", "版本已过期", "second",
        )
    await repository.dispose()
