from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID


class ChatMessageRequest(BaseModel):
    message: str
    session_id: UUID | None = None

    @field_validator("session_id", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "" or v is None:
            return None
        return v


class MessageEntry(BaseModel):
    question: str
    answer: str
    recipe_id: UUID | None = None
    recipe: dict | None = None  # populated at response time from recipe_local, tidak disimpan di chat.messages


class ChatMessageResponse(BaseModel):
    session_id: UUID
    messages: list[MessageEntry]


class ChatSessionDetail(BaseModel):
    session_id: UUID
    title: str | None = None
    messages: list[MessageEntry]


class ChatHistoryItem(BaseModel):
    session_id: UUID
    title: str | None = None
    created_at: datetime
