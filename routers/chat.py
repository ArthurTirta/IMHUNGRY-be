from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.security import get_current_user, get_current_user_id
from db.session import get_db
from models.chat import Chat
from schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryItem, ChatSessionDetail
from services.chat.general_ai import process_message
from services.chat.recipe_tools import enrich_with_recipe

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return process_message(payload, current_user, db)


@router.get("/session/{session_id}", response_model=ChatSessionDetail)
def get_session_detail(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    chat_session = db.query(Chat).filter(
        Chat.id == session_id,
        Chat.user_id == user_id,
    ).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan")

    enriched = enrich_with_recipe(chat_session.messages or [], db)
    return ChatSessionDetail(
        session_id=chat_session.id,
        title=chat_session.title,
        messages=enriched,
    )


@router.get("/history/{user_id}", response_model=list[ChatHistoryItem])
def get_chat_history(
    user_id: UUID,
    requester_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
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
