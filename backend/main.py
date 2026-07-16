"""智能电商运营 Agent 平台 - FastAPI service entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.api import admin, auth, chat, documents, ecommerce, enterprise_auth, evaluation, health, knowledge_bases, operations
from backend.config import settings
from backend.middleware.production import production_middleware
from backend.security.production_config import assert_production_settings
from backend.services.reranker_service import reranker
from backend.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle."""
    logger.info("=" * 50)
    logger.info("智能电商运营 Agent 平台启动")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"LLM 模型: {settings.LLM_MODEL}")
    logger.info(f"嵌入维度: {settings.EMBEDDING_DIM}")
    logger.info("=" * 50)
    assert_production_settings(settings)
    yield
    await ecommerce.close_execution_runtime()
    logger.info("系统关闭")


app = FastAPI(
    title="智能电商运营 Agent 平台",
    description="基于模拟电商经营数据、工具调用和审批闭环的 AI 运营决策系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS is explicit and environment-configurable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.CORS_ORIGINS.split(",") if item.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def apply_production_middleware(request, call_next):
    return await production_middleware(request, call_next)


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(knowledge_bases.router)
app.include_router(evaluation.router)
app.include_router(enterprise_auth.router)
app.include_router(operations.router)
app.include_router(health.router)
app.include_router(ecommerce.router)


@app.get("/api/health")
async def health_check():
    """Health check and model capability summary."""
    return {
        "status": "ok",
        "app": "ecommerce-operations-agent",
        "models": {
            "chat": f"{settings.LLM_MODEL} (optional LLM enhancement)",
            "orchestration": "Deterministic ecommerce tools + optional LangChain Runnable",
            "embedding": "text-embedding-v3 + multimodal-embedding-v1 (for operations knowledge base)",
            "reranker": reranker.get_model_info(),
            "vision": "qwen-vl-plus (DashScope, optional)" if settings.DASHSCOPE_API_KEY else "not configured",
        },
        "config": {
            "retrieval_top_k": settings.RETRIEVAL_TOP_K,
            "rerank_top_k": settings.RETRIEVAL_RERANK_TOP_K,
            "use_rerank": settings.RETRIEVAL_USE_RERANK,
        },
    }


@app.get("/")
async def root():
    """Root route."""
    return {
        "app": "智能电商运营 Agent 平台",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "version": "1.0.0",
        "primary_workflow": "/api/ecommerce/dashboard",
    }


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
