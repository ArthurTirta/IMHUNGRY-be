from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class ChatMessageRequest(BaseModel):
    message: str
    session_id: UUID | None = None


class MessageEntry(BaseModel):
    question: str
    answer: dict


class ChatMessageResponse(BaseModel):
    session_id: UUID
    messages: list[MessageEntry]


class ChatHistoryItem(BaseModel):
    session_id: UUID
    title: str | None = None
    created_at: datetime
