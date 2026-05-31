from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class PublishRequest(BaseModel):
    recipe_id: UUID  # UUID dari tabel library yang ingin dipublish


class PublishResponse(BaseModel):
    message: str
    recipe_id: UUID
    visibility: int


class UnpublishRequest(BaseModel):
    recipe_id: UUID


class LibraryItem(BaseModel):
    id: UUID
    session_id: UUID
    title: str
    video_id: str
    stars: int
    visibility: int
    creator: str
    created_at: datetime


class LibraryDetail(LibraryItem):
    recipe: dict  # full JSONB tutorial data


class StarRequest(BaseModel):
    pass  # user diambil dari JWT token


class StarResponse(BaseModel):
    message: str
    new_total_stars: int
