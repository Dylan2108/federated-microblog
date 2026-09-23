from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

class Actor(Base):
    """Un usuario, local a este servidor o cacheado desde uno remoto."""

    __tablename__ =  "actors"

    id: Mapped[str] = mapped_column(String,primary_key=True)
    username: Mapped[str] = mapped_column(String, index=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True, default=lambda: datetime.now(timezone.utc))
    )