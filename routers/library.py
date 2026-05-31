from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.security import get_current_user_id
from db.session import get_db
from models.library import Library
from models.tutorial_stars import TutorialStar
from models.user import User
from schemas.library import (
    PublishRequest, PublishResponse,
    UnpublishRequest,
    LibraryItem, LibraryDetail,
    StarResponse,
)

router = APIRouter(prefix="/library", tags=["library"])


@router.post("/publish", response_model=PublishResponse)
def publish_recipe(
    payload: PublishRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Ubah visibility recipe menjadi public (1)."""
    recipe = db.query(Library).filter(
        Library.id == payload.recipe_id,
        Library.user_id == user_id,
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe tidak ditemukan")

    recipe.visibility = 1
    db.commit()
    return PublishResponse(
        message="Recipe berhasil dipublish ke global feed",
        recipe_id=recipe.id,
        visibility=recipe.visibility,
    )


@router.post("/unpublish", response_model=PublishResponse)
def unpublish_recipe(
    payload: UnpublishRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Ubah visibility recipe menjadi private (0)."""
    recipe = db.query(Library).filter(
        Library.id == payload.recipe_id,
        Library.user_id == user_id,
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe tidak ditemukan")

    recipe.visibility = 0
    db.commit()
    return PublishResponse(
        message="Recipe diset ke private",
        recipe_id=recipe.id,
        visibility=recipe.visibility,
    )


@router.get("", response_model=list[LibraryItem])
def list_public_library(db: Session = Depends(get_db)):
    """Ambil semua recipe public tanpa JWT — bisa diakses siapa saja."""
    rows = (
        db.query(Library, User.username)
        .join(User, Library.user_id == User.id)
        .filter(Library.visibility == 1)
        .order_by(Library.stars.desc(), Library.created_at.desc())
        .all()
    )
    return [
        LibraryItem(
            id=row.Library.id,
            session_id=row.Library.session_id,
            title=row.Library.title,
            video_id=row.Library.video_id,
            stars=row.Library.stars,
            visibility=row.Library.visibility,
            creator=row.username,
            created_at=row.Library.created_at,
        )
        for row in rows
    ]


@router.get("/mine", response_model=list[LibraryItem])
def list_my_recipes(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Semua recipe milik user yang login (private + public)."""
    user = db.query(User).filter(User.id == user_id).first()
    rows = (
        db.query(Library)
        .filter(Library.user_id == user_id)
        .order_by(Library.created_at.desc())
        .all()
    )
    return [
        LibraryItem(
            id=r.id,
            session_id=r.session_id,
            title=r.title,
            video_id=r.video_id,
            stars=r.stars,
            visibility=r.visibility,
            creator=user.username if user else "",
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/starred", response_model=list[LibraryItem])
def list_starred_recipes(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Resep global yang sudah diberi bintang oleh user yang login."""
    rows = (
        db.query(Library, User.username)
        .join(TutorialStar, TutorialStar.recipe_id == Library.id)
        .join(User, Library.user_id == User.id)
        .filter(
            TutorialStar.user_id == user_id,
            Library.visibility == 1,
        )
        .order_by(Library.stars.desc(), Library.created_at.desc())
        .all()
    )
    return [
        LibraryItem(
            id=row.Library.id,
            session_id=row.Library.session_id,
            title=row.Library.title,
            video_id=row.Library.video_id,
            stars=row.Library.stars,
            visibility=row.Library.visibility,
            creator=row.username,
            created_at=row.Library.created_at,
        )
        for row in rows
    ]


@router.get("/{recipe_id}", response_model=LibraryDetail)
def get_public_recipe(recipe_id: UUID, db: Session = Depends(get_db)):
    """Detail recipe public — tidak butuh JWT."""
    row = (
        db.query(Library, User.username)
        .join(User, Library.user_id == User.id)
        .filter(Library.id == recipe_id, Library.visibility == 1)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Recipe tidak ditemukan atau masih private")

    return LibraryDetail(
        id=row.Library.id,
        title=row.Library.title,
        video_id=row.Library.video_id,
        stars=row.Library.stars,
        visibility=row.Library.visibility,
        creator=row.username,
        created_at=row.Library.created_at,
        recipe=row.Library.recipe,
    )


@router.put("/{recipe_id}/star", response_model=StarResponse)
def toggle_star(
    recipe_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Toggle bintang pada recipe public."""
    recipe = db.query(Library).filter(
        Library.id == recipe_id,
        Library.visibility == 1,
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe tidak ditemukan atau masih private")

    existing = db.query(TutorialStar).filter(
        TutorialStar.user_id == user_id,
        TutorialStar.recipe_id == recipe_id,
    ).first()

    if existing:
        db.delete(existing)
        recipe.stars = max(0, recipe.stars - 1)
        msg = "Bintang dicabut"
    else:
        db.add(TutorialStar(user_id=user_id, recipe_id=recipe_id))
        recipe.stars += 1
        msg = "Bintang ditambahkan"

    db.commit()
    return StarResponse(message=msg, new_total_stars=recipe.stars)
