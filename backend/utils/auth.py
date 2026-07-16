"""
认证工具：密码哈希、JWT 生成与验证
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import InvalidTokenError

from backend.config import settings

security = HTTPBearer(auto_error=False)


# ====================== 密码 ======================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ====================== JWT ======================

def create_access_token(username: str, role: str = "user", must_change_password: bool = False, workspace_id: str = "") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "workspace_id": workspace_id or f"workspace:{username}",
        "must_change_password": must_change_password,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """从 JWT 中提取当前用户信息"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        username: str = payload.get("sub")
        role: str = payload.get("role", "user")
        if username is None:
            raise HTTPException(status_code=401, detail="无效的令牌")
        return {
            "username": username,
            "role": role,
            "workspace_id": payload.get("workspace_id") or f"workspace:{username}",
            "must_change_password": bool(payload.get("must_change_password", False)),
        }
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的令牌")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """要求管理员权限"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
