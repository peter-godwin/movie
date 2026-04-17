from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    status: str = "success"
    message: str | None = None
    data: T | None = None


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    details: Any | None = None