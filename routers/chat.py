from fastapi import APIRouter, Depends
from schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryItem
from core.security import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Kirim pesan ke AI. Buat sesi baru jika session_id tidak ada,
    atau lanjutkan sesi yang sudah ada.
    Business logic AI (YouTube search, transcript, LLM) belum diimplementasi.
    """
    raise NotImplementedError("AI pipeline belum diimplementasi")


@router.get("/history/{user_id}", response_model=list[ChatHistoryItem])
def get_chat_history(
    user_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Ambil daftar sesi chat milik user (untuk sidebar history).
    """
    raise NotImplementedError("Chat history belum diimplementasi")
