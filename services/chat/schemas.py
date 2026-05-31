"""
Pydantic schemas internal untuk structured output AI tutorial generator.
Berbeda dari schemas/chat.py yang berisi public request/response schemas.
"""
from typing import Literal

from pydantic import BaseModel


class _ToolItem(BaseModel):
    name: str
    timer_seconds: int | None = None  # detik hitung mundur, diisi bila langkah butuh waktu tunggu


class _Ingredient(BaseModel):
    name: str
    amount: str
    price: int


class _CookingTool(BaseModel):
    name: str
    amount: str


class _Step(BaseModel):
    timestamp: int
    instruction: str
    tools: list[_ToolItem]


class _Tutorial(BaseModel):
    ingredients: list[_Ingredient]
    tools: list[_CookingTool]
    steps: list[_Step]


class TutorialOutput(BaseModel):
    estimated_budget: int
    video_id: str
    tutorial: _Tutorial


class TutorialQueryOutput(BaseModel):
    """Output untuk mode follow-up query pada resep yang sudah ada."""
    response_type: Literal["text", "recipe", "both"]
    text: str
    estimated_budget: int | None = None
    video_id: str | None = None
    tutorial: _Tutorial | None = None

