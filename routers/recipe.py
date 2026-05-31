from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.security import get_current_user_id
from db.session import get_db
from models.library import Library

router = APIRouter(prefix="/recipe", tags=["recipe"])


@router.get("/{recipe_id}")
def get_recipe(
    recipe_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    recipe = db.query(Library).filter(
        Library.id == recipe_id,
        Library.user_id == user_id,
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe tidak ditemukan")

    return {
        "id": str(recipe.id),
        "session_id": str(recipe.session_id),
        "title": recipe.title,
        "video_id": recipe.video_id,
        "recipe": recipe.recipe,
        "visibility": recipe.visibility,
        "stars": recipe.stars,
        "created_at": recipe.created_at.isoformat(),
    }
