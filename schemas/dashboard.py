from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DashboardStats(BaseModel):
    menu_created: int
    published_count: int
    top_stars: int
    starred_count: int


class DashboardRecipeHighlight(BaseModel):
    recipe_id: UUID
    session_id: UUID
    title: str
    video_id: str
    stars: int
    visibility: int
    steps: int
    created_at: datetime
    location: str | None = None


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recently_modified: DashboardRecipeHighlight | None = None
    top_published: DashboardRecipeHighlight | None = None
