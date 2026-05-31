"""
Pydantic schemas internal untuk structured output AI tutorial generator.
Berbeda dari schemas/chat.py yang berisi public request/response schemas.
"""
from pydantic import BaseModel


class _ToolItem(BaseModel):
    name: str
    value: int | None = None


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
