from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ToolStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


class ToolResponse(BaseModel):
    status: ToolStatus
    code: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    stats: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))

    @classmethod
    def success(cls, data: dict[str, Any], message: str = "ok", **stats) -> "ToolResponse":
        return cls(status=ToolStatus.SUCCESS, code="OK", message=message, data=data, stats=stats)

    @classmethod
    def partial(cls, data: dict[str, Any], message: str, code: str = "PARTIAL_RESULT", **stats) -> "ToolResponse":
        return cls(status=ToolStatus.PARTIAL, code=code, message=message, data=data, stats=stats)

    @classmethod
    def error(cls, code: str, message: str, retryable: bool = False, **stats) -> "ToolResponse":
        return cls(status=ToolStatus.ERROR, code=code, message=message, retryable=retryable, stats=stats)


class MCPToolError(RuntimeError):
    def __init__(self, response: ToolResponse):
        super().__init__(f"{response.code}: {response.message}")
        self.response = response
