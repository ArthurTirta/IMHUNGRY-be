from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from db.session import Base


class Library(Base):
    """
    Tabel tunggal untuk semua recipe yang dibuat AI.
    visibility=0 → private (draft), visibility=1 → public (published ke global feed).
    stars di-cache di sini; detail voting ada di tabel tutorial_stars.
    """
    __tablename__ = "library"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(String, nullable=False, server_default="")
    recipe = Column(JSONB, nullable=False, server_default="{}")
    visibility = Column(Integer, nullable=False, server_default="0")  # 0=private, 1=public
    stars = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
