from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.security import get_current_user_id
from db.session import get_db
from models.library import Library
from models.tutorial_stars import TutorialStar
from models.user import User
from schemas.dashboard import DashboardResponse, DashboardStats, DashboardRecipeHighlight

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _step_count(recipe_data: dict | None) -> int:
    if not recipe_data:
        return 0
    return len(recipe_data.get("tutorial", {}).get("steps", []))


def _to_highlight(row: Library, location: str | None) -> DashboardRecipeHighlight:
    return DashboardRecipeHighlight(
        recipe_id=row.id,
        session_id=row.session_id,
        title=row.title,
        video_id=row.video_id or (row.recipe or {}).get("video_id", ""),
        stars=row.stars,
        visibility=row.visibility,
        steps=_step_count(row.recipe),
        created_at=row.created_at,
        location=location,
    )


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Ringkasan statistik dan highlight resep milik user yang login."""
    user = db.query(User).filter(User.id == user_id).first()
    location = user.location if user else None

    recipes = (
        db.query(Library)
        .filter(Library.user_id == user_id)
        .order_by(Library.created_at.desc())
        .all()
    )

    published = [r for r in recipes if r.visibility == 1]
    starred_count = (
        db.query(TutorialStar)
        .filter(TutorialStar.user_id == user_id)
        .count()
    )

    top_stars = max((r.stars for r in published), default=0)

    recently_modified = _to_highlight(recipes[0], location) if recipes else None

    top_published_row = (
        db.query(Library)
        .filter(Library.user_id == user_id, Library.visibility == 1)
        .order_by(Library.stars.desc(), Library.created_at.desc())
        .first()
    )
    top_published = _to_highlight(top_published_row, location) if top_published_row else None

    return DashboardResponse(
        stats=DashboardStats(
            menu_created=len(recipes),
            published_count=len(published),
            top_stars=top_stars,
            starred_count=starred_count,
        ),
        recently_modified=recently_modified,
        top_published=top_published,
    )
