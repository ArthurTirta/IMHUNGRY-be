from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from db.session import Base


class TutorialStar(Base):
    __tablename__ = "tutorial_stars"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("library.id"), primary_key=True)
