from fastapi import APIRouter, Depends
from schemas.library import (
    PublishRequest, PublishResponse,
    LibraryItem, LibraryDetail,
    StarRequest, StarResponse,
)
from core.security import get_current_user

router = APIRouter(prefix="/library", tags=["library"])


@router.post("/publish", response_model=PublishResponse, status_code=201)
def publish_tutorial(
    payload: PublishRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Ekstrak versi terpilih dari sesi chat dan simpan ke library publik/privat.
    """
    raise NotImplementedError("Publish belum diimplementasi")


@router.get("", response_model=list[LibraryItem])
def list_library():
    """
    Ambil semua tutorial publik (visibility=1) tanpa payload JSON berat.
    Endpoint ini tidak butuh JWT — bisa diakses siapa saja.
    """
    raise NotImplementedError("Library list belum diimplementasi")


@router.get("/{tutorial_id}", response_model=LibraryDetail)
def get_tutorial(tutorial_id: int):
    """
    Ambil detail lengkap tutorial termasuk tutorial_data JSON
    untuk merender interactive player.
    """
    raise NotImplementedError("Tutorial detail belum diimplementasi")


@router.put("/{tutorial_id}/star", response_model=StarResponse)
def toggle_star(
    tutorial_id: int,
    payload: StarRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Toggle bintang — tambah jika belum pernah, hapus jika sudah.
    Menggunakan atomic transaction untuk mencegah race condition.
    """
    raise NotImplementedError("Star toggle belum diimplementasi")
