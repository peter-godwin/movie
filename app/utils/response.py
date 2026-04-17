from typing import Any, Optional
from app.schemas.base import StandardResponse

def send_response(data: Any = None, message: Optional[str] = None, status: str = "success") -> StandardResponse:
    return StandardResponse(
        status=status,
        message=message,
        data=data
    )
