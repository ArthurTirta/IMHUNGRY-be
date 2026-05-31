from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.security import get_current_user
from db.session import get_db
from models.chat import Chat
from schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryItem
from services.chat.general_ai import process_message

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return process_message(payload, current_user, db)


@router.get("/history/{user_id}", response_model=list[ChatHistoryItem])
def get_chat_history(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    requester_id = int(current_user["sub"])
    if requester_id != user_id:
        raise HTTPException(status_code=403, detail="Tidak bisa mengakses history user lain")

    sessions = (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .all()
    )

    return [
        ChatHistoryItem(
            session_id=s.id,
            title=s.title,
            created_at=s.created_at,
        )
        for s in sessions
    ]
