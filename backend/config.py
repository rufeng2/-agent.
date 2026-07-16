"""Application configuration loaded from environment and optional secret files."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://ecommerce_admin:change_me_plz@localhost:5432/ecommerce_ops"
    ECOMMERCE_DATABASE_URL: str = "sqlite+aiosqlite:///./data/ecommerce_agent.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    REDIS_URL: str = "redis://localhost:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ecommerce-agent"
    MINIO_SECURE: bool = False
    USE_MINIO: bool = False

    SECRET_KEY: str = "your-256-bit-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PRODUCTION_MAX_TOKEN_MINUTES: int = 120

    DASHSCOPE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    PROVIDER_TIMEOUT_SECONDS: float = 45.0
    PROVIDER_CIRCUIT_FAILURES: int = 3
    PROVIDER_CIRCUIT_RECOVERY_SECONDS: float = 30.0
    AGENT_EXECUTION_MODE: str = "inline"
    AGENT_CELERY_QUEUE: str = "ecommerce_agent"
    AGENT_JOB_TIME_LIMIT_SECONDS: int = 300

    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    MULTIMODAL_EMBEDDING_MODEL: str = "multimodal-embedding-v1"

    RETRIEVAL_TOP_K: int = 20
    RETRIEVAL_RERANK_TOP_K: int = 6
    RETRIEVAL_USE_RERANK: bool = True
    RRF_K: int = 60
    RERANKER_MODEL: str = "gte-rerank-v2"
    INTENT_ROUTER_USE_LLM: bool = True
    INTENT_ROUTER_CONFIDENCE_THRESHOLD: float = 0.65
    RAG_CACHE_ENABLED: bool = True
    RETRIEVAL_CACHE_TTL_SECONDS: int = 600
    ANSWER_CACHE_TTL_SECONDS: int = 900
    INTENT_CACHE_TTL_SECONDS: int = 3600
    REFLECTION_ENABLED: bool = True
    REFLECTION_USE_LLM: bool = True
    LONG_TERM_MEMORY_ENABLED: bool = True
    LONG_TERM_MEMORY_TOP_K: int = 3
    LONG_TERM_MEMORY_MAX_PER_USER: int = 100

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123456"
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    BACKEND_DIR: Path = Path(__file__).parent

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    RATE_LIMIT_PER_MINUTE: int = 120
    DAILY_REQUEST_QUOTA: int = 5000
    MAX_CONCURRENT_EXPENSIVE_REQUESTS: int = 8
    CLAMAV_ENABLED: bool = False
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = 3310
    FILE_SCAN_FAIL_CLOSED: bool = True
    CONVERSATION_RETENTION_DAYS: int = 90
    DOCUMENT_RETENTION_DAYS: int = 365
    AUDIT_RETENTION_DAYS: int = 365

    OIDC_ENABLED: bool = False
    OIDC_ISSUER: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = "http://localhost:8080/api/sso/oidc/callback"
    LDAP_ENABLED: bool = False
    LDAP_SERVER: str = ""
    LDAP_USER_DN_TEMPLATE: str = "uid={username},ou=people,dc=example,dc=com"
    LDAP_USE_SSL: bool = True

    OPENSEARCH_ENABLED: bool = False
    OPENSEARCH_URL: str = "http://opensearch:9200"

    def model_post_init(self, __context) -> None:
        for name in (
            "DATABASE_URL", "SECRET_KEY", "ADMIN_PASSWORD", "MINIO_SECRET_KEY",
            "DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY", "OIDC_CLIENT_SECRET",
        ):
            secret_file = os.getenv(f"{name}_FILE", "").strip()
            if secret_file:
                value = Path(secret_file).read_text(encoding="utf-8").strip()
                if value:
                    object.__setattr__(self, name, value)

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
