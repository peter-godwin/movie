import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class TokenBlocklist(Base):
    __tablename__ = "token_blocklist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(512), unique=True, nullable=False, index=True)
    token_type = Column(String(10), nullable=False)  # "access" or "refresh"
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )