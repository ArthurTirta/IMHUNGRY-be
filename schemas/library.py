from pydantic import BaseModel
from uuid import UUID


class PublishRequest(BaseModel):
    session_id: UUID
    user_id: int
    selected_version: str
    visibility: int = 1


class PublishResponse(BaseModel):
    message: str
    tutorial_id: int


class LibraryItem(BaseModel):
    tutorial_id: int
    title: str
    creator: str
    video_id: str
    stars: int


class LibraryDetail(LibraryItem):
    tutorial_data: dict


class StarRequest(BaseModel):
    user_id: int


class StarResponse(BaseModel):
    message: str
    new_total_stars: int
