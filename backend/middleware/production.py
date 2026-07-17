"""Request IDs, Prometheus metrics, Redis rate limits, concurrency and audit logging."""
import asyncio
import time
import uuid
import re

from fastapi import Request
from fastapi.responses import JSONResponse
import jwt
from jwt import InvalidTokenError
from prometheus_client import Counter, Histogram

from backend.config import settings
from backend.db.models import AuditLog
from backend.db.session import AsyncSessionLocal
from backend.utils.logger import logger
from backend.services.cache_service import cache_service
from backend.security.production_config import password_rotation_allows

REQUESTS = Counter("ecommerce_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("ecommerce_http_request_duration_seconds", "HTTP request latency", ["method", "path"])
ERRORS = Counter("ecommerce_http_errors_total", "Unhandled HTTP errors", ["path"])
EXPENSIVE_PATHS = (
    "/api/ecommerce/conversations/messages",
    "/api/ecommerce/execution/tasks",
    "/api/ecommerce/autonomous/tasks",
)
LOCAL_DEMO_FAIL_OPEN_PATHS = {"/api/login", "/api/register"}
LOCAL_DEMO_FAIL_OPEN_PREFIXES = ("/api/ecommerce/",)
_expensive = asyncio.Semaphore(settings.MAX_CONCURRENT_EXPENSIVE_REQUESTS)
_UUID_SEGMENT = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,}$", re.I)
_NUMBER_SEGMENT = re.compile(r"^\d+$")


def normalized_route(path: str) -> str:
    return "/".join(
        "{id}" if _UUID_SEGMENT.fullmatch(segment) or _NUMBER_SEGMENT.fullmatch(segment) else segment
        for segment in path.split("/")
    )


def _identity(request: Request) -> tuple[str, str]:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return str(payload.get("sub", "anonymous")), str(payload.get("role", ""))
        except InvalidTokenError:
            pass
    forwarded = request.headers.get("x-forwarded-for", "")
    return (forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown"), "")


async def _allow_request(identity: str, fail_closed: bool = False) -> tuple[bool, int, bool]:
    redis = cache_service.redis
    try:
        minute = int(time.time() // 60)
        day = int(time.time() // 86400)
        minute_key = f"limit:minute:{identity}:{minute}"
        day_key = f"limit:day:{identity}:{day}"
        pipe = redis.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 120)
        pipe.incr(day_key)
        pipe.expire(day_key, 172800)
        minute_count, _, day_count, _ = await pipe.execute()
        allowed = minute_count <= settings.RATE_LIMIT_PER_MINUTE and day_count <= settings.DAILY_REQUEST_QUOTA
        return allowed, max(0, settings.RATE_LIMIT_PER_MINUTE - int(minute_count)), False
    except Exception as exc:
        logger.warning("Rate limiter unavailable fail_closed=%s: %s", fail_closed, exc)
        return not fail_closed, settings.RATE_LIMIT_PER_MINUTE, True


def _rate_limit_fail_closed(method: str, path: str) -> bool:
    if settings.APP_ENV.lower() != "production" and (
        path in LOCAL_DEMO_FAIL_OPEN_PATHS
        or any(path.startswith(prefix) for prefix in LOCAL_DEMO_FAIL_OPEN_PREFIXES)
    ):
        return False
    return method in {"POST", "PUT", "PATCH", "DELETE"} or any(path.startswith(prefix) for prefix in EXPENSIVE_PATHS)


def _skip_external_controls(path: str) -> bool:
    return settings.APP_ENV.lower() != "production" and any(path.startswith(prefix) for prefix in LOCAL_DEMO_FAIL_OPEN_PREFIXES)


async def production_middleware(request: Request, call_next):
    started = time.perf_counter()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    identity, role = _identity(request)
    path = request.url.path
    metric_path = normalized_route(path)
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if not password_rotation_allows(path, bool(payload.get("must_change_password", False))):
                return JSONResponse(
                    {"code": 403, "msg": "Password change required", "error": "PASSWORD_CHANGE_REQUIRED"},
                    status_code=403,
                    headers={"X-Request-ID": request_id},
                )
        except InvalidTokenError:
            pass
    skip_external_controls = _skip_external_controls(path)
    if skip_external_controls:
        allowed, remaining, limiter_unavailable = True, "local-demo", False
    else:
        fail_closed = _rate_limit_fail_closed(request.method, path)
        allowed, remaining, limiter_unavailable = await _allow_request(identity, fail_closed=fail_closed)
    if not allowed:
        if limiter_unavailable:
            return JSONResponse(
                {"code": 503, "msg": "Rate limit service unavailable", "error": "REDIS_REQUIRED"},
                status_code=503,
                headers={"Retry-After": "30", "X-Request-ID": request_id},
            )
        return JSONResponse({"code": 429, "msg": "Request rate or daily quota exceeded"}, status_code=429, headers={"Retry-After": "60", "X-Request-ID": request_id})

    status_code = 500
    try:
        if any(path.startswith(prefix) for prefix in EXPENSIVE_PATHS):
            async with _expensive:
                response = await call_next(request)
        else:
            response = await call_next(request)
        status_code = response.status_code
    except Exception:
        ERRORS.labels(path=metric_path).inc()
        logger.exception(f"Unhandled request error request_id={request_id} path={path}")
        raise
    finally:
        elapsed = time.perf_counter() - started
        REQUESTS.labels(method=request.method, path=metric_path, status=str(status_code)).inc()
        LATENCY.labels(method=request.method, path=metric_path).observe(elapsed)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and path != "/api/login" and not skip_external_controls:
        try:
            async with AsyncSessionLocal() as db:
                db.add(AuditLog(
                    username=identity,
                    role=role,
                    action=request.method,
                    resource_type=path.split("/")[2] if len(path.split("/")) > 2 else "api",
                    resource_id=path.rsplit("/", 1)[-1],
                    path=path,
                    status_code=status_code,
                    ip_address=request.client.host if request.client else "",
                    request_id=request_id,
                ))
                await db.commit()
        except Exception as exc:
            logger.warning(f"Audit write failed request_id={request_id}: {exc}")
    return response
