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
    requester_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Detail resep untuk Cook Mode — wajib login.
    Bisa diakses jika pemilik resep ATAU resep sudah public (global feed).
    """
    recipe = db.query(Library).filter(Library.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe tidak ditemukan")

    is_owner = requester_id == recipe.user_id
    is_public = recipe.visibility == 1

    if not is_owner and not is_public:
        raise HTTPException(status_code=403, detail="Resep ini masih private")

    return {
        "id": str(recipe.id),
        "session_id": str(recipe.session_id) if is_owner else None,
        "title": recipe.title,
        "video_id": recipe.video_id or (recipe.recipe or {}).get("video_id", ""),
        "recipe": recipe.recipe,
        "visibility": recipe.visibility,
        "stars": recipe.stars,
        "created_at": recipe.created_at.isoformat(),
    }
